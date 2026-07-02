from __future__ import annotations

import unittest
from datetime import date

from health_monitor.agent import AgentDeps
from health_monitor.agent.tools import NutritionAgentTools
from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.lookup.labels import LabelTextExtraction, StaticLabelTextExtractor


class NutritionAgentToolsTest(unittest.TestCase):
    def make_deps(self) -> tuple[HealthMonitorService, AgentDeps, str]:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        _, current = service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="current label",
            nutrients_per_100g=Nutrients(315, 23, 2.6, 23.5, fiber_g=0, sodium_mg=620),
            source="label_scan",
            aliases=["queijo"],
        )
        service.create_food_with_version(
            household_id=household.id,
            name="Queijo Minas",
            brand=None,
            version_label="new label",
            nutrients_per_100g=Nutrients(300, 24, 2, 21, fiber_g=0, sodium_mg=590),
            source="label_scan",
            aliases=["queijo novo"],
            food_id=service.catalog.versions[current.id].food_id,
        )
        entry = service.log_diary_entry(
            person_id=person.id,
            logged_at_local="2026-07-01T10:00:00",
            food_version_id=current.id,
            quantity_g=100,
            source="manual",
        )
        deps = AgentDeps(
            service=service,
            person_id=person.id,
            household_id=household.id,
            today=date(2026, 7, 2),
            settings={"agent_runtime": "pydantic-ai", "model_name": "qwen3"},
            source_config={"openfoodfacts_enabled": False},
        )
        return service, deps, entry.id

    def test_read_tools_return_structured_grounded_payloads(self) -> None:
        service, deps, entry_id = self.make_deps()
        tools = NutritionAgentTools()

        day = tools.day_summary(deps, "2026-07-01")
        week = tools.week_summary(deps, "2026-07-01", "2026-07-07")
        trend = tools.weight_trend(deps)
        resolution = tools.food_resolution(deps, phrase="queijo")
        lookup = tools.food_lookup(deps, phrase="queijo")
        history = tools.food_version_history(deps, phrase="queijo")

        self.assertEqual(day["totals"]["calories_kcal"], 315)
        self.assertEqual(day["entries"][0]["entry_id"], entry_id)
        self.assertEqual(week["totals"]["calories_kcal"], 315)
        self.assertEqual(trend["entries"], [])
        self.assertEqual(resolution["food_name"], "Queijo Minas")
        self.assertEqual(resolution["reason"], "alias_default_version")
        self.assertEqual(lookup["candidates"][0]["source_name"], "Local library")
        self.assertEqual(lookup["candidates"][0]["food_name"], "Queijo Minas")
        self.assertEqual(history["food_name"], "Queijo Minas")
        self.assertEqual([item["label"] for item in history["versions"]], ["current label", "new label"])
        self.assertEqual(history["latest_entry"]["entry_id"], entry_id)
        self.assertEqual(service.catalog.foods[resolution["food_id"]].default_version_id, history["default_version_id"])

    def test_draft_tools_create_proposals_without_direct_diary_or_note_mutation(self) -> None:
        service, deps, _ = self.make_deps()
        tools = NutritionAgentTools()

        text_meal = tools.draft_text_meal_proposal(
            deps,
            logged_at_local="2026-07-02T10:00:00",
            text="50g queijo",
        )
        correction = tools.draft_diary_correction_proposal(
            deps,
            message="Change queijo on 2026-07-01 to 50g",
        )
        review = tools.draft_review_note_proposal(
            deps,
            message="Save review note: Social dinner was the main issue.",
        )

        self.assertEqual(text_meal["proposal_status"], "draft")
        self.assertEqual(text_meal["proposal_type"], "diary_entries")
        self.assertEqual(correction["proposal_type"], "diary_entry_update")
        self.assertEqual(review["proposal_type"], "review_note")
        self.assertEqual(service.day_summary(deps.person_id, date(2026, 7, 1)).totals.rounded(), Nutrients(315, 23, 2.6, 23.5, sodium_mg=620))
        self.assertEqual(service.day_summary(deps.person_id, date(2026, 7, 2)).totals, Nutrients())
        self.assertEqual(service.review_notes_for_person(deps.person_id), ())

    def test_ocr_tool_extracts_label_text_from_attachment(self) -> None:
        service = HealthMonitorService(
            label_text_extractor=StaticLabelTextExtractor(
                LabelTextExtraction(
                    text="Produto: Iogurte\nValor energetico: 120 kcal",
                    source="static_ocr",
                    confidence=0.88,
                    warnings=("glare",),
                )
            )
        )
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        attachment = service.create_attachment(
            household_id=household.id,
            person_id=person.id,
            object_type="nutrition_label_image",
            mime_type="image/png",
            content=b"fake-label-image",
            filename="label.png",
        )
        deps = AgentDeps(
            service=service,
            person_id=person.id,
            household_id=household.id,
            today=date(2026, 7, 2),
            settings={"agent_runtime": "pydantic-ai", "model_name": "qwen3"},
            source_config={"ocr_enabled": True},
        )

        result = NutritionAgentTools().extract_label_text_from_attachment(
            deps,
            attachment_id=attachment.id,
        )

        self.assertEqual(result["attachment_id"], attachment.id)
        self.assertEqual(result["source"], "static_ocr")
        self.assertEqual(result["confidence"], 0.88)
        self.assertIn("Valor energetico", result["text"])
        self.assertEqual(result["warnings"], ["glare"])


if __name__ == "__main__":
    unittest.main()
