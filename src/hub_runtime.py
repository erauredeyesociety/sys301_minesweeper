"""The async runtime, wrapped so main.py never imports the hub-only `runloop` directly.

Part of the hub-facing layer. **Only `hub_*.py` modules may import the LEGO API** ([ADR-0004],
enforced by ./scripts/check-docs.py) -- and `runloop` counts, so the one place it is named is here.

`runloop` is the SPIKE 3 cooperative scheduler: `runloop.run(coro)` starts the loop on the program's
`main()`, and `await runloop.sleep_ms(ms)` is how a coroutine yields inside it. main.py drives its whole
state machine through these two calls, so wrapping them keeps main.py pure enough to import on the host
while its hub call sites stay [UNVERIFIED]. THE RULE holds: a hub-only name lives only in a hub_*.py file.
"""
try:
    import runloop
except ImportError:              # host: this module imports, but run()/sleep_ms() are never reached
    runloop = None


def run(coro):
    """Start the cooperative loop on `coro`. Hub-only -- raises on the host, where there is no loop."""
    if runloop is None:
        raise RuntimeError("hub_runtime.run is hub-only: no runloop on the host")
    return runloop.run(coro)


async def sleep_ms(ms):
    """Yield for `ms` inside the loop. A no-op on the host (never reached in a real run)."""
    if runloop is None:
        return
    await runloop.sleep_ms(ms)
