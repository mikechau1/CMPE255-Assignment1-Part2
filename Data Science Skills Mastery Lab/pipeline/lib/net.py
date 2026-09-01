"""Network setup.

This machine's certifi bundle rejects several of the dataset hosts with
CERTIFICATE_VERIFY_FAILED (expired root). `truststore` routes verification
through the Windows certificate store instead, which trusts them, so we keep
full certificate verification rather than disabling it.
"""
from __future__ import annotations

_injected = False


def use_system_certs() -> bool:
    global _injected
    if _injected:
        return True
    try:
        import truststore
        truststore.inject_into_ssl()
        _injected = True
    except ImportError:
        pass
    return _injected
