import io
import sys
from pathlib import Path

import bibtexparser
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from doi_reference_enricher import cli

SOURCE_BIB = """@article{has_doi,
  title = {Original Title},
  doi = {10.1234/abc},
  year = {2020},
}

@article{no_doi,
  title = {Should Stay Same},
  year = {2021},
}
"""

SORT_BIB = """@article{zeta,
    title = {Zulu},
    author = {Zed Author},
    abstract = {Gamma abstract},
    keywords = {pear, orange},
    citations = {11},
}

@article{alpha,
    title = {Alpha},
    author = {Alice Author},
    abstract = {Alpha abstract},
    keywords = {apple, banana},
    citations = {2},
}

@article{beta,
    title = {Beta},
    author = {Bob Author},
    abstract = {Beta abstract},
    keywords = {kiwi, lemon},
    citations = {7},
}
"""


def _parse_entries(text: str):
    entries = {}
    for entry in bibtexparser.parse_string(text).entries:
        parsed = {field.key: field.value for field in entry.fields}
        parsed["ID"] = entry.key
        entries[entry.key] = parsed
    return entries


def _entry_order(text: str):
    return [entry.key for entry in bibtexparser.parse_string(text).entries]


def test_source_and_destination_paths(tmp_path, monkeypatch):
    source = tmp_path / "source.bib"
    dest = tmp_path / "dest.bib"
    source.write_text(SOURCE_BIB, encoding="utf-8")

    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_openalex_data", lambda _doi: {"title": "Enriched"})
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {})

    cli.main([str(source), str(dest)])

    entries = _parse_entries(dest.read_text(encoding="utf-8"))
    assert entries["has_doi"]["title"] == "Enriched"


def test_single_argument_uses_stdout_destination(tmp_path, monkeypatch):
    source = tmp_path / "source.bib"
    source.write_text(SOURCE_BIB, encoding="utf-8")

    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_openalex_data", lambda _doi: {"title": "Stdout Enriched"})
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {})

    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    cli.main([str(source)])

    entries = _parse_entries(stdout.getvalue())
    assert entries["has_doi"]["title"] == "Stdout Enriched"


def test_no_arguments_uses_stdin_and_stdout(monkeypatch):
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_openalex_data", lambda _doi: {"title": "From Stdin"})
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {})

    monkeypatch.setattr(sys, "stdin", io.StringIO(SOURCE_BIB))
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)

    cli.main([])

    entries = _parse_entries(stdout.getvalue())
    assert entries["has_doi"]["title"] == "From Stdin"


def test_rejects_non_bib_files():
    with pytest.raises(SystemExit):
        cli.main(["source.txt", "dest.bib"])
    with pytest.raises(SystemExit):
        cli.main(["source.bib", "dest.txt"])


def test_only_entries_with_doi_are_enriched(tmp_path, monkeypatch):
    source = tmp_path / "source.bib"
    dest = tmp_path / "dest.bib"
    source.write_text(SOURCE_BIB, encoding="utf-8")

    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_openalex_data", lambda _doi: {"title": "Only DOI"})
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {})

    cli.main([str(source), str(dest)])

    entries = _parse_entries(dest.read_text(encoding="utf-8"))
    assert entries["has_doi"]["title"] == "Only DOI"
    assert entries["no_doi"]["title"] == "Should Stay Same"


def test_openalex_then_crossref_fallback(tmp_path, monkeypatch):
    source = tmp_path / "source.bib"
    dest = tmp_path / "dest.bib"
    source.write_text(SOURCE_BIB, encoding="utf-8")

    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_openalex_data", lambda _doi: {"title": "OA Title"})
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {"abstract": "CR Abstract"})

    cli.main([str(source), str(dest)])

    entries = _parse_entries(dest.read_text(encoding="utf-8"))
    assert entries["has_doi"]["title"] == "OA Title"
    assert entries["has_doi"]["abstract"] == "CR Abstract"


def test_whitelist_flags_only_update_requested_fields(tmp_path, monkeypatch):
    source = tmp_path / "source.bib"
    dest = tmp_path / "dest.bib"
    source.write_text(SOURCE_BIB, encoding="utf-8")

    monkeypatch.setattr(
        "doi_reference_enricher.enricher.fetch_openalex_data",
        lambda _doi: {"title": "New Title", "abstract": "New Abstract", "author": "A. Author"},
    )
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {})

    cli.main(["--title", str(source), str(dest)])

    entries = _parse_entries(dest.read_text(encoding="utf-8"))
    assert entries["has_doi"]["title"] == "New Title"
    assert "abstract" not in entries["has_doi"]
    assert "author" not in entries["has_doi"]


def test_original_fields_are_preserved(tmp_path, monkeypatch):
    source = tmp_path / "source.bib"
    dest = tmp_path / "dest.bib"
    source.write_text(SOURCE_BIB, encoding="utf-8")

    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_openalex_data", lambda _doi: {"title": "Updated Title"})
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {})

    cli.main([str(source), str(dest)])

    entries = _parse_entries(dest.read_text(encoding="utf-8"))
    assert entries["has_doi"]["year"] == "2020"
    assert entries["has_doi"]["doi"] == "10.1234/abc"


def test_sort_by_field_defaults_to_asc(tmp_path, monkeypatch):
    source = tmp_path / "source.bib"
    dest = tmp_path / "dest.bib"
    source.write_text(SORT_BIB, encoding="utf-8")

    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_openalex_data", lambda _doi: {})
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {})

    cli.main(["--sort-by", "title", str(source), str(dest)])

    assert _entry_order(dest.read_text(encoding="utf-8")) == ["alpha", "beta", "zeta"]


def test_sort_by_field_with_explicit_asc(tmp_path, monkeypatch):
    source = tmp_path / "source.bib"
    dest = tmp_path / "dest.bib"
    source.write_text(SORT_BIB, encoding="utf-8")

    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_openalex_data", lambda _doi: {})
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {})

    cli.main(["--sort-by", "title", "asc", str(source), str(dest)])

    assert _entry_order(dest.read_text(encoding="utf-8")) == ["alpha", "beta", "zeta"]


def test_sort_by_field_with_desc(tmp_path, monkeypatch):
    source = tmp_path / "source.bib"
    dest = tmp_path / "dest.bib"
    source.write_text(SORT_BIB, encoding="utf-8")

    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_openalex_data", lambda _doi: {})
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {})

    cli.main(["--sort-by", "title", "desc", str(source), str(dest)])

    assert _entry_order(dest.read_text(encoding="utf-8")) == ["zeta", "beta", "alpha"]


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("title", ["alpha", "beta", "zeta"]),
        ("abstract", ["alpha", "beta", "zeta"]),
        ("keywords", ["alpha", "beta", "zeta"]),
        ("author", ["alpha", "beta", "zeta"]),
        ("citations", ["alpha", "beta", "zeta"]),
    ],
)
def test_sort_by_supported_fields(tmp_path, monkeypatch, field, expected):
    source = tmp_path / "source.bib"
    dest = tmp_path / "dest.bib"
    source.write_text(SORT_BIB, encoding="utf-8")

    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_openalex_data", lambda _doi: {})
    monkeypatch.setattr("doi_reference_enricher.enricher.fetch_crossref_data", lambda _doi: {})

    cli.main(["--sort-by", field, str(source), str(dest)])

    assert _entry_order(dest.read_text(encoding="utf-8")) == expected
