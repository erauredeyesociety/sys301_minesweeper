#!/usr/bin/env python3
"""Per-KB ingest CLI (deployment tooling; build plan ZD item 4).

Drives the EXISTING v1 ingest flow (app.ingestion.ingest_directory — the
content-hash ON CONFLICT dedupe path, app/database.py) against ONE knowledge
base's dedicated logical database, resolved through the frozen
``ConfigManager.get_kb_connection(name)`` interface. It deliberately never
uses ``PostgresKB.ingest`` (no dedupe).

Runs INSIDE the api container (the corpus is mounted same-path :ro there and
the compose env supplies POSTGRES_PASSWORD / embedding settings):

    docker compose run --rm --no-deps \
        -v "$PWD/scripts:/src/scripts:ro" \
        api python /src/scripts/ingest_kb.py --kb <name>

The KB's ``ingest_dirs`` come from config/config.yaml (knowledge_bases
stanza); ``--kb primary`` is refused — primary == ragdb is owned by the v1
ingest flow. Exit code 0 on success; prints a one-line JSON summary
(kb/database/documents/chunks) on stdout as its last line.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Script lives outside the app package; make /src (PACKAGE_ROOT) importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config_manager import ConfigManager  # noqa: E402
from app.database import upsert_meta  # noqa: E402
from app.embeddings import EmbeddingService  # noqa: E402
from app.ingestion import ingest_directory  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ingest_kb")

# Match the registry's per-KB engine budget (build plan R3).
POOL_SIZE = 2
MAX_OVERFLOW = 3


async def ingest_kb(kb_name: str, rebuild: bool = False) -> dict:
    cm = ConfigManager()
    kbs = cm.get_knowledge_bases() or {}
    if kb_name not in kbs:
        raise SystemExit(
            f"ERROR: '{kb_name}' is not a configured knowledge base "
            f"(configured: {', '.join(sorted(kbs)) or 'none'})"
        )
    if kb_name == "primary":
        raise SystemExit(
            "ERROR: 'primary' (== ragdb) is owned by the v1 ingest flow "
            "(rag ingest); refusing per-KB ingest into it."
        )

    kb_cfg = kbs[kb_name] or {}
    ingest_dirs = kb_cfg.get("ingest_dirs") or []
    if not ingest_dirs:
        raise SystemExit(f"ERROR: KB '{kb_name}' has no ingest_dirs configured.")

    # Per-KB file-type isolation (9C #2). Honor THIS KB's own `extensions` /
    # `exclude` when set; leave them None otherwise so ingest_directory falls
    # back to the GLOBAL ingestion.extensions / ingestion.exclude (behavior
    # preserved for KBs that declare neither). This is what makes a docs-KB
    # (`extensions: [md, pdf]`) and a code-KB (`extensions: [py, js, ...]`)
    # file-type isolated rather than merely pointed at different trees.
    kb_extensions = kb_cfg.get("extensions")
    kb_exclude = kb_cfg.get("exclude")

    # B16 per-KB chunk-budget override: a code KB wants larger code chunks, a docs
    # KB wants 256-tok prose. When a key is absent, pass None so ingest_file falls
    # back to the GLOBAL settings.CHUNK_SIZE / ingestion.code_chunk_chars (behavior
    # preserved byte-identically for KBs that declare neither).
    kb_chunk_size = kb_cfg.get("chunk_size")
    kb_code_chunk_chars = kb_cfg.get("code_chunk_chars")

    dsn = cm.get_kb_connection(kb_name)["dsn"]
    db_name = dsn.rsplit("/", 1)[-1]
    engine = create_async_engine(dsn, echo=False, pool_size=POOL_SIZE, max_overflow=MAX_OVERFLOW)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    embed = EmbeddingService()  # backend/model/dimension from container env

    try:
        # Schema must already exist (KB registry initializes it at api
        # startup); fail with an actionable message rather than a traceback.
        async with engine.connect() as conn:
            ok = await conn.scalar(text("SELECT to_regclass('public.documents')"))
            if ok is None:
                raise SystemExit(
                    f"ERROR: database '{db_name}' has no schema yet — start the "
                    "stack once (the KB registry provisions it at api startup) "
                    "before ingesting."
                )

        # --rebuild: destructively wipe THIS KB's own rows before re-ingesting so
        # unchanged content is re-chunked from source (the content-hash dedupe
        # would otherwise skip it, leaving 0.4.x line-spans null on old corpus).
        # The engine is bound to this KB's own dsn (get_kb_connection above), so
        # these DELETEs can only ever touch this single KB's database — never
        # another KB. Chunk.document_id is ON DELETE CASCADE, but delete chunks
        # first for explicitness/order. Raw text() to match the counts below.
        if rebuild:
            # Safety 1: this per-KB wipe must NEVER hit the primary corpus, even
            # if a KB is misconfigured with `database: ragdb`.
            if db_name == "ragdb":
                raise SystemExit(
                    f"ERROR: refusing --rebuild for KB '{kb_name}' — it resolves to "
                    "'ragdb' (the primary corpus), which is owned by the v1 ingest "
                    "flow. Fix the KB's `database:` in config."
                )
            # Safety 2 (refuse-if-empty; defense in depth — rechunk.sh checks too):
            # never wipe an index when there is nothing on disk to rebuild from.
            have_source = any(
                Path(d).is_dir() and any(f.is_file() for f in Path(d).rglob("*"))
                for d in ingest_dirs
            )
            if not have_source:
                raise SystemExit(
                    f"ERROR: KB '{kb_name}' --rebuild refused — none of its "
                    f"ingest_dirs contain files on disk ({ingest_dirs}); refusing "
                    "to wipe an index with nothing to rebuild it from."
                )
            logger.warning(
                "KB %s: --rebuild — wiping documents+chunks in %s before re-ingest",
                kb_name,
                db_name,
            )
            async with engine.begin() as conn:
                pre_docs = await conn.scalar(text("SELECT count(*) FROM documents"))
                pre_chunks = await conn.scalar(text("SELECT count(*) FROM chunks"))
                await conn.execute(text("DELETE FROM chunks"))
                await conn.execute(text("DELETE FROM documents"))
            logger.warning(
                "KB %s: wiped %s document(s) / %s chunk(s) from %s",
                kb_name,
                int(pre_docs or 0),
                int(pre_chunks or 0),
                db_name,
            )

        total_docs = 0
        async with session_factory() as session:
            for d in ingest_dirs:
                logger.info("KB %s: ingesting %s -> %s", kb_name, d, db_name)
                docs = await ingest_directory(
                    d, session, embed, extensions=kb_extensions, exclude=kb_exclude,
                    chunk_size=kb_chunk_size, code_chunk_chars=kb_code_chunk_chars,
                )
                total_docs += len(docs)
            # Meta row (dimension/model/indexed_at) — same contract the async
            # job API writes; the registry's per-KB dimension guard reads it.
            await upsert_meta(session, docs_root=str(Path(ingest_dirs[0]).resolve()))

        async with engine.connect() as conn:
            doc_count = await conn.scalar(text("SELECT count(*) FROM documents"))
            chunk_count = await conn.scalar(text("SELECT count(*) FROM chunks"))
    finally:
        await engine.dispose()

    return {
        "kb": kb_name,
        "database": db_name,
        "rebuilt": bool(rebuild),
        "ingested_this_run": total_docs,
        "documents": int(doc_count or 0),
        "chunks": int(chunk_count or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kb", required=True, help="knowledge base name (config/config.yaml)")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help=(
            "DESTRUCTIVE: delete THIS KB's chunks+documents (its own DB only) "
            "before ingesting, so unchanged content is re-chunked from source "
            "and line-spans backfill. Default off (plain content-hash dedupe)."
        ),
    )
    args = parser.parse_args()
    summary = asyncio.run(ingest_kb(args.kb, rebuild=args.rebuild))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
