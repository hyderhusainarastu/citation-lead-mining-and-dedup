"""Offline smoke test: re-run the bundled synthetic example and compare to the committed output."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], check=True,
                          capture_output=True, text=True)


class ExampleTest(unittest.TestCase):
    def test_pipeline_matches_committed_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            leads = Path(tmp) / "leads"
            out = Path(tmp) / "consolidated"
            for slug, theme in (("synthetic-source-a", "indexing-history"),
                                ("synthetic-source-b", "retrieval-order")):
                run(ROOT / "scripts/mine_leads.py", "--mode", "both",
                    "--source-slug", slug,
                    "--input", EX / "source_text" / f"{slug}.txt",
                    "--ideas-input", EX / "ideas" / f"{slug}.ideas.json",
                    "--out-dir", leads, "--theme", theme)
            run(ROOT / "scripts/consolidate_leads.py",
                "--leads-dir", leads, "--output-dir", out)
            for name in ("reference_leads.csv", "hypothesis_leads.csv", "shortlist.md"):
                got = (out / name).read_text(encoding="utf-8")
                want = (EX / "consolidated" / name).read_text(encoding="utf-8")
                self.assertEqual(got, want, name)

    def test_help(self):
        for script in ("mine_leads.py", "consolidate_leads.py"):
            self.assertIn("usage", run(ROOT / "scripts" / script, "--help").stdout.lower())


if __name__ == "__main__":
    unittest.main()
