#!/usr/bin/env python3
"""Idempotent search-index migration for EXISTING rag-bootstrap databases.

Adds the two indexes that back the hot query shapes in ``app/search.py`` to
databases that were populated BEFORE index support landed:

  * ``idx_chunks_content_fts``   — GIN on ``to_tsvector('english', content)``
    (keyword / FTS leg of hybrid search; matches ``keyword_search`` exactly).
  * ``idx_chunks_embedding_hnsw`` — HNSW ``vector_cosine_ops`` (m=16,
    ef_construction=64) for the pgvector ``<=>`` cosine scan used by
    ``semantic_search``.

Fresh databases get these at init time (``app.database.init_db`` /
``PostgresKB.initialize``); this script is only for already-ingested DBs.

Why a separate script: the init paths create indexes NON-concurrently inside the
schema-creation transaction (instant on an empty table). On a populated table a
plain ``CREATE INDEX`` takes an ``ACCESS EXCLUSIVE`` lock for the whole build,
blocking reads/writes. This script uses ``CREATE INDEX CONCURRENTLY IF NOT
EXISTS`` so a LIVE instance keeps serving during the build. CONCURRENTLY cannot
run inside a transaction block, so each statement is issued in autocommit via a
dedicated asyncpg connection (no bound params -> simple query protocol).

Idempotent: ``IF NOT EXISTS`` skips indexes that already exist. Safe to re-run.

maintenance_work_mem note: the HNSW graph is built in ``maintenance_work_mem``;
if the whole vector set does not fit, pgvector spills to a slower on-disk build.
For ~20k x 768 fp32 (~58 MB) a value of ~256MB comfortably keeps the build in
memory. On a memory-capped host (e.g. the 1 GB scratch container) do NOT set
this above what the container can spare on top of shared_buffers/work_mem, or
the build can OOM. Pass ``--maintenance-work-mem`` to override for the session
(applies only to the build; left unchanged when omitted).

Container /dev/shm note: a PARALLEL HNSW build shares its graph through dynamic
shared memory in ``/dev/shm``, sized up to ``maintenance_work_mem``. Docker's
default ``--shm-size`` is only 64 MB, so a large ``maintenance_work_mem`` makes
the parallel build fail with "could not resize shared memory segment ... No
space left on device". Two fixes: run the container with a bigger ``--shm-size``,
OR pass ``--max-parallel-maintenance-workers 0`` to build single-process (the
graph then lives in ordinary backend RAM bounded by ``maintenance_work_mem``, not
/dev/shm). This script auto-cleans a leftover INVALID index from an interrupted
build before retrying.

Usage:
    # single database
    python scripts/migrate_indexes.py --database ragdb
    # every ragdb* logical KB on the server (multi-KB deployments)
    python scripts/migrate_indexes.py --all-kbs
    # scratch/throwaway container on a nonstandard host port
    python scripts/migrate_indexes.py --all-kbs --host 127.0.0.1 --port 15499 \
        --maintenance-work-mem 256MB

Connection defaults come from app.config.settings (POSTGRES_HOST/PORT/USER/
PASSWORD); any --host/--port/--user/--password/--database flag overrides.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import asyncpg

# Import the canonical index names so this script can never drift from the DDL
# the application uses. The CONCURRENTLY DDL below mirrors app.database's
# SEARCH_INDEX_DDL (same expressions/opclass/params) but adds CONCURRENTLY.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings  # noqa: E402
from app.database import (  # noqa: E402
    FACT_HNSW_INDEX_NAME,
    FTS_INDEX_NAME,
    HNSW_INDEX_NAME,
)

# (index_name, human_label, CONCURRENTLY DDL). Expressions MUST stay identical
# to app/search.py + app/database.SEARCH_INDEX_DDL.
INDEX_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        FTS_INDEX_NAME,
        "GIN full-text (to_tsvector('english', content))",
        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {FTS_INDEX_NAME} "
        "ON chunks USING gin (to_tsvector('english', content))",
    ),
    (
        HNSW_INDEX_NAME,
        "HNSW vector_cosine_ops (m=16, ef_construction=64)",
        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {HNSW_INDEX_NAME} "
        "ON chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)",
    ),
)


# B28 heat side table (additive, append-only). Mirrors app.database.ChunkHeat
# (chunk_id PK/FK CASCADE, hit_count, decayed_score, last_hit_at). Creating this
# empty table changes NO search result — recording stays gated by RAG_HEAT_ENABLED
# — so it is safe to add on any existing KB. Fresh DBs get it from init_db's
# create_all; this is the migration for already-ingested DBs. CREATE TABLE
# CANNOT run CONCURRENTLY, but it takes only a brief lock on a NEW relation (no
# existing rows to rewrite), so it is safe on a live instance.
_CHUNK_HEAT_TABLE_DDL = (
    "CREATE TABLE IF NOT EXISTS chunk_heat ("
    "chunk_id integer PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE, "
    "hit_count integer NOT NULL DEFAULT 0, "
    "decayed_score double precision NOT NULL DEFAULT 0.0, "
    "last_hit_at timestamptz NOT NULL DEFAULT now())"
)


async def _ensure_chunk_heat_table(conn: asyncpg.Connection) -> bool:
    """Create the additive chunk_heat side table if missing. Returns True on success."""
    exists = await conn.fetchval("SELECT to_regclass('public.chunk_heat') IS NOT NULL")
    if exists:
        print("  [skip] chunk_heat already present - B28 heat side table", flush=True)
        return True
    print("  [build] chunk_heat - B28 heat side table ...", flush=True)
    try:
        await conn.execute(_CHUNK_HEAT_TABLE_DDL)
    except Exception as exc:  # noqa: BLE001 - report + continue
        print(f"  [FAIL] chunk_heat: {exc}", flush=True)
        return False
    print("  [done] chunk_heat created", flush=True)
    return True


# B30 fact multi-vector index (additive, DEFAULT-OFF). Mirrors app.database
# ChunkFact + _FACT_HNSW_INDEX_DDL: a sibling `chunk_facts` table (one row per
# atomic fact split from a parent chunk) with a halfvec(768) embedding + its OWN
# HNSW (halfvec_cosine_ops). Creating the empty table + inert index changes NO
# search result — facts are only WRITTEN when RAG_FACT_INDEX_ENABLED is on at a
# deliberate re-ingest, and only QUERIED on a granularity="fact" request — so it
# is safe to add on any existing KB. Fresh DBs get the table from init_db's
# create_all; this is the migration for already-ingested DBs. Column types mirror
# the ORM (serial id, FK CASCADE like chunk_heat, json metadata). halfvec +
# halfvec_cosine_ops need pgvector >= 0.7, so BOTH the table create and the HNSW
# build are fail-soft: on an older server the fact feature simply stays absent
# (it is default-OFF), never aborting the chunk-index migration above.
_CHUNK_FACTS_TABLE_DDL = (
    "CREATE TABLE IF NOT EXISTS chunk_facts ("
    "id serial PRIMARY KEY, "
    "chunk_id integer NOT NULL REFERENCES chunks(id) ON DELETE CASCADE, "
    "fact_index integer NOT NULL, "
    "content text NOT NULL, "
    f"embedding halfvec({int(settings.EMBEDDING_DIMENSION)}), "
    "start_line integer, "
    "end_line integer, "
    "metadata json)"
)
_CHUNK_FACTS_CHUNK_ID_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS ix_chunk_facts_chunk_id ON chunk_facts (chunk_id)"
)
_FACT_HNSW_CONCURRENTLY_DDL = (
    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {FACT_HNSW_INDEX_NAME} "
    "ON chunk_facts USING hnsw (embedding halfvec_cosine_ops) "
    "WITH (m = 16, ef_construction = 64)"
)


async def _ensure_chunk_facts(conn: asyncpg.Connection) -> bool:
    """Create the additive chunk_facts table + its fact HNSW if missing.

    Fail-soft on both halfvec objects (pgvector >= 0.7): a failure here leaves the
    fact feature absent (default-OFF) and returns True so it never fails the whole
    migration. Returns True unless an unexpected error escapes.
    """
    exists = await conn.fetchval("SELECT to_regclass('public.chunk_facts') IS NOT NULL")
    if exists:
        print("  [skip] chunk_facts already present - B30 fact side table", flush=True)
    else:
        print("  [build] chunk_facts - B30 fact side table ...", flush=True)
        try:
            await conn.execute(_CHUNK_FACTS_TABLE_DDL)
            await conn.execute(_CHUNK_FACTS_CHUNK_ID_INDEX_DDL)
        except Exception as exc:  # noqa: BLE001 - halfvec may be unavailable (pgvector <0.7)
            print(
                f"  [skip] chunk_facts not created (fact feature stays absent): {exc}",
                flush=True,
            )
            return True
        print("  [done] chunk_facts created", flush=True)

    # Fact HNSW (halfvec_cosine_ops) — inert until facts exist; fail-soft.
    status = await _index_status(conn, FACT_HNSW_INDEX_NAME)
    if status == "valid":
        size = await _index_size(conn, FACT_HNSW_INDEX_NAME)
        print(f"  [skip] {FACT_HNSW_INDEX_NAME} already present ({size}) - B30 fact HNSW", flush=True)
        return True
    if status == "invalid":
        print(f"  [clean] dropping INVALID leftover {FACT_HNSW_INDEX_NAME}", flush=True)
        try:
            await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {FACT_HNSW_INDEX_NAME}")
        except Exception:  # noqa: BLE001
            pass
    print(f"  [build] {FACT_HNSW_INDEX_NAME} - B30 fact HNSW ...", flush=True)
    try:
        await conn.execute(_FACT_HNSW_CONCURRENTLY_DDL)
    except Exception as exc:  # noqa: BLE001 - halfvec_cosine_ops may be unavailable
        print(
            f"  [skip] {FACT_HNSW_INDEX_NAME} not built (facts stay unindexed): {exc}",
            flush=True,
        )
        try:
            await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {FACT_HNSW_INDEX_NAME}")
        except Exception:  # noqa: BLE001
            pass
        return True
    print(f"  [done] {FACT_HNSW_INDEX_NAME} built", flush=True)
    return True


# Symbol def-index (additive, DEFAULT-OFF). Mirrors app.database.Symbol: a sibling
# `symbols` table (one row per named code def-site chunk) with NO embedding/vector
# column — a def-index is an exact name lookup, not a similarity search. Creating
# the empty table + its btree indexes changes NO search result — rows are only
# WRITTEN when RAG_SYMBOL_INDEX is on at a deliberate re-ingest (or the offline
# scripts/build_symbol_index.py backfill), and only READ by /api/v2/symbol_lookup —
# so it is safe to add on any existing KB. Fresh DBs get the table from init_db's
# create_all; this is the migration for already-ingested DBs. Column types +
# index names mirror the ORM (serial id, FK CASCADE like chunk_heat/chunk_facts;
# the `lower(symbol_name)` functional index backs the case-insensitive lookup).
_SYMBOLS_TABLE_DDL = (
    "CREATE TABLE IF NOT EXISTS symbols ("
    "id serial PRIMARY KEY, "
    "chunk_id integer NOT NULL REFERENCES chunks(id) ON DELETE CASCADE, "
    "document_id integer, "
    "symbol_name varchar(512) NOT NULL, "
    "symbol_path varchar(1024), "
    "language varchar(50), "
    "start_line integer, "
    "end_line integer)"
)
_SYMBOLS_INDEX_DDL: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS ix_symbols_chunk_id ON symbols (chunk_id)",
    "CREATE INDEX IF NOT EXISTS ix_symbols_symbol_name ON symbols (symbol_name)",
    "CREATE INDEX IF NOT EXISTS ix_symbols_symbol_name_lower ON symbols (lower(symbol_name))",
)


async def _ensure_symbols(conn: asyncpg.Connection) -> bool:
    """Create the additive symbols def-index table + its btree indexes if missing.

    A NEW/empty relation takes only a brief lock, and the indexes on an empty table
    are instant, so this is safe on a live instance. Returns True on success.
    """
    exists = await conn.fetchval("SELECT to_regclass('public.symbols') IS NOT NULL")
    if exists:
        print("  [skip] symbols already present - symbol def-index table", flush=True)
    else:
        print("  [build] symbols - symbol def-index table ...", flush=True)
        try:
            await conn.execute(_SYMBOLS_TABLE_DDL)
        except Exception as exc:  # noqa: BLE001 - report + continue
            print(f"  [FAIL] symbols: {exc}", flush=True)
            return False
        print("  [done] symbols created", flush=True)
    ok = True
    for ddl in _SYMBOLS_INDEX_DDL:
        try:
            await conn.execute(ddl)
        except Exception as exc:  # noqa: BLE001 - report + continue other indexes
            print(f"  [FAIL] symbols index ({ddl.split()[5]}): {exc}", flush=True)
            ok = False
    return ok


async def _index_status(conn: asyncpg.Connection, name: str) -> str:
    """Return 'valid', 'invalid', or 'missing' for index ``name``."""
    row = await conn.fetchrow(
        "SELECT i.indisvalid "
        "FROM pg_class c "
        "JOIN pg_index i ON i.indexrelid = c.oid "
        "WHERE c.relname = $1",
        name,
    )
    if row is None:
        return "missing"
    # A leftover INVALID index (from an interrupted CONCURRENTLY build) reports
    # as existing but is unusable AND blocks CREATE ... IF NOT EXISTS by name.
    return "valid" if row["indisvalid"] else "invalid"


async def _index_size(conn: asyncpg.Connection, name: str) -> str:
    val = await conn.fetchval("SELECT pg_size_pretty(pg_relation_size($1::regclass))", name)
    return val or "?"


async def _has_chunks_table(conn: asyncpg.Connection) -> bool:
    return bool(await conn.fetchval("SELECT to_regclass('public.chunks') IS NOT NULL"))


async def migrate_database(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    maint_mem: str | None,
    parallel_workers: int | None,
) -> bool:
    """Create the search indexes on one database. Returns True on success."""
    print(f"\n=== {database} ===", flush=True)
    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=database
    )
    try:
        if not await _has_chunks_table(conn):
            print("  chunks table not found -> skipped (not a rag KB)", flush=True)
            return True

        chunk_count = await conn.fetchval("SELECT count(*) FROM chunks")
        print(f"  chunks: {chunk_count}", flush=True)

        # Extension must exist for the HNSW opclass to resolve.
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        if maint_mem:
            # Session-scoped; speeds the in-memory graph build. No bound params.
            await conn.execute(f"SET maintenance_work_mem = '{maint_mem}'")
            print(f"  maintenance_work_mem = {maint_mem} (this session)", flush=True)
        if parallel_workers is not None:
            await conn.execute(f"SET max_parallel_maintenance_workers = {int(parallel_workers)}")
            print(
                f"  max_parallel_maintenance_workers = {parallel_workers} (this session)",
                flush=True,
            )

        ok = True
        for name, label, ddl in INDEX_SPECS:
            status = await _index_status(conn, name)
            if status == "valid":
                size = await _index_size(conn, name)
                print(f"  [skip] {name} already present ({size}) - {label}", flush=True)
                continue
            if status == "invalid":
                # Interrupted CONCURRENTLY build left an unusable index that also
                # blocks CREATE ... IF NOT EXISTS; drop it before rebuilding.
                print(f"  [clean] dropping INVALID leftover {name}", flush=True)
                await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
            print(f"  [build] {name} - {label} ...", flush=True)
            t0 = time.perf_counter()
            try:
                await conn.execute(ddl)
            except Exception as exc:  # noqa: BLE001 - report + continue other indexes
                ok = False
                print(f"  [FAIL] {name}: {exc}", flush=True)
                # Drop the half-built INVALID index so a re-run starts clean.
                try:
                    await conn.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
                except Exception:  # noqa: BLE001
                    pass
                continue
            elapsed = time.perf_counter() - t0
            size = await _index_size(conn, name)
            print(f"  [done] {name} built in {elapsed:.1f}s, size {size}", flush=True)

        # B28 additive heat side table (append-only, safe on a live instance).
        if not await _ensure_chunk_heat_table(conn):
            ok = False
        # B30 additive fact side table + fact HNSW (DEFAULT-OFF, fail-soft on
        # halfvec; safe on a live instance — no rows until an opt-in fact-ingest).
        if not await _ensure_chunk_facts(conn):
            ok = False
        # Symbol def-index side table + btree indexes (DEFAULT-OFF; no rows until
        # an opt-in symbol-ingest or scripts/build_symbol_index.py backfill).
        if not await _ensure_symbols(conn):
            ok = False
        return ok
    finally:
        await conn.close()


async def discover_kb_databases(
    *, host: str, port: int, user: str, password: str
) -> list[str]:
    """Return all non-template ``ragdb*`` databases on the server (sorted)."""
    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database="postgres"
    )
    try:
        rows = await conn.fetch(
            "SELECT datname FROM pg_database "
            "WHERE datistemplate = false AND datname LIKE 'ragdb%' "
            "ORDER BY datname"
        )
        return [r["datname"] for r in rows]
    finally:
        await conn.close()


async def _amain(args: argparse.Namespace) -> int:
    host = args.host or settings.POSTGRES_HOST
    port = args.port or settings.POSTGRES_PORT
    user = args.user or settings.POSTGRES_USER
    password = args.password if args.password is not None else settings.POSTGRES_PASSWORD

    if args.all_kbs:
        databases = await discover_kb_databases(
            host=host, port=port, user=user, password=password
        )
        if not databases:
            print("No ragdb* databases found on the server.", flush=True)
            return 1
        print(f"Discovered {len(databases)} KB database(s): {', '.join(databases)}")
    else:
        databases = [args.database or settings.POSTGRES_DB]

    print(f"Target server: {user}@{host}:{port}  |  databases: {len(databases)}")

    all_ok = True
    for db in databases:
        try:
            ok = await migrate_database(
                host=host,
                port=port,
                user=user,
                password=password,
                database=db,
                maint_mem=args.maintenance_work_mem,
                parallel_workers=args.max_parallel_maintenance_workers,
            )
            all_ok = all_ok and ok
        except Exception as exc:  # noqa: BLE001 - one bad DB shouldn't abort the rest
            all_ok = False
            print(f"  [ERROR] {db}: {exc}", flush=True)

    print("\nDone." if all_ok else "\nDone WITH ERRORS.", flush=True)
    return 0 if all_ok else 1


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default=None, help="Postgres host (default: settings.POSTGRES_HOST)")
    p.add_argument("--port", type=int, default=None, help="Postgres port (default: settings.POSTGRES_PORT)")
    p.add_argument("--user", default=None, help="Postgres user (default: settings.POSTGRES_USER)")
    p.add_argument("--password", default=None, help="Postgres password (default: settings.POSTGRES_PASSWORD)")
    p.add_argument("--database", default=None, help="Single target database (default: settings.POSTGRES_DB)")
    p.add_argument("--all-kbs", action="store_true", help="Migrate every ragdb* database on the server")
    p.add_argument(
        "--maintenance-work-mem",
        default=None,
        help="Session maintenance_work_mem for the build, e.g. 256MB "
        "(omit to leave the server default; keep well under container memory)",
    )
    p.add_argument(
        "--max-parallel-maintenance-workers",
        type=int,
        default=None,
        help="Session max_parallel_maintenance_workers for the build. Use 0 to "
        "force a single-process HNSW build when the container's /dev/shm is too "
        "small for a parallel build (Docker default shm is 64MB).",
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
