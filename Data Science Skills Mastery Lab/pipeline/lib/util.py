"""Small helpers shared by the phase modules."""
from __future__ import annotations
import contextlib, io, time


def capture(fn, *args, **kwargs) -> str:
    """Run a skill script function that prints, and return what it printed."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*args, **kwargs)
    return buf.getvalue()


@contextlib.contextmanager
def timer(store: dict, key: str):
    t0 = time.perf_counter()
    yield
    store[key] = time.perf_counter() - t0
