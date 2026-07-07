import argparse
import sys
from pathlib import Path

from .enricher import enrich_bib

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
    args = parser.parse_args(argv)

    _validate_bib_path(args.source, parser, "source")
    _validate_bib_path(args.destination, parser, "destination")

    selected = {field for flag, field in FLAG_TO_FIELD.items() if getattr(args, flag)}
    whitelist = selected if selected else None

    if args.source in (None, "-"):
        source_content = sys.stdin.read()
    else:
        source_content = Path(args.source).read_text(encoding="utf-8")

    enriched = enrich_bib(source_content, whitelist=whitelist)

    if args.destination in (None, "-"):
        sys.stdout.write(enriched)
    else:
        Path(args.destination).write_text(enriched, encoding="utf-8")


if __name__ == "__main__":
    main()
