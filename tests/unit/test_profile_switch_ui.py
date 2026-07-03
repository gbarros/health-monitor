from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class ProfileSwitchUiTest(unittest.TestCase):
    def test_header_uses_avatar_chip_profile_switcher(self) -> None:
        app = read_web_file("App.tsx")
        styles = read_web_file("styles.css")

        self.assertIn("function PersonChips", app)
        self.assertIn('aria-label="Selecionar perfil"', app)
        self.assertIn("localStorage.setItem(STORAGE_KEYS.personId", app)
        self.assertIn('className={person.id === activePersonId ? "person-chip is-active" : "person-chip"}', app)
        self.assertIn(".person-chips", styles)
        self.assertIn(".person-chip.is-active", styles)

    def test_profile_switch_changes_person_scoped_queries_and_resets_transient_mode(self) -> None:
        app = read_web_file("App.tsx")

        self.assertIn("const changePerson", app)
        self.assertIn('setActiveMode("general_chat")', app)
        self.assertIn("queryKeys.people(householdId)", app)
        self.assertIn("queryKeys.proposals(selectedPersonId)", app)
        self.assertIn("queryKeys.chatHistory(selectedPersonId)", app)


if __name__ == "__main__":
    unittest.main()
