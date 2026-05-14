from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


@dataclass
class KnowledgeHit:
    id: str
    title: str
    category: str
    text: str
    score: float
    source: str


@dataclass
class ValidationOutcome:
    valid: bool
    violations: list[str] = field(default_factory=list)


@dataclass
class ChatResult:
    user_id: str
    answer: str
    state: str
    intent: str
    request_type: str | None = None
    draft: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    quick_replies: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    ticket: dict[str, Any] | None = None
    validated: bool = True
    violations: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResult:
    text: str
    trace: dict[str, Any] = field(default_factory=dict)


def to_plain(value):
    if is_dataclass(value):
        return to_plain(asdict(value))
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    return value
