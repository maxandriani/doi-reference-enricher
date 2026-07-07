import json
import logging
import re
from copy import deepcopy
from contextlib import contextmanager
from urllib.parse import quote
from urllib.request import urlopen

import bibtexparser
import bibtexparser.middlewares as m
from bibtexparser.library import Library
from bibtexparser.model import Entry, Field

SUPPORTED_FIELDS = {"title", "abstract", "keywords", "author", "citations"}
SORT_ORDERS = {"asc", "desc"}


@contextmanager
def _suppress_unknown_block_logs():
    logger = logging.getLogger("bibtexparser.middlewares.middleware")
    previous = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(previous)


if not hasattr(m, "SortBlocksMiddleware"):
    class SortBlocksMiddleware(m.BlockMiddleware):
        def __init__(self, key):
            super().__init__()
            self._key = key

        def transform(self, library: Library) -> Library:
            sorted_entries = sorted(library.entries, key=self._key)
            sorted_iter = iter(sorted_entries)
            blocks = []
            for block in library.blocks:
                if isinstance(block, Entry):
                    blocks.append(deepcopy(next(sorted_iter)))
                else:
                    blocks.append(deepcopy(block))
            return Library(blocks=blocks)

    m.SortBlocksMiddleware = SortBlocksMiddleware


class _DescendingKey:
    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value > other.value

    def __eq__(self, other):
        return self.value == other.value


def _entry_get(entry, field: str) -> str:
    raw = entry.get(field)
    if raw is None:
        return ""
    value = getattr(raw, "value", raw)
    return str(value).strip()


def _entry_set(entry, field: str, value: str):
    if hasattr(entry, "set_field"):
        entry.set_field(Field(key=field, value=value))
        return
    entry[field] = value


def _text_key(value: str):
    normalized = value.casefold()
    return normalized == "", normalized


def _citations_key(value: str):
    match = re.search(r"-?\d+", value)
    if not match:
        return 1, 0
    return 0, int(match.group(0))


def sort_by_title(entry):
    return _text_key(_entry_get(entry, "title"))


def sort_by_abstract(entry):
    return _text_key(_entry_get(entry, "abstract"))


def sort_by_keywords(entry):
    return _text_key(_entry_get(entry, "keywords"))


def sort_by_author(entry):
    return _text_key(_entry_get(entry, "author"))


def sort_by_citations(entry):
    return _citations_key(_entry_get(entry, "citations"))


SORT_FUNCTIONS = {
    "title": sort_by_title,
    "abstract": sort_by_abstract,
    "keywords": sort_by_keywords,
    "author": sort_by_author,
    "citations": sort_by_citations,
}


def _sort_function(field: str, order: str):
    base = SORT_FUNCTIONS[field]
    if order == "asc":
        return base

    def _desc(entry):
        return _DescendingKey(base(entry))

    return _desc


def _doi_to_openalex_url(doi: str) -> str:
    return f"https://api.openalex.org/works/https://doi.org/{quote(doi, safe='')}"


def _doi_to_crossref_url(doi: str) -> str:
    return f"https://api.crossref.org/works/{quote(doi, safe='')}"


def _get_json(url: str):
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _openalex_abstract(index):
    if not isinstance(index, dict):
        return ""
    words = []
    for word, positions in index.items():
        for position in positions:
            words.append((position, word))
    words.sort(key=lambda t: t[0])
    return " ".join(word for _, word in words)


def fetch_openalex_data(doi: str):
    try:
        payload = _get_json(_doi_to_openalex_url(doi))
    except Exception:
        return {}

    authorships = payload.get("authorships") or []
    authors = []
    for item in authorships:
        author = (item.get("author") or {}).get("display_name")
        if author:
            authors.append(author)

    keywords = []
    for item in payload.get("keywords") or []:
        name = item.get("display_name")
        if name:
            keywords.append(name)

    result = {
        "title": payload.get("display_name") or payload.get("title") or "",
        "abstract": _openalex_abstract(payload.get("abstract_inverted_index")),
        "keywords": ", ".join(keywords),
        "author": " and ".join(authors),
    }
    cited = payload.get("cited_by_count")
    if cited is not None:
        result["citations"] = str(cited)
    return result


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def fetch_crossref_data(doi: str):
    try:
        payload = _get_json(_doi_to_crossref_url(doi)).get("message", {})
    except Exception:
        return {}

    author_list = []
    for author in payload.get("author") or []:
        given = author.get("given", "").strip()
        family = author.get("family", "").strip()
        full_name = " ".join(v for v in [given, family] if v)
        if full_name:
            author_list.append(full_name)

    subjects = payload.get("subject") or []
    title_list = payload.get("title") or []
    abstract = payload.get("abstract") or ""

    result = {
        "title": title_list[0] if title_list else "",
        "abstract": _strip_tags(abstract).strip(),
        "keywords": ", ".join(subjects),
        "author": " and ".join(author_list),
    }
    cited = payload.get("is-referenced-by-count")
    if cited is not None:
        result["citations"] = str(cited)
    return result


def enrich_entries(entries, whitelist=None):
    selected_fields = set(whitelist or SUPPORTED_FIELDS)

    for entry in entries:
        doi = _entry_get(entry, "doi")
        if not doi:
            continue

        openalex = fetch_openalex_data(doi)
        crossref = {}

        for field in selected_fields:
            value = openalex.get(field)
            if not value:
                if not crossref:
                    crossref = fetch_crossref_data(doi)
                value = crossref.get(field)
            if value:
                _entry_set(entry, field, value)

    return entries


def enrich_bib(text: str, whitelist=None, sort_by=None, sort_order="asc") -> str:
    with _suppress_unknown_block_logs():
        bib_database = bibtexparser.parse_string(text)
    enrich_entries(bib_database.entries, whitelist=whitelist)

    prepend_middleware = None
    if sort_by:
        sort_function = _sort_function(sort_by, sort_order)
        prepend_middleware = [m.SortBlocksMiddleware(key=sort_function)]

    with _suppress_unknown_block_logs():
        return bibtexparser.write_string(bib_database, prepend_middleware=prepend_middleware)
