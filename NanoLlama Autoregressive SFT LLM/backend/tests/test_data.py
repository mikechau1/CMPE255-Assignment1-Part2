import json
from pathlib import Path

from app.ml.data import load_records


def test_sample_dataset_is_valid():
    records, report = load_records(Path("data/sample_chat.jsonl"))
    assert report.valid_records == len(records) > 0
    assert report.validation_records >= 0
    assert report.fingerprint


def test_prompt_completion_is_supported(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps({"prompt": "hi", "completion": "hello"}) + "\n", encoding="utf-8")
    records, report = load_records(path)
    assert report.valid_records == 1
    assert records[0]["messages"][1]["role"] == "assistant"
