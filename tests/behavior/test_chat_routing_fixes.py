from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from health_monitor.api.http_api import HttpApi
from health_monitor.application.service import HealthMonitorService, ModelUnavailableError
from health_monitor.domain.nutrients import Nutrients
from health_monitor.lookup.estimates import NutritionEstimate, StaticFoodEstimator
from health_monitor.persistence.sqlite_state import SQLiteStateRepository

TODAY = date(2026, 7, 3)


def build_service(**kwargs: object) -> tuple[HealthMonitorService, str, str]:
    estimator = StaticFoodEstimator(
        {
            phrase: NutritionEstimate(
                phrase=phrase,
                food_name=phrase.title(),
                nutrients_per_100g=nutrients,
                source="fixture_model_estimate",
                confidence=0.6,
                notes=None,
            )
            for phrase, nutrients in {
                "arroz": Nutrients(130, 2.5, 28, 0.3),
                "manga": Nutrients(60, 0.8, 15, 0.4),
                "sobrecoxa": Nutrients(210, 26, 0, 12),
                "ovos mexidos": Nutrients(150, 12, 1, 11),
            }.items()
        }
    )
    service = HealthMonitorService(estimator=estimator, **kwargs)
    household = service.create_household(name="Casa")
    person = service.create_person(
        household_id=household.id,
        name="Gabriel",
        timezone="America/Sao_Paulo",
    )
    return service, household.id, person.id


class WeightRoutingFixTest(unittest.TestCase):
    def test_weight_question_does_not_create_a_weight_entry(self) -> None:
        service, _, person_id = build_service()
        response = service.chat(
            person_id=person_id,
            message="qual era meu peso em 2025?",
            today=TODAY,
        )
        self.assertNotEqual(response.behavior_label, "log_weight")
        trend = service.weight_trend(person_id=person_id)
        self.assertEqual(trend.entries, ())

    def test_combined_weigh_in_and_meal_message_handles_both(self) -> None:
        service, _, person_id = build_service()
        response = service.chat(
            person_id=person_id,
            message="Bom dia! amanheci com 96,4kg\nCafé da manhã:\n100g de ovos mexidos",
            today=TODAY,
        )
        trend = service.weight_trend(person_id=person_id)
        self.assertEqual(trend.latest_kg, 96.4)
        self.assertEqual(response.behavior_label, "draft_text_meal")
        self.assertIn("Registrei o peso", response.message)
        proposal = service.proposals.proposals[response.proposal_id]
        self.assertEqual(len(proposal.entries), 1)
        self.assertEqual(proposal.entries[0].meal_type, "breakfast")


class EstimateProposalAmendmentTest(unittest.TestCase):
    def test_amending_estimate_backed_proposal_adds_and_subtracts(self) -> None:
        service, _, person_id = build_service()
        first = service.chat(
            person_id=person_id,
            message="Almoço: 100g de arroz",
            today=TODAY,
        )
        original = service.proposals.proposals[first.proposal_id]
        self.assertEqual(original.proposal_type, "diary_entries_with_estimates")

        amended_response = service.chat(
            person_id=person_id,
            message="Ah, esqueci de incluir 100g de manga",
            today=TODAY,
        )
        amended = service.proposals.proposals[amended_response.proposal_id]
        self.assertEqual(len(amended.entries), 2)
        self.assertEqual(
            service.proposals.proposals[original.id].status, "superseded"
        )
        pending_names = {
            item["food_name"] for item in amended.payload["estimated_food_versions"]
        }
        self.assertEqual(pending_names, {"Arroz", "Manga"})
        self.assertEqual(amended.totals.rounded().calories_kcal, 190)

        subtract_response = service.chat(
            person_id=person_id,
            message="subtrai 30g de arroz",
            today=TODAY,
        )
        final = service.proposals.proposals[subtract_response.proposal_id]
        arroz_entries = [entry for entry in final.entries if entry.quantity_g == 70.0]
        self.assertEqual(len(arroz_entries), 1)

        applied = service.confirm_proposal(final.id)
        self.assertEqual(applied.status, "applied")
        summary = service.day_summary(person_id, TODAY)
        self.assertEqual(sum(len(v) for v in summary.meals.values()), 2)

    def test_meal_heading_creates_new_meal_even_with_open_draft(self) -> None:
        service, _, person_id = build_service()
        breakfast = service.chat(
            person_id=person_id,
            message="Café da manhã: 100g de ovos mexidos",
            today=TODAY,
        )
        lunch = service.chat(
            person_id=person_id,
            message="Almoço:\n74g arroz\n113g sobrecoxa\n-33g ossos e pele",
            today=TODAY,
        )
        breakfast_proposal = service.proposals.proposals[breakfast.proposal_id]
        lunch_proposal = service.proposals.proposals[lunch.proposal_id]
        self.assertEqual(breakfast_proposal.status, "draft")
        self.assertNotEqual(breakfast.proposal_id, lunch.proposal_id)
        self.assertEqual(
            {entry.meal_type for entry in lunch_proposal.entries}, {"lunch"}
        )
        quantities = sorted(entry.quantity_g for entry in lunch_proposal.entries)
        self.assertEqual(quantities, [74.0, 80.0])


