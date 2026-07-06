from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

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

        structured_meal = tools.draft_meal_proposal(
            deps,
            day="2026-07-02",
            time="12:30",
            meal_type="lunch",
            items=[{"phrase": "queijo", "quantity_g": 40}],
            source_text="agent extracted 40g queijo",
        )
        correction = tools.draft_diary_correction_proposal(
            deps,
            day="2026-07-01",
            phrase="queijo",
            quantity_g=50,
            source_text="agent extracted correction",
        )
        review = tools.draft_review_note_proposal(
            deps,
            body="Social dinner was the main issue.",
            title="Review note",
            source_text="agent extracted review note",
        )

        self.assertEqual(structured_meal["proposal_type"], "diary_entries")
        self.assertEqual(structured_meal["entries"][0]["meal_type"], "lunch")
        self.assertEqual(structured_meal["entries"][0]["quantity_g"], 40)
        self.assertEqual(correction["proposal_type"], "diary_entry_update")
        self.assertEqual(review["proposal_type"], "review_note")
        self.assertEqual(service.day_summary(deps.person_id, date(2026, 7, 1)).totals.rounded(), Nutrients(315, 23, 2.6, 23.5, sodium_mg=620))
        self.assertEqual(service.day_summary(deps.person_id, date(2026, 7, 2)).totals, Nutrients())
        self.assertEqual(service.review_notes_for_person(deps.person_id), ())

    def test_draft_meal_accepts_model_estimates_without_food_lookup(self) -> None:
        service = HealthMonitorService()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        deps = AgentDeps(
            service=service,
            person_id=person.id,
            household_id=household.id,
            today=date(2026, 7, 2),
            settings={"agent_runtime": "pydantic-ai", "external_lookup": True},
            source_config={},
        )

        result = NutritionAgentTools().draft_meal_proposal(
            deps,
            day="2026-07-02",
            meal_type="lunch",
            items=[
                {
                    "phrase": "arroz",
                    "quantity_g": 74,
                    "nutrients_per_100g": {
                        "calories_kcal": 130,
                        "protein_g": 2.7,
                        "carbs_g": 28,
                        "fat_g": 0.3,
                    },
                    "confidence": 0.6,
                },
                {
                    "phrase": "feijão preto",
                    "quantity_g": 139,
                    "nutrients_per_100g": {
                        "calories_kcal": 77,
                        "protein_g": 4.5,
                        "carbs_g": 14,
                        "fat_g": 0.5,
                    },
                    "confidence": 0.55,
                },
            ],
            source_text="Almoço: 74g arroz, 139g feijão preto",
        )

        proposal = service.get_proposal(result["proposal_id"])
        tool_names = [
            call.tool_name
            for call in service.agent_tool_calls_for_run(proposal.source_agent_run_id or "")
        ]
        self.assertEqual(proposal.proposal_type, "diary_entries_with_estimates")
        self.assertEqual([entry.quantity_g for entry in proposal.entries], [74, 139])
        self.assertEqual([evidence["source_type"] for evidence in proposal.evidence], ["model_item_estimate", "model_item_estimate"])
        self.assertEqual(tool_names, ["use_model_item_estimate", "use_model_item_estimate"])

    def test_onboarding_tool_creates_profile_setup_proposal(self) -> None:
        service = HealthMonitorService()
        deps = AgentDeps(
            service=service,
            person_id="onboarding:session-1",
            household_id="",
            today=date(2026, 7, 2),
            settings={"agent_runtime": "pydantic-ai", "model_name": "qwen3"},
            source_config={},
        )

        result = NutritionAgentTools().draft_onboarding_proposal(
            deps,
            session_id="session-1",
            household_name="Casa",
            person={"name": "Gabriel", "timezone": "America/Sao_Paulo"},
            targets={"calories_kcal": 2000, "protein_g": 150},
            notes="Setup inicial",
            source_text="conversa de onboarding",
        )

        proposal = service.get_proposal(result["proposal_id"])
        self.assertEqual(result["proposal_status"], "draft")
        self.assertEqual(result["proposal_type"], "profile_setup")
        self.assertEqual(proposal.payload["person"]["name"], "Gabriel")
        self.assertEqual(proposal.payload["targets"]["calories_kcal"], 2000)

    def test_onboarding_tool_rejects_placeholder_household_id(self) -> None:
        service = HealthMonitorService()
        deps = AgentDeps(
            service=service,
            person_id="onboarding:session-1",
            household_id="",
            today=date(2026, 7, 2),
            settings={"agent_runtime": "pydantic-ai", "model_name": "qwen3"},
            source_config={},
        )

        with self.assertRaisesRegex(ValueError, "placeholder onboarding household ids"):
            NutritionAgentTools().draft_onboarding_proposal(
                deps,
                session_id="session-1",
                household_id="onboarding-household:session-1",
                person={"name": "Gabriel", "timezone": "America/Sao_Paulo"},
                targets={"calories_kcal": 2000, "protein_g": 150},
            )

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

    def test_runtime_does_not_register_raw_text_meal_parser_tool(self) -> None:
        runtime = Path("src/health_monitor/agent/runtime.py").read_text()

        self.assertNotIn("@agent.tool\n        async def draft_text_meal_proposal", runtime)
        self.assertIn("async def draft_meal_proposal", runtime)


if __name__ == "__main__":
    unittest.main()
