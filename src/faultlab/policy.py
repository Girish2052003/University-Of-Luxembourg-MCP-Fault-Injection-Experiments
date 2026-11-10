"""Strict configuration and request-order-based fault selection."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _text(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 10000


@dataclass(frozen=True)
class Config:
    enabled: bool
    seed: int
    tool: str
    fault: str
    probability: float
    occurrence: int | None
    parameters: dict

    @classmethod
    def from_dict(cls, value: dict) -> "Config":
        if not isinstance(value, dict):
            raise ValueError("configuration must be a JSON object")
        fields = {"enabled", "seed", "tool", "fault", "probability", "occurrence", "parameters"}
        if set(value) - fields:
            raise ValueError("unknown configuration keys: " + ", ".join(sorted(set(value) - fields)))
        v = {"enabled": True, "seed": 42, "probability": 1.0, "occurrence": None, **value}
        if not {"tool", "fault", "parameters"} <= v.keys():
            raise ValueError("tool, fault and parameters are required")
        if type(v["enabled"]) is not bool or type(v["seed"]) is not int:
            raise ValueError("enabled must be boolean and seed must be integer")
        if not _text(v["tool"]) or len(v["tool"]) > 128:
            raise ValueError("tool must be a non-empty name of at most128 characters")
        p = v["probability"]
        if type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("probability must be a finite number between0 and1")
        n = v["occurrence"]
        if n is not None and (type(n) is not int or n < 1):
            raise ValueError("occurrence must be null or a positive integer")
        f, args = v["fault"], v["parameters"]
        keys = {"latency": {"delay_ms"}, "error": {"message"}, "semantic": {"old", "new"},
                "request": {"argument", "old", "new"}, "omission": {"old"}}
        if not isinstance(f, str) or f not in keys or not isinstance(args, dict) or set(args) != keys[f]:
            raise ValueError("unknown fault or incorrect parameter keys")
        if f == "latency":
            ms = args["delay_ms"]
            if type(ms) not in (int, float) or not math.isfinite(ms) or not 0 <= ms <= 60000:
                raise ValueError("delay_ms must be finite and between0 and60000")
        elif not all(_text(x) for x in args.values()):
            raise ValueError("fault parameters must be non-empty strings")
        if f in {"semantic", "request"} and args["old"] == args["new"]:
            raise ValueError("old and new must differ")
        return cls(**{**v, "probability": float(p), "parameters": dict(args)})

    @property
    def identity(self) -> str:
        return digest(asdict(self))


@dataclass(frozen=True)
class Decision:
    ordinal: int
    selected: bool
    draw: float


class Policy:
    def __init__(self, config: Config):
        self.config = config
        self.ordinal = 0

    def decide(self, tool: str) -> Decision | None:
        c = self.config
        if tool != c.tool:
            return None
        self.ordinal += 1
        h = digest([c.identity, c.seed, c.tool, self.ordinal])
        # Top53 bits produce exactly representable values strictly below1.
        draw = (int(h[:16], 16) >> 11) / (1 << 53)
        selected = c.enabled and (c.occurrence is None or self.ordinal == c.occurrence) and draw < c.probability
        return Decision(self.ordinal, selected, draw)