class RepeatMealPersistenceTest(unittest.TestCase):
    def test_repeat_meal_proposal_survives_service_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "health-monitor.sqlite3"
            service, household_id, person_id = build_service(
                repository=SQLiteStateRepository(db_path)
            )
            _, version = service.create_food_with_version(
                household_id=household_id,
                name="Arroz Branco",
                brand=None,
                version_label="cozido",
                nutrients_per_100g=Nutrients(130, 2.5, 28, 0.3),
                source="manual",
            )
            service.log_diary_entry(
                person_id=person_id,
                logged_at_local="2026-07-02T12:00:00",
                food_version_id=version.id,
                quantity_g=100,
                source="manual",
            )
            proposal = service.repeat_meal(
                person_id=person_id,
                source_day=date(2026, 7, 2),
                meal_type="lunch",
                logged_at_local="2026-07-03T12:00:00",
            )

            restarted = HealthMonitorService(
                repository=SQLiteStateRepository(db_path)
            )
            self.assertIn(proposal.id, restarted.proposals.proposals)
            self.assertEqual(
                restarted.proposals.proposals[proposal.id].status, "draft"
            )


class RollingSummaryTest(unittest.TestCase):
    def test_rolling_summary_mean_and_stddev_over_days_with_data(self) -> None:
        service, household_id, person_id = build_service()
        _, version = service.create_food_with_version(
            household_id=household_id,
            name="Arroz Branco",
            brand=None,
            version_label="cozido",
            nutrients_per_100g=Nutrients(100, 10, 20, 5),
            source="manual",
        )
        service.log_diary_entry(
            person_id=person_id,
            logged_at_local="2026-07-01T12:00:00",
            food_version_id=version.id,
            quantity_g=500,
            source="manual",
        )
        service.log_diary_entry(
            person_id=person_id,
            logged_at_local="2026-07-03T12:00:00",
            food_version_id=version.id,
            quantity_g=700,
            source="manual",
        )

        summary = service.rolling_summary(person_id=person_id, end=TODAY, days=7)

        self.assertEqual(summary.days, 7)
        self.assertEqual(summary.days_with_data, 2)
        self.assertEqual(summary.averages.calories_kcal, 600.0)
        self.assertEqual(summary.stddev.calories_kcal, 100.0)
        self.assertEqual(summary.averages.protein_g, 60.0)
        self.assertEqual(sorted(summary.daily), [date(2026, 7, 1), date(2026, 7, 3)])


class RequireModelFlagTest(unittest.TestCase):
    PYDANTIC_SETTINGS = {"agent_runtime": "pydantic-ai", "model_profile": "test-model"}

    def test_model_down_blocks_processing_and_carries_replay_message(self) -> None:
        service, _, person_id = build_service(model_health_checker=lambda: False)
        message = "Almoço: 100g de arroz"
        with self.assertRaises(ModelUnavailableError) as caught:
            service.chat(
                person_id=person_id,
                message=message,
                today=TODAY,
                agent_settings=self.PYDANTIC_SETTINGS,
            )
        self.assertEqual(caught.exception.replay_message, message)
        # Nothing was processed deterministically behind the user's back.
        self.assertEqual(service.proposals.proposals, {})
        self.assertEqual(service.weight_trend(person_id=person_id).entries, ())

    def test_model_down_blocks_weigh_in_too(self) -> None:
        service, _, person_id = build_service(model_health_checker=lambda: False)
        with self.assertRaises(ModelUnavailableError):
            service.chat(
                person_id=person_id,
                message="amanheci com 96,4kg",
                today=TODAY,
                agent_settings=self.PYDANTIC_SETTINGS,
            )
        self.assertEqual(service.weight_trend(person_id=person_id).entries, ())

    def test_flag_disabled_restores_deterministic_fallback(self) -> None:
        service, _, person_id = build_service(
            require_model=False, model_health_checker=lambda: False
        )
        response = service.chat(
            person_id=person_id,
            message="Almoço: 100g de arroz",
            today=TODAY,
            agent_settings=self.PYDANTIC_SETTINGS,
        )
        self.assertEqual(response.behavior_label, "draft_text_meal")
        self.assertIsNotNone(response.proposal_id)

    def test_deterministic_runtime_is_never_gated(self) -> None:
        service, _, person_id = build_service(model_health_checker=lambda: False)
        response = service.chat(
            person_id=person_id,
            message="Almoço: 100g de arroz",
            today=TODAY,
        )
        self.assertEqual(response.behavior_label, "draft_text_meal")

    def test_http_api_maps_model_unavailable_to_503(self) -> None:
        service, _, person_id = build_service(model_health_checker=lambda: False)
        api = HttpApi(service)
        response = api.handle(
            "POST",
            "/api/agent/chat",
            {
                "person_id": person_id,
                "message": "Almoço: 100g de arroz",
                "today": TODAY.isoformat(),
                "agent_settings": self.PYDANTIC_SETTINGS,
            },
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.body["error"]["type"], "model_unavailable")
        self.assertEqual(response.body["error"]["replay_message"], "Almoço: 100g de arroz")


if __name__ == "__main__":
    unittest.main()
