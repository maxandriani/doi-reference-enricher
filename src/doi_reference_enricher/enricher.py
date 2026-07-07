import json
import re
from urllib.parse import quote
from urllib.request import urlopen

import bibtexparser

SUPPORTED_FIELDS = {"title", "abstract", "keywords", "author", "citations"}


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
        doi = (entry.get("doi") or "").strip()
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
                entry[field] = value

    return entries


def enrich_bib(text: str, whitelist=None) -> str:
    bib_database = bibtexparser.loads(text)
    enrich_entries(bib_database.entries, whitelist=whitelist)
    return bibtexparser.dumps(bib_database)
