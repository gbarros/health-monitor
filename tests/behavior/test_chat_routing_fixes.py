from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

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
    def test_model_backed_weight_question_does_not_create_a_weight_entry_when_model_down(self) -> None:
        service, _, person_id = build_service(model_health_checker=lambda: False)
        with self.assertRaises(ModelUnavailableError):
            service.chat(
                person_id=person_id,
                message="qual era meu peso em 2025?",
                today=TODAY,
                agent_settings=RequireModelFlagTest.PYDANTIC_SETTINGS,
            )
        trend = service.weight_trend(person_id=person_id)
        self.assertEqual(trend.entries, ())

    def test_weight_modal_exception_still_logs_directly(self) -> None:
        service, _, person_id = build_service()
        entry = service.log_weight(
            person_id=person_id,
            measured_at_local="2026-07-03T08:00:00",
            weight_kg=96.4,
            note="manual modal",
            source="manual_ui",
        )
        trend = service.weight_trend(person_id=person_id)
        self.assertEqual(trend.latest_kg, 96.4)
        self.assertEqual(trend.entries[0].id, entry.id)


class EstimateProposalAmendmentTest(unittest.TestCase):
    def test_amending_estimate_backed_proposal_adds_and_subtracts(self) -> None:
        service, _, person_id = build_service()
        original = service.draft_structured_meal_proposal(
            person_id=person_id,
            day=TODAY,
            meal_type="lunch",
            items=[{"phrase": "arroz", "quantity_g": 100}],
            agent_settings={"research_lookup": True},
            source_text="model extracted rice",
        )
        self.assertEqual(original.proposal_type, "diary_entries_with_estimates")

        amended = service.amend_structured_meal_proposal(
            proposal_id=original.id,
            person_id=person_id,
            add=[{"phrase": "manga", "quantity_g": 100}],
            agent_settings={"research_lookup": True},
            source_text="model extracted manga amendment",
        )
        self.assertEqual(len(amended.entries), 2)
        self.assertEqual(
            service.proposals.proposals[original.id].status, "superseded"
        )
        pending_names = {
            item["food_name"] for item in amended.payload["estimated_food_versions"]
        }
        self.assertEqual(pending_names, {"Arroz", "Manga"})
        self.assertEqual(amended.totals.rounded().calories_kcal, 190)

        final = service.amend_structured_meal_proposal(
            proposal_id=amended.id,
            person_id=person_id,
            remove=[{"phrase": "arroz", "quantity_g": 30}],
            agent_settings={"research_lookup": True},
            source_text="model extracted rice subtraction",
        )
        arroz_entries = [entry for entry in final.entries if entry.quantity_g == 70.0]
        self.assertEqual(len(arroz_entries), 1)

        applied = service.confirm_proposal(final.id)
        self.assertEqual(applied.status, "applied")
        summary = service.day_summary(person_id, TODAY)
        self.assertEqual(sum(len(v) for v in summary.meals.values()), 2)

    def test_meal_heading_creates_new_meal_even_with_open_draft(self) -> None:
        service, _, person_id = build_service()
        breakfast = service.draft_structured_meal_proposal(
            person_id=person_id,
            day=TODAY,
            meal_type="breakfast",
            items=[{"phrase": "ovos mexidos", "quantity_g": 100}],
            agent_settings={"research_lookup": True},
            source_text="model extracted breakfast",
        )
        lunch = service.draft_structured_meal_proposal(
            person_id=person_id,
            day=TODAY,
            meal_type="lunch",
            items=[
                {"phrase": "arroz", "quantity_g": 74},
                {"phrase": "sobrecoxa", "quantity_g": 80},
            ],
            agent_settings={"research_lookup": True},
            source_text="model extracted lunch after subtracting bones",
        )
        self.assertEqual(breakfast.status, "draft")
        self.assertNotEqual(breakfast.id, lunch.id)
        self.assertEqual(
            {entry.meal_type for entry in lunch.entries}, {"lunch"}
        )
        quantities = sorted(entry.quantity_g for entry in lunch.entries)
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

    def test_flag_disabled_does_not_restore_hidden_deterministic_fallback(self) -> None:
        service, _, person_id = build_service(
            require_model=False, model_health_checker=lambda: False
        )
        response = service.chat(
            person_id=person_id,
            message="Almoço: 100g de arroz",
            today=TODAY,
            agent_settings=self.PYDANTIC_SETTINGS,
        )
        self.assertEqual(response.behavior_label, "answer_question")
        self.assertIsNone(response.proposal_id)
        self.assertEqual(service.proposals.proposals, {})

    def test_default_runtime_no_longer_interprets_chat_text_deterministically(self) -> None:
        service, _, person_id = build_service(model_health_checker=lambda: False)
        response = service.chat(
            person_id=person_id,
            message="Almoço: 100g de arroz",
            today=TODAY,
        )
        self.assertEqual(response.behavior_label, "answer_question")
        self.assertIsNone(response.proposal_id)
        self.assertEqual(service.proposals.proposals, {})

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

    def test_http_api_maps_agent_failure_to_500_without_outbox_replay(self) -> None:
        class BrokenAgent:
            def __init__(self, *, model_name: str, ollama_base_url: str) -> None:
                pass

            def answer(self, *, deps, message: str):
                raise ValueError("tool validation failed")

        service, _, person_id = build_service(model_health_checker=lambda: True)
        api = HttpApi(service)

        with patch("health_monitor.application.service.PydanticAINutritionAgent", BrokenAgent):
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

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.body["error"]["type"], "agent_error")
        self.assertIn("tool validation failed", response.body["error"]["message"])


