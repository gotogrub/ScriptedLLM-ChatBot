import math
import re

from aho_bot.schemas import KnowledgeHit


TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)


def tokenize(text):
    return [item.lower().replace("ё", "е") for item in TOKEN_RE.findall(text)]


class RagRetriever:
    def __init__(self, documents):
        self.documents = documents
        self.index = []
        for document in documents:
            text_parts = [document.get("title", ""), document.get("text", "")]
            text_parts.extend(document.get("facts", []))
            text = " ".join(text_parts)
            tokens = set(tokenize(text))
            self.index.append((document, tokens))

    def retrieve(self, query, categories=None, limit=4):
        query_tokens = set(tokenize(query))
        category_set = set(categories or [])
        scored = []
        for document, tokens in self.index:
            overlap = query_tokens.intersection(tokens)
            score = len(overlap) / math.sqrt(max(len(tokens), 1))
            if category_set and document.get("category") in category_set:
                score += 0.45
            if score > 0:
                scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        results = []
        for score, document in scored[:limit]:
            results.append(
                KnowledgeHit(
                    id=document.get("id", ""),
                    title=document.get("title", ""),
                    category=document.get("category", ""),
                    text=document.get("text", ""),
                    score=round(score, 4),
                    source=document.get("source", ""),
                )
            )
        return results

