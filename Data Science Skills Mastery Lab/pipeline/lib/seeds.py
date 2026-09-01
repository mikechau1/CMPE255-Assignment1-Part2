"""Single seeding entry point -- evidence for the `reproducible-ml` skill.

Every phase module calls `set_global_seed()` before doing anything stochastic, so
reruns of phases 3-5 reproduce identical metrics.
"""
from __future__ import annotations
import os, random, hashlib, platform, sys, subprocess, json

SEED = 20255255  # CMPE255, fall 2025


def set_global_seed(seed: int = SEED) -> int:
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(False)  # CPU convs have no deterministic kernel need here
    except ImportError:
        pass
    return seed


def env_fingerprint() -> dict:
    """Versions + platform, hashed into a single id so two runs can be compared."""
    pkgs = {}
    for mod in ("numpy", "pandas", "sklearn", "scipy", "torch", "transformers", "xgboost", "lightgbm"):
        try:
            pkgs[mod] = __import__(mod).__version__
        except Exception:
            pkgs[mod] = "not installed"
    fp = {
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()}",
        "seed": SEED,
        "packages": pkgs,
    }
    fp["fingerprint_sha256"] = hashlib.sha256(
        json.dumps(fp, sort_keys=True).encode()
    ).hexdigest()[:16]
    return fp
