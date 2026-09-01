"""Fetch the datasets used by the lab from public, no-auth mirrors of popular
Kaggle datasets, cache them by SHA-256, and write data/raw/manifest.json.

The manifest is itself the evidence used later by `reproducible-ml` and
`data-catalog-entry`, so it records url, size and digest for every file.
"""
from __future__ import annotations
import hashlib, json, sys, urllib.request, zipfile, datetime, io

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from lib.paths import RAW, INTERIM
from lib.net import use_system_certs

use_system_certs()

SOURCES = {
    "telco_churn": {
        "kaggle": "blastchar/telco-customer-churn",
        "url": "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv",
        "file": "Telco-Customer-Churn.csv",
        "track": "T1 churn",
    },
    "titanic": {
        "kaggle": "c/titanic",
        "url": "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv",
        "file": "titanic.csv",
        "track": "T3 titanic",
    },
    "online_retail": {
        "kaggle": "vijayuv/onlineretail",
        "url": "https://archive.ics.uci.edu/static/public/352/online+retail.zip",
        "file": "online_retail.zip",
        "track": "T2 retail",
    },
    "fashion_mnist_train_images": {
        "kaggle": "zalando-research/fashionmnist",
        "url": "https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/data/fashion/train-images-idx3-ubyte.gz",
        "file": "train-images-idx3-ubyte.gz",
        "track": "T4 vision",
    },
    "fashion_mnist_train_labels": {
        "kaggle": "zalando-research/fashionmnist",
        "url": "https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/data/fashion/train-labels-idx1-ubyte.gz",
        "file": "train-labels-idx1-ubyte.gz",
        "track": "T4 vision",
    },
    "fashion_mnist_test_images": {
        "kaggle": "zalando-research/fashionmnist",
        "url": "https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/data/fashion/t10k-images-idx3-ubyte.gz",
        "file": "t10k-images-idx3-ubyte.gz",
        "track": "T4 vision",
    },
    "fashion_mnist_test_labels": {
        "kaggle": "zalando-research/fashionmnist",
        "url": "https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/data/fashion/t10k-labels-idx1-ubyte.gz",
        "file": "t10k-labels-idx1-ubyte.gz",
        "track": "T4 vision",
    },
}

UA = {"User-Agent": "Mozilla/5.0 (CMPE255 skills lab)"}


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, spec: dict) -> dict:
    dest = RAW / spec["file"]
    if not dest.exists():
        print(f"  downloading {name} <- {spec['url']}")
        req = urllib.request.Request(spec["url"], headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as out:
            out.write(r.read())
    else:
        print(f"  cached      {name}")
    return {
        "dataset": name,
        "kaggle_equivalent": spec["kaggle"],
        "source_url": spec["url"],
        "local_path": f"data/raw/{spec['file']}",
        "bytes": dest.stat().st_size,
        "sha256": sha256(dest),
        "track": spec["track"],
    }


def unpack_retail() -> dict | None:
    """UCI ships Online Retail as a zipped .xlsx; convert once to CSV for speed."""
    csv_path = INTERIM / "online_retail.csv"
    if csv_path.exists():
        print("  cached      online_retail.csv")
    else:
        import pandas as pd
        print("  converting  online_retail.zip -> csv (xlsx parse, ~1 min)")
        with zipfile.ZipFile(RAW / "online_retail.zip") as z:
            inner = z.namelist()[0]
            with z.open(inner) as fh:
                df = pd.read_excel(io.BytesIO(fh.read()), engine="openpyxl")
        df.to_csv(csv_path, index=False)
    import pandas as pd
    n = sum(1 for _ in open(csv_path, encoding="utf-8", errors="replace")) - 1
    return {"dataset": "online_retail_csv", "local_path": "data/interim/online_retail.csv",
            "rows": n, "sha256": sha256(csv_path), "bytes": csv_path.stat().st_size,
            "kaggle_equivalent": "vijayuv/onlineretail", "source_url": "derived from UCI 352 zip",
            "track": "T2 retail"}


def fetch_creditcard() -> dict:
    """Credit Card Fraud (mlg-ulb/creditcardfraud) via OpenML -- optional.

    If OpenML is unreachable the imbalanced-data demo falls back to a
    severely-downsampled churn target, which the artifact states explicitly.
    """
    out = RAW / "creditcard.csv"
    if out.exists():
        print("  cached      creditcard")
    else:
        try:
            from sklearn.datasets import fetch_openml
            print("  downloading creditcard <- OpenML (this can take a few minutes)")
            bunch = fetch_openml("creditcard", version=1, as_frame=True, parser="auto")
            df = bunch.frame
            df.to_csv(out, index=False)
        except Exception as e:  # network / OpenML outage
            print(f"  SKIP creditcard ({type(e).__name__}: {e}); imbalanced-data will use the churn fallback")
            return {"dataset": "creditcard", "status": "unavailable", "reason": f"{type(e).__name__}: {e}",
                    "kaggle_equivalent": "mlg-ulb/creditcardfraud"}
    return {"dataset": "creditcard", "kaggle_equivalent": "mlg-ulb/creditcardfraud",
            "source_url": "https://www.openml.org/d/1597 (mirror of the Kaggle set)",
            "local_path": "data/raw/creditcard.csv", "bytes": out.stat().st_size,
            "sha256": sha256(out), "track": "T1b imbalance", "status": "ok"}


def main() -> None:
    print("CRISP-DM phase 2 prerequisite: acquiring data")
    entries = [fetch(n, s) for n, s in SOURCES.items()]
    entries.append(unpack_retail())
    entries.append(fetch_creditcard())
    manifest = {
        "retrieved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": "Public no-auth mirrors of popular Kaggle datasets; digests pin the exact bytes used.",
        "datasets": [e for e in entries if e],
    }
    (RAW / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"\nwrote data/raw/manifest.json with {len(manifest['datasets'])} entries")


if __name__ == "__main__":
    main()
