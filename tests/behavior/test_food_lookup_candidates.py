from __future__ import annotations

import unittest

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.lookup.foods import FoodLookupCandidate, StaticFoodLookupProvider


class FoodLookupCandidatesTest(unittest.TestCase):
    def test_local_barcode_association_ranks_above_external_lookup(self) -> None:
        provider = StaticFoodLookupProvider(
            [
                FoodLookupCandidate(
                    source_type="external_database",
                    source_name="Open Food Facts",
                    source_id="7891000000000",
                    product_name="External Yogurt",
                    brand="External",
                    barcode="7891000000000",
                    nutrients_per_100g=Nutrients(70, 6, 8, 1),
                    serving_size_g=170,
                    confidence=0.8,
                    warnings=("user-contributed data",),
                )
            ]
        )
        service = HealthMonitorService(food_lookup_provider=provider)
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, version = service.create_food_with_version(
            household_id=household.id,
            name="Iogurte Batavo Protein",
            brand="Batavo",
            version_label="label scan",
            nutrients_per_100g=Nutrients(70.59, 8.82, 5.88, 1.18),
            source="label_scan",
            aliases=["iogurte batavo"],
            barcode="7891000000000",
            serving_size_g=170,
        )

        candidates = service.lookup_food_candidates(
            household_id=household.id,
            person_id=person.id,
            barcode="7891000000000",
        )

        self.assertEqual(candidates[0].source_type, "local_barcode")
        self.assertEqual(candidates[0].food_version_id, version.id)
        self.assertEqual(candidates[1].source_name, "Open Food Facts")

    def test_external_lookup_candidate_can_be_saved_through_proposal(self) -> None:
        provider = StaticFoodLookupProvider(
            [
                FoodLookupCandidate(
                    source_type="external_database",
                    source_name="Open Food Facts",
                    source_id="7891000000000",
                    product_name="Iogurte Batavo Protein",
                    brand="Batavo",
                    barcode="7891000000000",
                    nutrients_per_100g=Nutrients(70.59, 8.82, 5.88, 1.18),
                    serving_size_g=170,
                    confidence=0.82,
                    warnings=("user-contributed data",),
                )
            ]
        )
        service = HealthMonitorService(food_lookup_provider=provider)
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        candidate = service.lookup_food_candidates(
            household_id=household.id,
            person_id=person.id,
            barcode="7891000000000",
        )[0]

        proposal = service.propose_food_lookup_candidate(
            household_id=household.id,
            person_id=person.id,
            candidate_id=candidate.id,
        )
        applied = service.confirm_proposal(proposal.id)
        resolved = service.resolve_food_reference(
            household_id=household.id,
            person_id=person.id,
            barcode="7891000000000",
        )

        self.assertEqual(proposal.proposal_type, "food_version_from_lookup")
        self.assertEqual(proposal.payload["source_name"], "Open Food Facts")
        self.assertEqual(proposal.payload["confidence"], 0.82)
        self.assertIn("user-contributed data", proposal.evidence[0]["warnings"])
        self.assertEqual(applied.status, "applied")
        self.assertEqual(resolved.food_version_id, applied.applied_record_ids[1])
        self.assertEqual(service.catalog.get_version(resolved.food_version_id).confidence, 0.82)


if __name__ == "__main__":
    unittest.main()
