from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "web" / "src" / "main.ts"


class OfflineOutboxUiTest(unittest.TestCase):
    def test_outbox_uses_indexeddb_and_client_request_id(self) -> None:
        source = MAIN.read_text(encoding="utf-8")

        self.assertIn("indexedDB.open(outboxDbName", source)
        self.assertIn("offline_outbox", source)
        self.assertIn("client_request_id", source)
        self.assertIn("uploadQueuedAttachment", source)
        self.assertIn('window.addEventListener("online"', source)

    def test_agent_forms_queue_offline_but_manual_forms_remain_online(self) -> None:
        source = MAIN.read_text(encoding="utf-8")

        self.assertIn('queueOfflineAgent("agent_text_meal"', source)
        self.assertIn('queueOfflineAgent("agent_chat"', source)
        self.assertIn('queueOfflineAgent("agent_label_scan"', source)
        self.assertIn('queueOfflineAgent("agent_recipe"', source)
        self.assertNotIn('queueOfflineAgent("manual_log"', source)
        self.assertNotIn('queueOfflineAgent("weight"', source)


if __name__ == "__main__":
    unittest.main()
