"""Append-only-per-run JSONL evidence. A failed write propagates to the caller."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from .policy import Config


class Evidence:
    def __init__(self, path: str | Path, config: Config):
        # Exclusive creation prevents accidentally destroying prior evidence.
        self.file = Path(path).open("x", encoding="utf-8")
        self.sequence = 0
        self.common = {"run_id": uuid.uuid4().hex, "config_sha256": config.identity,
                       "seed": config.seed, "rule_id": "rule-1", "fault": config.fault}

    def emit(self, event: str, **fields) -> None:
        self.sequence += 1
        record = {**self.common, "seq": self.sequence, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                  "event": event, **fields}
        self.file.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        self.file.flush()

    def close(self) -> None:
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
