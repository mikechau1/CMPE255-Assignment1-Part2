from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "Mall_Customers.csv"
ARTIFACT_DIR = ROOT / "artifacts"
SEED = 42
DEFAULT_MAX_EXPERIMENTS = 18
