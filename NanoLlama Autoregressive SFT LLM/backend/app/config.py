from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts"
DB_PATH = ARTIFACT_DIR / "nanollama.sqlite3"
METRIC_DIR = ARTIFACT_DIR / "metrics"
CHECKPOINT_DIR = ARTIFACT_DIR / "checkpoints"
DEFAULT_DATASET = DATA_DIR / "sample_chat.jsonl"

for directory in (ARTIFACT_DIR, METRIC_DIR, CHECKPOINT_DIR):
    directory.mkdir(parents=True, exist_ok=True)
