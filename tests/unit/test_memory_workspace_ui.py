from __future__ import annotations

import unittest

from tests.unit.frontend_helpers import read_web_file


class MemoryWorkspaceUiTest(unittest.TestCase):
    def test_memory_is_an_editable_living_workspace(self) -> None:
        app = read_web_file("App.tsx")
        api = read_web_file("api.ts")
        proposal_card = read_web_file("components/ProposalCard.tsx")

        self.assertIn("MemoryWorkspace", app)
        self.assertIn("Memória viva", app)
        self.assertIn("Nova memória", app)
        self.assertIn("Salvar memória", app)
        self.assertIn("Confirmar exclusão", app)
        self.assertIn("createMemoryNote", api)
        self.assertIn("updateMemoryNote", api)
        self.assertIn('method: "PATCH"', api)
        self.assertIn("proposal-memory-preview", proposal_card)
        self.assertIn('if (status === "applied") return "Aplicada"', proposal_card)


if __name__ == "__main__":
    unittest.main()
