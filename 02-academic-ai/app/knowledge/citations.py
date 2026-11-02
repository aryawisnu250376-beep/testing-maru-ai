from __future__ import annotations

import re

_PAGE_REFERENCE = re.compile(r"\b(?:halaman|hlm\.?|page|p\.)\s*(?:ke[- ]?)?(\d+)\b", re.IGNORECASE)


def page_references(text: str) -> set[int]:
    """Find explicit Indonesian/English page-number claims in generated prose."""
    return {int(match.group(1)) for match in _PAGE_REFERENCE.finditer(text)}


_INLINE_CITATION = re.compile(r"\[([^\[\]]+),\s*h\.\s*(\d+)\]", re.IGNORECASE)


def inline_citations(text: str) -> set[tuple[str, int]]:
    """Find [document, h.N] inline citation markers in generated prose."""
    return {
        (match.group(1).strip(), int(match.group(2))) for match in _INLINE_CITATION.finditer(text)
    }


def _cited_doc_pages(sources: list[dict[str, object]]) -> set[tuple[str, int]]:
    pairs: set[tuple[str, int]] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        document, page = source.get("document"), source.get("page")
        if (
            isinstance(document, str)
            and document.strip()
            and isinstance(page, int)
            and not isinstance(page, bool)
        ):
            pairs.add((document.strip(), page))
    return pairs


def inline_citations_have_sources(text: str, sources: list[dict[str, object]]) -> bool:
    """Every [document, h.N] marker must point at a validated source entry."""
    return inline_citations(text).issubset(_cited_doc_pages(sources))


def page_claims_have_sources(text: str, sources: list[dict[str, object]]) -> bool:
    cited_pages = {
        int(source["page"])
        for source in sources
        if isinstance(source, dict)
        and isinstance(source.get("page"), int)
        and not isinstance(source.get("page"), bool)
    }
    return page_references(text).issubset(cited_pages)
