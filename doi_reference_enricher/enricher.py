import json
import re
from urllib.parse import quote
from urllib.request import urlopen

SUPPORTED_FIELDS = {"title", "abstract", "keywords", "author", "citations"}


def _strip_wrapping(value: str) -> str:
    value = value.strip().strip(",").strip()
    if (value.startswith("{") and value.endswith("}")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1].strip()
    return value


def parse_bib(text: str):
    entries = []
    current = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("@") and "{" in stripped:
            head, _, rest = stripped.partition("{")
            entry_type = head[1:].strip()
            key = rest.split(",", 1)[0].strip()
            current = {"type": entry_type, "key": key, "fields": {}}
            continue

        if current is None:
            continue

        if stripped == "}":
            entries.append(current)
            current = None
            continue

        field_match = re.match(r"^([A-Za-z][\w-]*)\s*=\s*(.+?)(,)?$", stripped)
        if not field_match:
            continue

        field_name = field_match.group(1).lower()
        field_value = _strip_wrapping(field_match.group(2))
        current["fields"][field_name] = field_value

    if current is not None:
        entries.append(current)

    return entries


def dump_bib(entries) -> str:
    blocks = []
    for entry in entries:
        lines = [f"@{entry['type']}{{{entry['key']},"]
        for name, value in entry["fields"].items():
            lines.append(f"  {name} = {{{value}}},")
        lines.append("}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")


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
        doi = (entry["fields"].get("doi") or "").strip()
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
                entry["fields"][field] = value

    return entries


def enrich_bib(text: str, whitelist=None) -> str:
    entries = parse_bib(text)
    enrich_entries(entries, whitelist=whitelist)
    return dump_bib(entries)
