from __future__ import annotations

import json
import unittest

from tests.unit.frontend_helpers import read_public_file, read_web_file


class OfflineOutboxUiTest(unittest.TestCase):
    def test_pwa_install_basics(self) -> None:
        manifest = json.loads(read_public_file("manifest.webmanifest"))

        self.assertEqual(manifest["display"], "standalone")
        self.assertIn("theme_color", manifest)
        self.assertGreaterEqual(len(manifest["icons"]), 1)

    def test_service_worker_registers_in_prod_and_never_caches_api(self) -> None:
        main = read_web_file("main.tsx")
        service_worker = read_public_file("service-worker.js")

        self.assertIn("serviceWorker.register", main)
        self.assertIn("import.meta.env.PROD", main)
        self.assertIn('startsWith("/api/")', service_worker)

    def test_outbox_module_is_a_pure_persisted_queue(self) -> None:
        outbox = read_web_file("outbox.ts")

        self.assertIn("health-monitor.outbox.v1", outbox)
        self.assertIn("export function enqueue", outbox)
        self.assertIn("export function removeById", outbox)
        self.assertIn("export function forPerson", outbox)
        self.assertIn("export function readOutbox", outbox)
        self.assertIn("export function writeOutbox", outbox)


if __name__ == "__main__":
    unittest.main()
