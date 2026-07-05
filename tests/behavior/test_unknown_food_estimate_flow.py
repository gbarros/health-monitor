from __future__ import annotations

import unittest
from datetime import date

from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.lookup.estimates import NutritionEstimate, StaticFoodEstimator
from health_monitor.lookup.foods import FoodLookupCandidate, StaticFoodLookupProvider


class UnknownFoodEstimateFlowTest(unittest.TestCase):
    def test_external_lookup_is_used_before_model_estimate_for_unknown_text_meal(self) -> None:
        service = HealthMonitorService(
            food_lookup_provider=StaticFoodLookupProvider(
                [
                    FoodLookupCandidate(
                        source_type="external_database",
                        source_name="Open Food Facts",
                        source_id="kfc-double-crunch-br",
                        product_name="KFC Double Crunch combo",
                        brand="KFC Brasil",
                        barcode=None,
                        nutrients_per_100g=Nutrients(240, 12, 25, 10),
                        serving_size_g=None,
                        confidence=0.76,
                        warnings=("third-party nutrition data",),
                    )
                ]
            ),
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="Model KFC estimate",
                        nutrients_per_100g=Nutrients(300, 9, 30, 16),
                        source="fixture_model_estimate",
                        confidence=0.42,
                        notes="Model fallback should not be used when lookup returns a candidate.",
                    )
                }
            ),
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        proposal = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="20:00",
            items=[{"phrase": "kfc double crunch combo", "quantity_g": 300}],
            agent_settings={"external_lookup": True},
            source_text="300g KFC Double Crunch combo",
        )
        pending = proposal.payload["estimated_food_versions"][0]
        applied = service.confirm_proposal(proposal.id)
        resolution = service.resolve_food_reference(
            household_id=household.id,
            person_id=person.id,
            phrase="kfc double crunch combo",
        )
        stored_version = service.catalog.get_version(resolution.food_version_id)
        stored_food = service.catalog.foods[stored_version.food_id]

        self.assertEqual(proposal.proposal_type, "diary_entries_with_estimates")
        self.assertEqual(proposal.totals.rounded(), Nutrients(720, 36, 75, 30))
        self.assertEqual(pending["source"], "external_lookup")
        self.assertEqual(pending["source_name"], "Open Food Facts")
        self.assertEqual(proposal.evidence[0]["source_type"], "external_database")
        self.assertEqual(proposal.evidence[0]["resolution_reason"], "external_lookup")
        self.assertEqual(applied.status, "applied")
        self.assertEqual(resolution.food_version_id, proposal.entries[0].food_version_id)
        self.assertEqual(stored_food.brand, "KFC Brasil")
        self.assertEqual(stored_version.source, "external_lookup")
        tool_calls = service.agent_tool_calls_for_run(proposal.source_agent_run_id or "")
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [
                ("resolve_food_reference", "failed"),
                ("lookup_external_food", "completed"),
            ],
        )
        self.assertIn("kfc double crunch combo", tool_calls[0].input_summary)
        self.assertIn("KFC Double Crunch combo", tool_calls[1].output_summary)

    def test_controlled_research_lookup_is_used_before_model_estimate(self) -> None:
        service = HealthMonitorService(
            food_lookup_provider=StaticFoodLookupProvider([]),
            research_lookup_provider=StaticFoodLookupProvider(
                [
                    FoodLookupCandidate(
                        source_type="research_agent",
                        source_name="Controlled research agent",
                        source_id="research-kfc-double-crunch-br",
                        product_name="KFC Double Crunch combo Brazil",
                        brand="KFC Brasil",
                        barcode=None,
                        nutrients_per_100g=Nutrients(245, 12, 26, 10),
                        serving_size_g=None,
                        confidence=0.64,
                        warnings=("restaurant nutrition reference is approximate",),
                        source_url="https://example.test/kfc-double-crunch",
                        research_prompt="Research nutritional references for KFC Double Crunch combo in Brazil.",
                        source_claims=(
                            {
                                "source": "third-party menu reference",
                                "claim": "combo is treated as sandwich plus side and drink",
                            },
                        ),
                    )
                ]
            ),
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="Model KFC estimate",
                        nutrients_per_100g=Nutrients(300, 9, 30, 16),
                        source="fixture_model_estimate",
                        confidence=0.42,
                        notes="Model fallback should not be used when research returns a candidate.",
                    )
                }
            ),
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        proposal = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="20:00",
            items=[{"phrase": "kfc double crunch combo", "quantity_g": 300}],
            agent_settings={"external_lookup": True, "research_lookup": True},
            source_text="300g KFC Double Crunch combo",
        )
        pending = proposal.payload["estimated_food_versions"][0]
        tool_calls = service.agent_tool_calls_for_run(proposal.source_agent_run_id or "")

        self.assertEqual(proposal.proposal_type, "diary_entries_with_estimates")
        self.assertEqual(proposal.totals.rounded(), Nutrients(735, 36, 78, 30))
        self.assertEqual(pending["source"], "research_lookup")
        self.assertEqual(pending["source_type"], "research_agent")
        self.assertEqual(pending["research_prompt"], "Research nutritional references for KFC Double Crunch combo in Brazil.")
        self.assertEqual(pending["source_claims"][0]["source"], "third-party menu reference")
        self.assertEqual(proposal.evidence[0]["source_type"], "research_agent")
        self.assertEqual(proposal.evidence[0]["resolution_reason"], "research_lookup")
        self.assertEqual(proposal.evidence[0]["source_claims"][0]["claim"], "combo is treated as sandwich plus side and drink")
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [
                ("resolve_food_reference", "failed"),
                ("lookup_external_food", "completed"),
                ("lookup_research_food", "completed"),
            ],
        )

    def test_research_lookup_can_be_disabled_independently_from_model_estimate(self) -> None:
        service = HealthMonitorService(
            food_lookup_provider=StaticFoodLookupProvider([]),
            research_lookup_provider=StaticFoodLookupProvider(
                [
                    FoodLookupCandidate(
                        source_type="research_agent",
                        source_name="Controlled research agent",
                        source_id="research-kfc-double-crunch-br",
                        product_name="KFC Double Crunch combo",
                        brand="KFC Brasil",
                        barcode=None,
                        nutrients_per_100g=Nutrients(245, 12, 26, 10),
                        serving_size_g=None,
                        confidence=0.64,
                    )
                ]
            ),
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="KFC Double Crunch combo",
                        nutrients_per_100g=Nutrients(260, 11, 24, 13),
                        source="fixture_model_estimate",
                        confidence=0.42,
                        notes="Research lookup disabled for this run.",
                    )
                }
            ),
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        proposal = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="20:00",
            items=[{"phrase": "kfc double crunch combo", "quantity_g": 300}],
            agent_settings={"external_lookup": True, "research_lookup": False},
            source_text="300g KFC Double Crunch combo",
        )
        tool_calls = service.agent_tool_calls_for_run(proposal.source_agent_run_id or "")

        self.assertEqual(proposal.evidence[0]["source_type"], "model_estimate")
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [
                ("resolve_food_reference", "failed"),
                ("lookup_external_food", "completed"),
                ("estimate_food", "completed"),
            ],
        )

    def test_unknown_food_estimate_is_proposed_before_any_mutation(self) -> None:
        service = HealthMonitorService(
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="KFC Double Crunch combo",
                        nutrients_per_100g=Nutrients(
                            calories_kcal=260,
                            protein_g=11,
                            carbs_g=24,
                            fat_g=13,
                        ),
                        source="fixture_model_estimate",
                        confidence=0.42,
                        notes="Fixture estimate for a regional restaurant meal.",
                    )
                }
            )
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        proposal = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="20:00",
            items=[{"phrase": "kfc double crunch combo", "quantity_g": 300}],
            agent_settings={"model_profile": "ollama-local", "external_lookup": True},
            source_text="300g KFC Double Crunch combo",
        )

        self.assertEqual(proposal.proposal_type, "diary_entries_with_estimates")
        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.entries[0].quantity_g, 300)
        self.assertEqual(proposal.totals.rounded(), Nutrients(780, 33, 72, 39))
        self.assertEqual(proposal.evidence[0]["source_type"], "model_estimate")
        self.assertEqual(proposal.evidence[0]["confidence"], 0.42)
        self.assertEqual(service.day_summary(person.id, date(2026, 7, 1)).totals, Nutrients())
        self.assertIsNone(service.resolver.resolve_phrase("kfc double crunch combo", person_id=person.id))
        tool_calls = service.agent_tool_calls_for_run(proposal.source_agent_run_id or "")
        self.assertEqual(
            [(call.tool_name, call.status) for call in tool_calls],
            [
                ("resolve_food_reference", "failed"),
                ("lookup_external_food", "completed"),
                ("estimate_food", "completed"),
            ],
        )
        self.assertIn("KFC Double Crunch combo", tool_calls[-1].output_summary)

    def test_confirming_unknown_food_estimate_creates_reusable_food_and_diary_entry(self) -> None:
        service = HealthMonitorService(
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="KFC Double Crunch combo",
                        nutrients_per_100g=Nutrients(260, 11, 24, 13),
                        source="fixture_model_estimate",
                        confidence=0.42,
                        notes="Fixture estimate for a regional restaurant meal.",
                    )
                }
            )
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        proposal = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="20:00",
            items=[{"phrase": "kfc double crunch combo", "quantity_g": 300}],
            agent_settings={"external_lookup": True},
            source_text="300g KFC Double Crunch combo",
        )

        applied = service.confirm_proposal(proposal.id)
        summary = service.day_summary(person.id, date(2026, 7, 1))
        resolution = service.resolve_food_reference(
            household_id=household.id,
            person_id=person.id,
            phrase="kfc double crunch combo",
        )

        self.assertEqual(applied.status, "applied")
        self.assertEqual(len(applied.applied_record_ids), 3)
        self.assertEqual(summary.totals.rounded(), Nutrients(780, 33, 72, 39))
        self.assertEqual(summary.meals["dinner"][0].evidence_status, "estimated")
        self.assertEqual(summary.meals["dinner"][0].confidence, 0.42)
        self.assertEqual(resolution.food_version_id, proposal.entries[0].food_version_id)

    def test_rejecting_unknown_food_estimate_does_not_create_reusable_food(self) -> None:
        service = HealthMonitorService(
            estimator=StaticFoodEstimator(
                {
                    "kfc double crunch combo": NutritionEstimate(
                        phrase="kfc double crunch combo",
                        food_name="KFC Double Crunch combo",
                        nutrients_per_100g=Nutrients(260, 11, 24, 13),
                        source="fixture_model_estimate",
                        confidence=0.42,
                        notes="Fixture estimate for a regional restaurant meal.",
                    )
                }
            )
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        proposal = service.draft_structured_meal_proposal(
            person_id=person.id,
            day=date(2026, 7, 1),
            time_text="20:00",
            items=[{"phrase": "kfc double crunch combo", "quantity_g": 300}],
            agent_settings={"external_lookup": True},
            source_text="300g KFC Double Crunch combo",
        )

        service.reject_proposal(proposal.id)

        self.assertIsNone(service.resolver.resolve_phrase("kfc double crunch combo", person_id=person.id))
        self.assertEqual(service.day_summary(person.id, date(2026, 7, 1)).totals, Nutrients())


if __name__ == "__main__":
    unittest.main()
