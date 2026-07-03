from __future__ import annotations

import json
import unittest

from tests.unit.frontend_helpers import read_public_file, read_web_file


class OfflineOutboxUiTest(unittest.TestCase):
    def test_phase_one_keeps_pwa_install_basics_without_service_worker_runtime(self) -> None:
        manifest = json.loads(read_public_file("manifest.webmanifest"))
        main = read_web_file("main.tsx")

        self.assertEqual(manifest["display"], "standalone")
        self.assertIn("theme_color", manifest)
        self.assertGreaterEqual(len(manifest["icons"]), 1)
        self.assertNotIn("serviceWorker.register", main)


if __name__ == "__main__":
    unittest.main()
