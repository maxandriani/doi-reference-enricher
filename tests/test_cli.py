import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


class CliTests(unittest.TestCase):
    def test_source_and_destination_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.bib"
            dest = Path(tmpdir) / "dest.bib"
            source.write_text(SOURCE_BIB, encoding="utf-8")

            with patch("doi_reference_enricher.enricher.fetch_openalex_data", return_value={"title": "Enriched"}), patch(
                "doi_reference_enricher.enricher.fetch_crossref_data", return_value={}
            ):
                cli.main([str(source), str(dest)])

            output = dest.read_text(encoding="utf-8")
            self.assertIn("title = {Enriched}", output)

    def test_single_argument_uses_stdout_destination(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.bib"
            source.write_text(SOURCE_BIB, encoding="utf-8")

            with patch("doi_reference_enricher.enricher.fetch_openalex_data", return_value={"title": "Stdout Enriched"}), patch(
                "doi_reference_enricher.enricher.fetch_crossref_data", return_value={}
            ), patch("sys.stdout", new_callable=io.StringIO) as stdout:
                cli.main([str(source)])

            self.assertIn("title = {Stdout Enriched}", stdout.getvalue())

    def test_no_arguments_uses_stdin_and_stdout(self):
        with patch("doi_reference_enricher.enricher.fetch_openalex_data", return_value={"title": "From Stdin"}), patch(
            "doi_reference_enricher.enricher.fetch_crossref_data", return_value={}
        ), patch("sys.stdin", new=io.StringIO(SOURCE_BIB)), patch("sys.stdout", new_callable=io.StringIO) as stdout:
            cli.main([])

        self.assertIn("title = {From Stdin}", stdout.getvalue())

    def test_rejects_non_bib_files(self):
        with self.assertRaises(SystemExit):
            cli.main(["source.txt", "dest.bib"])
        with self.assertRaises(SystemExit):
            cli.main(["source.bib", "dest.txt"])

    def test_only_entries_with_doi_are_enriched(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.bib"
            dest = Path(tmpdir) / "dest.bib"
            source.write_text(SOURCE_BIB, encoding="utf-8")

            with patch("doi_reference_enricher.enricher.fetch_openalex_data", return_value={"title": "Only DOI"}), patch(
                "doi_reference_enricher.enricher.fetch_crossref_data", return_value={}
            ):
                cli.main([str(source), str(dest)])

            output = dest.read_text(encoding="utf-8")
            self.assertIn("@article{has_doi", output)
            self.assertIn("title = {Only DOI}", output)
            self.assertIn("@article{no_doi", output)
            self.assertIn("title = {Should Stay Same}", output)

    def test_openalex_then_crossref_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.bib"
            dest = Path(tmpdir) / "dest.bib"
            source.write_text(SOURCE_BIB, encoding="utf-8")

            with patch("doi_reference_enricher.enricher.fetch_openalex_data", return_value={"title": "OA Title"}), patch(
                "doi_reference_enricher.enricher.fetch_crossref_data", return_value={"abstract": "CR Abstract"}
            ):
                cli.main([str(source), str(dest)])

            output = dest.read_text(encoding="utf-8")
            self.assertIn("title = {OA Title}", output)
            self.assertIn("abstract = {CR Abstract}", output)

    def test_whitelist_flags_only_update_requested_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.bib"
            dest = Path(tmpdir) / "dest.bib"
            source.write_text(SOURCE_BIB, encoding="utf-8")

            with patch(
                "doi_reference_enricher.enricher.fetch_openalex_data",
                return_value={"title": "New Title", "abstract": "New Abstract", "author": "A. Author"},
            ), patch("doi_reference_enricher.enricher.fetch_crossref_data", return_value={}):
                cli.main(["--title", str(source), str(dest)])

            output = dest.read_text(encoding="utf-8")
            self.assertIn("title = {New Title}", output)
            self.assertNotIn("abstract = {New Abstract}", output)
            self.assertNotIn("author = {A. Author}", output)

    def test_original_fields_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.bib"
            dest = Path(tmpdir) / "dest.bib"
            source.write_text(SOURCE_BIB, encoding="utf-8")

            with patch("doi_reference_enricher.enricher.fetch_openalex_data", return_value={"title": "Updated Title"}), patch(
                "doi_reference_enricher.enricher.fetch_crossref_data", return_value={}
            ):
                cli.main([str(source), str(dest)])

            output = dest.read_text(encoding="utf-8")
            self.assertIn("year = {2020}", output)
            self.assertIn("doi = {10.1234/abc}", output)


if __name__ == "__main__":
    unittest.main()
