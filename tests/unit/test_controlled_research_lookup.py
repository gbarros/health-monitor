from __future__ import annotations

import unittest

from health_monitor.domain.nutrients import Nutrients
from health_monitor.lookup.foods import (
    ControlledResearchLookupProvider,
    FoodLookupCandidate,
    StaticFoodLookupProvider,
)


class ControlledResearchLookupProviderTest(unittest.TestCase):
    def make_provider(self, *, enabled: bool) -> ControlledResearchLookupProvider:
        return ControlledResearchLookupProvider(
            StaticFoodLookupProvider(
                [
                    FoodLookupCandidate(
                        source_type="research_agent",
                        source_name="Controlled research",
                        source_id="research:kfc-double-crunch-br",
                        product_name="KFC Double Crunch combo Brazil estimate",
                        brand="KFC",
                        barcode=None,
                        nutrients_per_100g=Nutrients(250, 13, 20, 12, sodium_mg=510),
                        serving_size_g=520,
                        confidence=0.52,
                        research_prompt="Search nutritional references for KFC Double Crunch combo in Brazil.",
                        source_claims=(
                            {"claim": "regional menu estimate", "source": "fixture"},
                        ),
                    )
                ]
            ),
            enabled=enabled,
        )

    def test_disabled_provider_returns_no_candidates(self) -> None:
        self.assertEqual(self.make_provider(enabled=False).lookup(phrase="KFC Double Crunch"), [])

    def test_enabled_provider_returns_normalized_research_candidate(self) -> None:
        candidates = self.make_provider(enabled=True).lookup(phrase="KFC Double Crunch")

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source_type, "research_agent")
        self.assertEqual(candidates[0].source_id, "research:kfc-double-crunch-br")
        self.assertIn("Brazil", candidates[0].research_prompt or "")
        self.assertEqual(candidates[0].source_claims[0]["source"], "fixture")


if __name__ == "__main__":
    unittest.main()
