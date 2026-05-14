from dataclasses import dataclass, field
from pathlib import Path
import re


@dataclass
class CatalogItem:
    name: str
    category: str
    supplier: str
    url: str
    group: str
    patterns: list[str] = field(default_factory=list)


@dataclass
class CatalogGroup:
    key: str
    label: str
    supplier: str
    items: list[CatalogItem] = field(default_factory=list)


class CatalogClassifier:
    def __init__(self, path):
        self.path = Path(path)
        self.groups = []
        self.items = []
        self.load()

    def load(self):
        current = None
        if not self.path.exists():
            return
        for raw_line in self.path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split("|", 2)]
            head = parts[0]
            if head.startswith("category ") and len(parts) >= 3:
                key = head.split(" ", 1)[1].strip()
                current = CatalogGroup(key=key, label=parts[1], supplier=parts[2])
                self.groups.append(current)
                continue
            if head.startswith("item ") and current and len(parts) >= 3:
                patterns = [item.strip().replace("ё", "е") for item in parts[2].split(",") if item.strip()]
                item = CatalogItem(
                    name=head.split(" ", 1)[1].strip(),
                    category=current.label,
                    supplier=current.supplier,
                    url=parts[1],
                    group=current.key,
                    patterns=patterns,
                )
                current.items.append(item)
                self.items.append(item)

    def classify(self, text):
        value = text.replace("ё", "е")
        found = []
        for item in self.items:
            position = self.match_position(value, item.patterns)
            if position is None:
                continue
            found.append(
                {
                    "name": item.name,
                    "category": item.category,
                    "supplier": item.supplier,
                    "url": item.url,
                    "catalog_group": item.group,
                    "quantity": None,
                    "_pos": position,
                }
            )
        return sorted(found, key=lambda item: item["_pos"])

    def match_position(self, value, patterns):
        matches = []
        normalized = value.lower()
        for pattern in patterns:
            if pattern.startswith("rx:"):
                try:
                    match = re.search(pattern[3:], value, re.IGNORECASE)
                except re.error:
                    match = None
                if match:
                    matches.append(match.start())
                continue
            simple = pattern.lower()
            position = normalized.find(simple)
            if position >= 0:
                matches.append(position)
        if not matches:
            return None
        return min(matches)

    def documents(self):
        documents = []
        for group in self.groups:
            names = ", ".join(item.name for item in group.items)
            links = ", ".join(item.url for item in group.items[:6])
            documents.append(
                {
                    "id": f"catalog_{group.key}",
                    "title": f"Каталог {group.supplier}: {group.label}",
                    "category": "procurement",
                    "source": f"catalog.reg:{group.key}",
                    "text": f"{group.label} закупаются через {group.supplier}: {names}. Для демо используются ссылки {links}.",
                    "facts": [
                        f"{group.label}: {names}",
                        f"Поставщик: {group.supplier}",
                    ],
                    "forbidden_claims": [],
                }
            )
        return documents
