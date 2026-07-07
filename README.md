# doi-reference-enricher

`doi-reference-enricher` provides a CLI tool, `doi-enricher`, to enrich BibTeX entries using DOI metadata.

## Features

- Enriches only entries that contain a `doi` field.
- Uses OpenAlex first, then falls back to Crossref when a field is missing.
- Preserves original entry data and only updates enrichment fields.
- Supports field whitelisting with CLI flags.
- Works with file input/output and stdin/stdout modes.

## Installation

```bash
pip install .
```

For local development with tests:

```bash
pip install -e '.[test]'
```

## Usage

```bash
doi-enricher [OPTIONS] [SOURCE] [DESTINATION]
```

### I/O modes

- `doi-enricher ./source.bib ./dest.bib`
  - Read from source file and write to destination file.
- `doi-enricher ./source.bib`
  - Read from source file and write to stdout.
- `doi-enricher`
  - Read from stdin and write to stdout.

`SOURCE` and `DESTINATION` paths must end with `.bib`.

### Whitelist options

If no whitelist option is provided, all supported enrichment fields are updated.

Supported options:

- `--title`
- `--abstract`
- `--keywords`
- `--keyworkds` (alias for `--keywords`)
- `--author`
- `--citations`

Examples:

```bash
# only title and author
doi-enricher --title --author ./source.bib ./dest.bib

# stdin -> stdout, only abstract and citations
cat ./source.bib | doi-enricher --abstract --citations
```

## Development

Run tests:

```bash
pytest -q
```

Coverage is configured with `pytest-cov` in `pyproject.toml` and runs automatically with pytest.
