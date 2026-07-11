from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"


class PwaAssetsTest(unittest.TestCase):
    def test_index_links_manifest_and_icon(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")

        self.assertIn('rel="manifest"', html)
        self.assertIn('href="/manifest.webmanifest"', html)
        self.assertIn('rel="icon"', html)
        self.assertIn('href="/app-icon.svg"', html)

    def test_manifest_declares_installable_app_shell(self) -> None:
        manifest = json.loads((WEB / "public" / "manifest.webmanifest").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "Health Monitor")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["id"], "/")
        self.assertEqual(manifest["start_url"], "/chat")
        self.assertEqual(manifest["icons"][0]["src"], "/app-icon.svg")
        self.assertIn("maskable", manifest["icons"][0]["purpose"])

    def test_service_worker_caches_shell_but_not_api_responses(self) -> None:
        worker = (WEB / "public" / "service-worker.js").read_text(encoding="utf-8")

        self.assertIn('"/manifest.webmanifest"', worker)
        self.assertIn('"/app-icon.svg"', worker)
        self.assertIn('url.pathname.startsWith("/api/")', worker)
        self.assertIn('caches.match("/")', worker)


if __name__ == "__main__":
    unittest.main()
