import re


DANGEROUS_PATTERNS = [
    r"твой\s+нов(?:ый|ого|ому|ым|ом)?\s+системн(?:ый|ого|ому|ым|ом)\s+промпт\s*:?[^\n.!?]*",
    r"\b(?:new|updated)\s+system\s+prompt\s*:?[^\n.!?]*",
    r"\bsystem\s+prompt\s*:?[^\n.!?]*",
    r"\bdeveloper\s+prompt\b",
    r"\bprompt\s+injection\b",
    r"\bjailbreak\b",
    r"\bignore\s+(?:all|previous)\s+instructions[^\n.!?]*",
    r"\brole\s*:\s*(?:system|developer|assistant)\b",
    r"системн(?:ый|ого|ому|ым|ом)\s+промпт",
    r"игнорируй\s+(?:все|предыдущие|старые)\s+инструкц",
    r"забудь\s+(?:все|предыдущие|старые)\s+инструкц",
    r"<\s*/?\s*(?:system|developer|assistant|user)\s*>",
]

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SPECIAL_RE = re.compile(r"[<>{}\[\]`$^~|\\]+")


def sanitize_for_llm(value):
    text = str(value or "")
    text = CONTROL_RE.sub(" ", text)
    for pattern in DANGEROUS_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = SPECIAL_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
