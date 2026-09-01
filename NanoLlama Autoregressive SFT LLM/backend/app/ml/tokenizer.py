from __future__ import annotations

import json
from pathlib import Path


class ByteTokenizer:
    """Deterministic byte tokenizer with explicit chat/control tokens.

    It avoids a heavyweight tokenizer build step while preserving every UTF-8
    input byte. The interface is intentionally compatible with a future BPE.
    """

    PAD, BOS, EOS, USER, ASSISTANT, SYSTEM = range(256, 262)
    vocab_size = 262

    def encode(self, text: str, add_bos: bool = False, add_eos: bool = False) -> list[int]:
        ids = [b for b in text.encode("utf-8", errors="replace")]
        if add_bos:
            ids.insert(0, self.BOS)
        if add_eos:
            ids.append(self.EOS)
        return ids

    def decode(self, ids: list[int]) -> str:
        raw = bytes(i for i in ids if 0 <= i < 256)
        return raw.decode("utf-8", errors="replace")

    def encode_messages(self, messages: list[dict[str, str]], max_length: int) -> tuple[list[int], list[int]]:
        ids: list[int] = [self.BOS]
        labels: list[int] = [-100]
        role_tokens = {"user": self.USER, "assistant": self.ASSISTANT, "system": self.SYSTEM}
        for message in messages:
            role = message["role"].lower()
            content = message["content"].strip()
            role_id = role_tokens.get(role, self.USER)
            ids.append(role_id)
            labels.append(-100)
            content_ids = self.encode(content)
            ids.extend(content_ids)
            labels.extend(content_ids if role == "assistant" else [-100] * len(content_ids))
            ids.append(self.EOS)
            labels.append(self.EOS if role == "assistant" else -100)
        ids, labels = ids[:max_length], labels[:max_length]
        if len(ids) < 2:
            ids += [self.EOS]
            labels += [self.EOS]
        return ids, labels

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({"type": "byte", "vocab_size": self.vocab_size}, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ByteTokenizer":
        if path.exists():
            json.loads(path.read_text(encoding="utf-8"))
        return cls()
