from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_TS = ROOT / "web" / "src" / "main.ts"


class ProfileSwitchUiTest(unittest.TestCase):
    def test_topbar_renders_profile_switcher(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('renderProfileSwitcher("topbar")', source)
        self.assertIn('class="profile-select"', source)
        self.assertIn("state.people", source)

    def test_profile_switch_clears_person_scoped_transient_state(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn("function clearPersonScopedState()", source)
        self.assertIn("clearPersonScopedState();", source)
        self.assertIn("state.proposal = null", source)
        self.assertIn("state.chatResponse = null", source)
        self.assertIn("state.lookupCandidates = []", source)
        self.assertIn("state.lastDeletedEntry = null", source)

    def test_all_profile_select_controls_bind_to_switch_handler(self) -> None:
        source = MAIN_TS.read_text(encoding="utf-8")

        self.assertIn('querySelectorAll<HTMLSelectElement>(".profile-select")', source)
        self.assertIn("onProfileSelect", source)


if __name__ == "__main__":
    unittest.main()