class GateThreeFixesTest(unittest.TestCase):
    PYDANTIC_SETTINGS = {"agent_runtime": "pydantic-ai", "model_profile": "test-model"}

    def test_connection_failure_is_model_unavailable_with_original_replay(self) -> None:
        class ConnectionBrokenAgent:
            def __init__(self, *, model_name: str, ollama_base_url: str) -> None:
                pass

            def answer(self, *, deps, message: str):
                wrapper = RuntimeError("Connection error.")
                wrapper.__cause__ = ConnectionError("connection refused")
                raise wrapper

        service, _, person_id = build_service(model_health_checker=lambda: True)
        api = HttpApi(service)
        with patch("health_monitor.application.service.PydanticAINutritionAgent", ConnectionBrokenAgent):
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
        # Replay must carry the user's original text, never the composed context.
        self.assertEqual(response.body["error"]["replay_message"], "Almoço: 100g de arroz")

    def test_non_connection_agent_error_replay_is_original_user_message(self) -> None:
        class BrokenAgent:
            def __init__(self, *, model_name: str, ollama_base_url: str) -> None:
                pass

            def answer(self, *, deps, message: str):
                raise ValueError("tool validation failed")

        service, _, person_id = build_service(model_health_checker=lambda: True)
        api = HttpApi(service)
        with patch("health_monitor.application.service.PydanticAINutritionAgent", BrokenAgent):
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
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.body["error"]["type"], "agent_error")
        self.assertEqual(response.body["error"]["replay_message"], "Almoço: 100g de arroz")

    def test_failed_agent_run_still_persists_the_user_turn(self) -> None:
        class BrokenAgent:
            def __init__(self, *, model_name: str, ollama_base_url: str) -> None:
                pass

            def answer(self, *, deps, message: str):
                raise ValueError("tool_calls_limit exceeded")

        service, _, person_id = build_service(model_health_checker=lambda: True)
        from health_monitor.application.service import AgentExecutionError

        with patch("health_monitor.application.service.PydanticAINutritionAgent", BrokenAgent):
            with self.assertRaises(AgentExecutionError):
                service.chat(
                    person_id=person_id,
                    message="Almoço: 100g de arroz",
                    today=TODAY,
                    agent_settings=self.PYDANTIC_SETTINGS,
                )
        turns = service.chat_turns_for_person(person_id)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].user_message, "Almoço: 100g de arroz")
        self.assertEqual(turns[0].behavior_label, "agent_error")

    def test_new_chat_session_hides_prior_turns_from_agent_context(self) -> None:
        from health_monitor.application.service import AgentChatResponse

        class EchoAgent:
            def __init__(self, *, model_name: str, ollama_base_url: str) -> None:
                pass

            def answer(self, *, deps, message: str):
                return AgentChatResponse(
                    run_id="inner",
                    person_id=deps.person_id,
                    message="oi",
                    behavior_label="answer_question",
                )

        service, _, person_id = build_service(model_health_checker=lambda: True)
        with patch("health_monitor.application.service.PydanticAINutritionAgent", EchoAgent):
            service.chat(
                person_id=person_id,
                message="mensagem antiga",
                today=TODAY,
                agent_settings=self.PYDANTIC_SETTINGS,
            )
            service.start_new_chat_session(person_id=person_id)
            context = service._build_agent_context(person_id, TODAY)
            self.assertEqual(context["recent_chat_turns"], [])
            service.chat(
                person_id=person_id,
                message="mensagem nova",
                today=TODAY,
                agent_settings=self.PYDANTIC_SETTINGS,
            )
            context = service._build_agent_context(person_id, TODAY)
        self.assertEqual([t["user"] for t in context["recent_chat_turns"]], ["mensagem nova"])
        # Full history keeps every turn across both sessions.
        turns = service.chat_turns_for_person(person_id)
        self.assertEqual(len(turns), 2)
        self.assertEqual(len({t.session_id for t in turns}), 2)
        # Reopening the first session brings its turns back into context.
        sessions = service.chat_sessions_for_person(person_id)
        old_session = next(s for s in sessions if not s["active"])
        service.activate_chat_session(person_id=person_id, session_id=old_session["id"])
        context = service._build_agent_context(person_id, TODAY)
        self.assertEqual([t["user"] for t in context["recent_chat_turns"]], ["mensagem antiga"])

    def test_legacy_boundary_turns_migrate_to_sessions_on_restore(self) -> None:
        from health_monitor.application.service import AgentChatTurn

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.sqlite3"
            service, _, person_id = build_service(
                model_health_checker=lambda: True,
                repository=SQLiteStateRepository(db_path),
            )
            # Simulate the pre-session data shape: plain turns split by a
            # legacy boundary marker, none carrying a session id.
            for index, (user, label) in enumerate(
                [("primeira", "answer_question"), ("", "session_boundary"), ("segunda", "answer_question")]
            ):
                turn = AgentChatTurn(
                    id=f"agent_chat_turn_legacy_{index}",
                    person_id=person_id,
                    agent_run_id="",
                    user_message=user,
                    assistant_message="ok",
                    behavior_label=label,
                )
                service.chat_turns[turn.id] = turn
            service._persist()

            restored = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            turns = restored.chat_turns_for_person(person_id)
            labels = [t.behavior_label for t in turns]
            self.assertNotIn("session_boundary", labels)
            self.assertEqual(len(turns), 2)
            self.assertTrue(all(t.session_id for t in turns))
            self.assertEqual(len({t.session_id for t in turns}), 2)
            sessions = restored.chat_sessions_for_person(person_id)
            self.assertEqual(len(sessions), 2)
            # Active session is the most recent segment.
            self.assertTrue(next(s for s in sessions if s["active"])["preview"].startswith("segunda"))

    def test_memory_note_proposal_roundtrip_and_context_injection(self) -> None:
        service, _, person_id = build_service(model_health_checker=lambda: True)
        proposal = service.draft_memory_note_proposal(
            person_id=person_id,
            title="Rotina de almoço",
            body="Almoço padrão: 120g arroz integral, 100g feijão preto, 150g frango.",
        )
        self.assertEqual(proposal.proposal_type, "memory_note")
        # Nothing stored until the user confirms.
        self.assertEqual(service.memory_notes_for_person(person_id), ())
        applied = service.confirm_proposal(proposal.id)
        self.assertEqual(applied.status, "applied")
        notes = service.memory_notes_for_person(person_id)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].title, "Rotina de almoço")
        context = service._build_agent_context(person_id, TODAY)
        self.assertEqual(context["memory_notes"][0]["title"], "Rotina de almoço")

        # Update path keeps the same note id and created_at.
        update = service.draft_memory_note_proposal(
            person_id=person_id,
            title="Rotina de almoço",
            body="Almoço padrão agora com 140g arroz.",
            note_id=notes[0].id,
        )
        service.confirm_proposal(update.id)
        updated = service.memory_notes_for_person(person_id)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].id, notes[0].id)
        self.assertIn("140g arroz", updated[0].body)
        self.assertEqual(updated[0].created_at, notes[0].created_at)

        # Delete is a direct user action.
        service.delete_memory_note(updated[0].id)
        self.assertEqual(service.memory_notes_for_person(person_id), ())

    def test_memory_notes_survive_snapshot_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.sqlite3"
            service, _, person_id = build_service(
                model_health_checker=lambda: True,
                repository=SQLiteStateRepository(db_path),
            )
            proposal = service.draft_memory_note_proposal(
                person_id=person_id, title="Fato", body="Não como carne de porco."
            )
            service.confirm_proposal(proposal.id)
            restored = HealthMonitorService(repository=SQLiteStateRepository(db_path))
            notes = restored.memory_notes_for_person(person_id)
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0].body, "Não como carne de porco.")

    def test_model_item_estimates_tolerate_explicit_null_nutrients(self) -> None:
        # gemma/qwen sometimes emit "fiber_g": null; that must coerce to 0,
        # not crash the draft with float(None).
        service, _, person_id = build_service(model_health_checker=lambda: True)
        proposal = service.draft_structured_meal_proposal(
            person_id=person_id,
            items=[
                {
                    "phrase": "iogurte natural",
                    "quantity_g": 100,
                    "nutrients_per_100g": {
                        "calories_kcal": 60,
                        "protein_g": 4,
                        "carbs_g": 5,
                        "fat_g": 3,
                        "fiber_g": None,
                        "sodium_mg": None,
                    },
                }
            ],
            day=TODAY,
        )
        self.assertEqual(proposal.status, "draft")
        self.assertEqual(proposal.totals.rounded().calories_kcal, 60)
        self.assertEqual(proposal.totals.rounded().fiber_g, 0)

    def test_generic_staple_phrase_rejects_branded_lookup_product(self) -> None:
        match = HealthMonitorService._phrase_matches_product_name
        self.assertFalse(match("arroz", "Mini Biscoitos de Arroz Integral Camil Natural"))
        self.assertTrue(match("feijão preto", "Feijão Preto Camil"))
        self.assertTrue(match("arroz", "Arroz branco cozido"))
        self.assertFalse(match("arroz", "Biscoito Camil"))

    def test_second_meal_draft_in_same_chat_request_supersedes_first(self) -> None:
        service, _, person_id = build_service(model_health_checker=lambda: True)
        # Simulate an active chat request the way service.chat() sets it up.
        service._active_meal_draft_requests[person_id] = []
        first = service.draft_structured_meal_proposal(
            person_id=person_id,
            items=[{"phrase": "arroz", "quantity_g": 74}],
            day=TODAY,
        )
        second = service.draft_structured_meal_proposal(
            person_id=person_id,
            items=[{"phrase": "arroz", "quantity_g": 74}, {"phrase": "manga", "quantity_g": 100}],
            day=TODAY,
        )
        service._active_meal_draft_requests.pop(person_id, None)
        self.assertEqual(service.proposals.proposals[first.id].status, "superseded")
        self.assertEqual(service.proposals.proposals[second.id].status, "draft")

    def test_meal_draft_outside_chat_request_does_not_supersede(self) -> None:
        service, _, person_id = build_service(model_health_checker=lambda: True)
        first = service.draft_structured_meal_proposal(
            person_id=person_id,
            items=[{"phrase": "arroz", "quantity_g": 74}],
            day=TODAY,
        )
        second = service.draft_structured_meal_proposal(
            person_id=person_id,
            items=[{"phrase": "manga", "quantity_g": 100}],
            day=TODAY,
        )
        self.assertEqual(service.proposals.proposals[first.id].status, "draft")
        self.assertEqual(service.proposals.proposals[second.id].status, "draft")

    def test_stream_event_sink_receives_tool_calls_from_inner_draft_runs(self) -> None:
        from health_monitor.application.service import AgentChatResponse

        class DraftingAgent:
            def __init__(self, *, model_name: str, ollama_base_url: str) -> None:
                pass

            def answer(self, *, deps, message: str):
                proposal = deps.service.draft_structured_meal_proposal(
                    person_id=deps.person_id,
                    items=[{"phrase": "arroz", "quantity_g": 74}],
                    day=TODAY,
                    agent_settings=deps.settings,
                    source_text="structured meal draft from agent",
                )
                return AgentChatResponse(
                    run_id="inner",
                    person_id=deps.person_id,
                    message="drafted",
                    behavior_label="proposal_draft",
                    proposal_id=proposal.id,
                )

        service, _, person_id = build_service(model_health_checker=lambda: True)
        events: list[dict] = []
        with patch("health_monitor.application.service.PydanticAINutritionAgent", DraftingAgent):
            service.chat(
                person_id=person_id,
                message="Almoço: 74g arroz",
                today=TODAY,
                agent_settings=self.PYDANTIC_SETTINGS,
                stream_event_sink=events.append,
            )
        tool_events = [e for e in events if e.get("event") == "tool_call"]
        self.assertTrue(tool_events, "sink received no tool_call events from inner runs")
        names = {e["data"]["name"] for e in tool_events}
        self.assertTrue(
            names & {"resolve_food_reference", "estimate_food", "use_model_item_estimate"},
            f"expected inner-run resolution events, got {names}",
        )
        # Sink is cleaned up after the request.
        self.assertEqual(service._agent_event_sinks, {})
        self.assertEqual(service._active_meal_draft_requests, {})


if __name__ == "__main__":
    unittest.main()
