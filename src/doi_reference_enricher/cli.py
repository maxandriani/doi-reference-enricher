import argparse
import sys
from pathlib import Path

from .enricher import SORT_ORDERS, SUPPORTED_FIELDS, enrich_bib

FLAG_TO_FIELD = {
    "title": "title",
    "abstract": "abstract",
    "keywords": "keywords",
    "keyworkds": "keywords",
    "author": "author",
    "citations": "citations",
}


def _validate_bib_path(path: str, parser: argparse.ArgumentParser, role: str):
    if path in (None, "-"):
        return
    if Path(path).suffix.lower() != ".bib":
        parser.error(f"{role} must be a .bib file")


def _parse_sort_by(sort_by, parser: argparse.ArgumentParser):
    if not sort_by:
        return None, "asc"

    if len(sort_by) > 2:
        parser.error("--sort-by accepts: <field> [asc|desc]")

    field = sort_by[0].strip().lower()
    if field not in SUPPORTED_FIELDS:
        parser.error(f"--sort-by field must be one of: {', '.join(sorted(SUPPORTED_FIELDS))}")

    order = "asc"
    if len(sort_by) == 2:
        order = sort_by[1].strip().lower()
        if order not in SORT_ORDERS:
            parser.error("--sort-by order must be 'asc' or 'desc'")

    return field, order


def _extract_sort_by_args(argv):
    extracted = None
    passthrough = []
    i = 0

    while i < len(argv):
        token = argv[i]
        if token != "--sort-by":
            passthrough.append(token)
            i += 1
            continue

        if extracted is not None:
            passthrough.append(token)
            i += 1
            continue

        i += 1
        values = []
        if i < len(argv):
            values.append(argv[i])
            i += 1

        if i < len(argv) and argv[i].strip().lower() in SORT_ORDERS:
            values.append(argv[i])
            i += 1

        extracted = values

    return passthrough, extracted


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="doi-enricher")
    parser.add_argument("source", nargs="?", default=None)
    parser.add_argument("destination", nargs="?", default=None)
    parser.add_argument("--title", action="store_true")
    parser.add_argument("--abstract", action="store_true")
    parser.add_argument("--keywords", action="store_true")
    parser.add_argument("--keyworkds", action="store_true")
    parser.add_argument("--author", action="store_true")
    parser.add_argument("--citations", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    original_argv = list(sys.argv[1:] if argv is None else argv)
    filtered_argv, sort_by_values = _extract_sort_by_args(original_argv)
    args = parser.parse_args(filtered_argv)

    _validate_bib_path(args.source, parser, "source")
    _validate_bib_path(args.destination, parser, "destination")
    sort_by, sort_order = _parse_sort_by(sort_by_values, parser)

    selected = {field for flag, field in FLAG_TO_FIELD.items() if getattr(args, flag)}
    whitelist = selected if selected else None

    if args.source in (None, "-"):
        source_content = sys.stdin.read()
    else:
        source_content = Path(args.source).read_text(encoding="utf-8")

    enriched = enrich_bib(source_content, whitelist=whitelist, sort_by=sort_by, sort_order=sort_order)

    if args.destination in (None, "-"):
        sys.stdout.write(enriched)
    else:
        Path(args.destination).write_text(enriched, encoding="utf-8")


if __name__ == "__main__":
    main()
