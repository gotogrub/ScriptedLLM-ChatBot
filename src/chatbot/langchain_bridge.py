def make_document(text, metadata):
    try:
        from langchain_core.documents import Document
    except Exception:
        return {"page_content": text, "metadata": metadata}
    return Document(page_content=text, metadata=metadata)


def document_text(document):
    if isinstance(document, dict):
        return document.get("page_content", "")
    return getattr(document, "page_content", "")
