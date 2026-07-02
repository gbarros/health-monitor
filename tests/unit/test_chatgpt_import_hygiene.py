from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ChatGPTImportHygieneTest(unittest.TestCase):
    def test_raw_exports_and_private_snippets_are_ignored(self) -> None:
        source = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("/imports/", source)
        self.assertIn("/data/imports/", source)
        self.assertIn("/private/", source)
        self.assertIn("/Health - *.html", source)

    def test_supported_import_commands_are_documented(self) -> None:
        source = (ROOT / "docs" / "chatgpt-history-import.md").read_text(encoding="utf-8")

        self.assertIn("python scripts/inspect_chatgpt_log.py <export.html>", source)
        self.assertIn(
            "python scripts/extract_chatgpt_log_signals.py <export.html> --out <fixtures.json>",
            source,
        )
        self.assertIn("--start-date", source)
        self.assertIn("--end-date", source)


if __name__ == "__main__":
    unittest.main()
