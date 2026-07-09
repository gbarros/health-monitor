from __future__ import annotations

import base64
import queue
import threading
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, urlparse

from health_monitor.application.service import (
    AgentChatResponse,
    AgentChatTurn,
    AgentExecutionError,
    AttachmentObject,
    BackgroundJob,
    DaySummary,
    DaySummaryEntry,
    AgentToolCall,
    GoalProfile,
    HealthMonitorService,
    Household,
    MemoryNote,
    ModelUnavailableError,
    OnboardingTurn,
    Person,
    ReviewNote,
    RollingSummary,
    WeekSummary,
    WeightEntry,
    WeightTrend,
)
from health_monitor.domain.diary import DiaryEntry
from health_monitor.domain.food_resolution import FoodResolution
from health_monitor.domain.foods import Food, FoodVersion
from health_monitor.domain.nutrients import Nutrients
from health_monitor.domain.proposals import CreateDiaryEntriesProposal
from health_monitor.lookup.foods import FoodLookupCandidate
from health_monitor.observability.nexuslog import NexusLogEvent, NexusLogSink


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: dict[str, Any]


@dataclass(frozen=True)
class HttpStreamResponse(HttpResponse):
    events: tuple[dict[str, Any], ...]
    event_iter: Callable[[], Iterable[dict[str, Any]]] | None = None

    def iter_events(self) -> Iterable[dict[str, Any]]:
        if self.event_iter is not None:
            return self.event_iter()
        return iter(self.events)


class HttpApi:
    def __init__(self, service: HealthMonitorService, event_sink: NexusLogSink | None = None) -> None:
        self.service = service
        self.event_sink = event_sink

    def handle(self, method: str, target: str, body: dict[str, Any] | None) -> HttpResponse:
        normalized_method = method.upper()
        parsed = urlparse(target)
        path = parsed.path
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        try:
            response = self._handle(normalized_method, target, body or {})
        except ModelUnavailableError as exc:
            response = HttpResponse(
                status_code=503,
                body={
                    "error": {
                        "type": "model_unavailable",
                        "message": str(exc),
                        "replay_message": exc.replay_message,
                    }
                },
            )
        except AgentExecutionError as exc:
            response = HttpResponse(
                status_code=500,
                body={
                    "error": {
                        "type": "agent_error",
                        "message": str(exc),
                        "replay_message": exc.replay_message,
                    }
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            response = HttpResponse(
                status_code=400,
                body={"error": {"type": type(exc).__name__, "message": str(exc)}},
            )
        self._emit_runtime_events(
            method=normalized_method,
            path=path,
            query=query,
            response=response,
        )
        return response

    def _emit_runtime_events(
        self,
        *,
        method: str,
        path: str,
        query: dict[str, str],
        response: HttpResponse,
    ) -> None:
        if self.event_sink is None:
            return
        self._emit(
            NexusLogEvent(
                service="health-monitor-api",
                level="error" if response.status_code >= 500 else "info",
                event="api.request.completed",
                payload={
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "has_error": "error" in response.body,
                },
                entity_type=entity_type_for_path(path),
                entity_id=entity_id_for_path(path, response.body),
            )
        )
        if response.status_code >= 400:
            return

        if method == "POST" and path == "/api/jobs":
            self._emit(
                NexusLogEvent(
                    service="health-monitor-api",
                    level="info",
                    event="job.enqueued",
                    entity_type="job",
                    entity_id=str(response.body["id"]),
                    job_id=str(response.body["id"]),
                    payload={
                        "job_type": str(response.body["job_type"]),
                        "status": str(response.body["status"]),
                        "person_id": person_id_from_job_payload(response.body),
                    },
                )
            )
            return

        if method == "POST" and path in {"/api/foods", "/api/diary/custom-food"}:
            self._emit_food_created(response.body)
            return

        if method == "POST" and path.startswith("/api/jobs/") and path.endswith("/process"):
            self._emit(
                NexusLogEvent(
                    service="health-monitor-api",
                    level="info",
                    event="job.processed",
                    entity_type="job",
                    entity_id=str(response.body["id"]),
                    job_id=str(response.body["id"]),
                    payload={
                        "job_type": str(response.body["job_type"]),
                        "status": str(response.body["status"]),
                        "attempts": int(response.body["attempts"]),
                    },
                )
            )
            return

        if method == "POST" and path.startswith("/api/proposals/") and path.endswith("/confirm"):
            self._emit_proposal_decision("proposal.applied", response.body)
            return

        if method == "POST" and path.startswith("/api/proposals/") and path.endswith("/reject"):
            self._emit_proposal_decision("proposal.rejected", response.body)
            return

        if method == "POST" and path.startswith("/api/agent/"):
            self._emit_agent_run_completed(response.body)
            return

        if method == "GET" and path == "/api/lookups/foods":
            source_types = sorted(
                {
                    str(item.get("source_type"))
                    for item in response.body
                    if isinstance(item, dict) and item.get("source_type") is not None
                }
            )
            self._emit(
                NexusLogEvent(
                    service="health-monitor-api",
                    level="info",
                    event="lookup.completed",
                    entity_type="lookup",
                    payload={
                        "person_id": query.get("person_id"),
                        "candidate_count": len(response.body),
                        "source_types": source_types,
                    },
                )
            )

    def _emit_proposal_decision(self, event_name: str, proposal: dict[str, Any]) -> None:
        self._emit(
            NexusLogEvent(
                service="health-monitor-api",
                level="info",
                event=event_name,
                entity_type="proposal",
                entity_id=str(proposal["id"]),
                payload={
                    "proposal_id": str(proposal["id"]),
                    "person_id": str(proposal["person_id"]),
                    "proposal_type": str(proposal["proposal_type"]),
                    "status": str(proposal["status"]),
                    "applied_record_count": len(proposal.get("applied_record_ids", [])),
                    "agent_run_id": proposal.get("source_agent_run_id"),
                },
            )
        )

    def _emit_food_created(self, body: dict[str, Any]) -> None:
        food = body.get("food")
        version = body.get("version")
        if not isinstance(food, dict) or not isinstance(version, dict):
            return
        self._emit(
            NexusLogEvent(
                service="health-monitor-api",
                level="info",
                event="food.created",
                entity_type="food",
                entity_id=str(food["id"]),
                payload={
                    "food_id": str(food["id"]),
                    "food_version_id": str(version["id"]),
                    "source": str(version.get("source")),
                    "alias_count": len(body.get("aliases", [])),
                    "barcode_count": len(body.get("barcodes", [])),
                },
            )
        )

    def _emit_agent_run_completed(self, body: dict[str, Any]) -> None:
        run_id = body.get("run_id") or body.get("source_agent_run_id")
        if run_id is None and isinstance(body.get("agent_run"), dict):
            run_id = body["agent_run"].get("id")
        if run_id is None:
            return
        self._emit(
            NexusLogEvent(
                service="health-monitor-api",
                level="info",
                event="agent.run.completed",
                entity_type="agent_run",
                entity_id=str(run_id),
                payload={
                    "agent_run_id": str(run_id),
                    "person_id": str(body.get("person_id")),
                    "proposal_id": body.get("proposal_id") or body.get("id"),
                    "proposal_type": body.get("proposal_type"),
                    "behavior_label": body.get("behavior_label"),
                    "status": body.get("status"),
                },
            )
        )

    def _emit(self, event: NexusLogEvent) -> None:
        if self.event_sink is None:
            return
        try:
            self.event_sink.emit(event)
        except Exception:
            return

    def _handle(self, method: str, target: str, body: dict[str, Any]) -> HttpResponse:
        parsed = urlparse(target)
        path = parsed.path
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}

        if method == "GET" and path == "/api/health":
            return HttpResponse(
                200,
                {
                    "status": "ok",
                    "service": "health-monitor-api",
                },
            )

        if method == "POST" and path == "/api/households":
            household = self.service.create_household(name=body["name"])
            return HttpResponse(201, household_to_dict(household))

        if method == "POST" and path == "/api/people":
            person = self.service.create_person(
                household_id=body["household_id"],
                name=body["name"],
                timezone=body["timezone"],
                birth_date=date.fromisoformat(body["birth_date"]) if body.get("birth_date") else None,
                sex=body.get("sex"),
                height_cm=body.get("height_cm"),
                activity_level=body.get("activity_level"),
            )
            return HttpResponse(201, person_to_dict(person))

        if method == "GET" and path == "/api/people":
            people = self.service.people_for_household(query["household_id"])
            return HttpResponse(200, [person_to_dict(person) for person in people])

        if method == "POST" and path == "/api/goals":
            goal = self.service.create_goal_profile(
                person_id=body["person_id"],
                starts_on=date.fromisoformat(body["starts_on"]),
                targets=nutrients_from_dict(body["targets"]),
                notes=body.get("notes"),
            )
            return HttpResponse(201, goal_profile_to_dict(goal))

        if method == "GET" and path == "/api/goals/active":
            goal = self.service.active_goal_profile(
                person_id=query["person_id"],
                day=date.fromisoformat(query["day"]),
            )
            return HttpResponse(200, goal_profile_to_dict(goal) if goal is not None else {})

        if method == "POST" and path == "/api/attachments":
            attachment = self.service.create_attachment(
                household_id=body["household_id"],
                person_id=body["person_id"],
                object_type=body["object_type"],
                mime_type=body["mime_type"],
                filename=body.get("filename"),
                content=base64.b64decode(body["content_base64"]),
                retention_policy=body.get("retention_policy", "keep"),
            )
            return HttpResponse(201, attachment_to_dict(attachment))

        if method == "GET" and path == "/api/attachments":
            attachments = self.service.attachments_for_record(
                linked_record_type=query["linked_record_type"],
                linked_record_id=query["linked_record_id"],
            )
            return HttpResponse(
                200,
                [attachment_to_dict(attachment, include_content=False) for attachment in attachments],
            )

        if method == "GET" and path.startswith("/api/attachments/"):
            attachment_id = path.removeprefix("/api/attachments/")
            attachment = self.service.get_attachment(attachment_id)
            return HttpResponse(200, attachment_to_dict(attachment))

        if method == "GET" and path == "/api/foods":
            foods = self.service.list_food_versions(
                household_id=query["household_id"],
                person_id=query.get("person_id"),
                query=query.get("q"),
            )
            return HttpResponse(
                200,
                [
                    food_response_to_dict(
                        self.service,
                        food,
                        version,
                        person_id=query.get("person_id"),
                    )
                    for food, version in foods
                ],
            )

        if method == "POST" and path == "/api/foods":
            food, version = self.service.create_food_with_version(
                household_id=body["household_id"],
                name=body["name"],
                brand=body.get("brand"),
                version_label=body["version_label"],
                nutrients_per_100g=nutrients_from_dict(body["nutrients_per_100g"]),
                source=body["source"],
                aliases=body.get("aliases"),
                barcode=body.get("barcode"),
                serving_size_g=body.get("serving_size_g"),
            )
            return HttpResponse(
                201,
                food_response_to_dict(self.service, food, version),
            )

        if method == "POST" and path.startswith("/api/foods/") and path.endswith("/archive"):
            food_id = path.removeprefix("/api/foods/").removesuffix("/archive")
            food = self.service.archive_food(food_id)
            return HttpResponse(200, food_to_dict(food))

        if method == "GET" and path == "/api/foods/resolve":
            resolution = self.service.resolve_food_reference(
                household_id=query["household_id"],
                person_id=query["person_id"],
                phrase=query.get("phrase"),
                barcode=query.get("barcode"),
            )
            return HttpResponse(200, food_resolution_to_dict(resolution))

        if method == "GET" and path == "/api/lookups/foods":
            candidates = self.service.lookup_food_candidates(
                household_id=query["household_id"],
                person_id=query["person_id"],
                phrase=query.get("phrase"),
                barcode=query.get("barcode"),
            )
            return HttpResponse(200, [food_lookup_candidate_to_dict(item) for item in candidates])

        if method == "POST" and path == "/api/lookups/foods/propose":
            proposal = self.service.propose_food_lookup_candidate(
                household_id=body["household_id"],
                person_id=body["person_id"],
                candidate_id=body["candidate_id"],
            )
            return HttpResponse(201, proposal_to_dict(proposal, self.service))

        if method == "POST" and path == "/api/diary":
            entry = self.service.log_diary_entry(
                person_id=body["person_id"],
                logged_at_local=body["logged_at_local"],
                food_version_id=body["food_version_id"],
                quantity_g=float(body["quantity_g"]) if body.get("quantity_g") is not None else None,
                serving_count=float(body["serving_count"]) if body.get("serving_count") is not None else None,
                source=body["source"],
                meal_type=body.get("meal_type"),
            )
            return HttpResponse(201, diary_entry_to_dict(entry))

        if method == "POST" and path == "/api/diary/custom-food":
            food, version, entry = self.service.create_custom_food_and_log_entry(
                household_id=body["household_id"],
                person_id=body["person_id"],
                name=body["name"],
                brand=body.get("brand"),
                version_label=body["version_label"],
                nutrients_per_100g=nutrients_from_dict(body["nutrients_per_100g"]),
                logged_at_local=body["logged_at_local"],
                quantity_g=float(body["quantity_g"]),
                aliases=body.get("aliases"),
                serving_size_g=body.get("serving_size_g"),
                barcode=body.get("barcode"),
                meal_type=body.get("meal_type"),
            )
            return HttpResponse(
                201,
                {
                    **food_response_to_dict(self.service, food, version),
                    "entry": diary_entry_to_dict(entry),
                },
            )

        if method == "PATCH" and path.startswith("/api/diary/"):
            entry_id = path.removeprefix("/api/diary/")
            entry = self.service.update_diary_entry(
                entry_id=entry_id,
                logged_at_local=body.get("logged_at_local"),
                food_version_id=body.get("food_version_id"),
                quantity_g=float(body["quantity_g"]) if body.get("quantity_g") is not None else None,
                meal_type=body.get("meal_type"),
            )
            return HttpResponse(200, diary_entry_to_dict(entry))

        if method == "DELETE" and path.startswith("/api/diary/"):
            entry_id = path.removeprefix("/api/diary/")
            entry = self.service.delete_diary_entry(entry_id)
            return HttpResponse(200, diary_entry_to_dict(entry))

        if method == "POST" and path.startswith("/api/diary/") and path.endswith("/restore"):
            entry_id = path.removeprefix("/api/diary/").removesuffix("/restore")
            entry = self.service.restore_diary_entry(entry_id)
            return HttpResponse(200, diary_entry_to_dict(entry))

        if method == "GET" and path == "/api/diary/day":
            summary = self.service.day_summary(
                person_id=query["person_id"],
                day=date.fromisoformat(query["day"]),
            )
            return HttpResponse(200, day_summary_to_dict(summary))

        if method == "GET" and path == "/api/diary/range":
            entries = self.service.diary_entries_range(
                person_id=query["person_id"],
                start=date.fromisoformat(query["start"]),
                end=date.fromisoformat(query["end"]),
            )
            return HttpResponse(200, [day_summary_entry_to_dict(entry) for entry in entries])

        if method == "POST" and path == "/api/weights":
            entry = self.service.log_weight(
                person_id=body["person_id"],
                measured_at_local=body["measured_at_local"],
                weight_kg=float(body["weight_kg"]),
                note=body.get("note"),
                source=body["source"],
            )
            return HttpResponse(201, weight_entry_to_dict(entry))

        if method == "PATCH" and path.startswith("/api/weights/"):
            entry_id = path.removeprefix("/api/weights/")
            entry = self.service.update_weight_entry(
                entry_id=entry_id,
                measured_at_local=body.get("measured_at_local"),
                weight_kg=float(body["weight_kg"]) if body.get("weight_kg") is not None else None,
                note=body.get("note"),
            )
            return HttpResponse(200, weight_entry_to_dict(entry))

        if method == "GET" and path == "/api/weights/trend":
            trend = self.service.weight_trend(
                person_id=query["person_id"],
                start=date.fromisoformat(query["start"]) if query.get("start") else None,
                end=date.fromisoformat(query["end"]) if query.get("end") else None,
            )
            return HttpResponse(200, weight_trend_to_dict(trend))

        if method == "GET" and path == "/api/summaries/week":
            summary = self.service.week_summary(
                person_id=query["person_id"],
                start=date.fromisoformat(query["start"]),
                end=date.fromisoformat(query["end"]),
            )
            return HttpResponse(200, week_summary_to_dict(summary))

        if method == "GET" and path == "/api/summaries/rolling":
            summary = self.service.rolling_summary(
                person_id=query["person_id"],
                end=date.fromisoformat(query["end"]),
                days=int(query.get("days", "7")),
            )
            return HttpResponse(200, rolling_summary_to_dict(summary))

        if method == "GET" and path == "/api/review-notes":
            notes = self.service.review_notes_for_person(query["person_id"])
            return HttpResponse(200, [review_note_to_dict(note) for note in notes])

        if method == "GET" and path == "/api/exports/full":
            return HttpResponse(200, self.service.export_data())

        if method == "POST" and path == "/api/imports/full":
            imported = self.service.import_data(body)
            return HttpResponse(201, {"imported": imported})

        if method == "POST" and path == "/api/jobs":
            job = self.service.enqueue_job(
                job_type=body["job_type"],
                payload=body.get("payload", {}),
                client_request_id=body.get("client_request_id"),
            )
            return HttpResponse(201, job_to_dict(job))

        if method == "GET" and path == "/api/jobs":
            jobs = self.service.list_jobs(
                person_id=query.get("person_id"),
                status=query.get("status"),
            )
            return HttpResponse(200, [job_to_dict(job) for job in jobs])

        if method == "GET" and path.startswith("/api/jobs/"):
            job_id = path.removeprefix("/api/jobs/")
            job = self.service.get_job(job_id)
            return HttpResponse(200, job_to_dict(job))

        if method == "POST" and path.startswith("/api/jobs/") and path.endswith("/process"):
            job_id = path.removeprefix("/api/jobs/").removesuffix("/process")
            job = self.service.process_job(job_id)
            return HttpResponse(200, job_to_dict(job))

        if method == "POST" and path == "/api/agent/chat":
            response = self.service.chat(
                person_id=body["person_id"],
                message=body["message"],
                today=date.fromisoformat(body["today"]) if body.get("today") else date.today(),
                agent_settings=body.get("agent_settings"),
                attachment_ids=body.get("attachment_ids"),
                intent=body.get("intent"),
            )
            return HttpResponse(201, agent_chat_response_to_dict(response, self.service))

        if method in {"GET", "POST"} and path == "/api/agent/chat/stream":
            # EventSource-friendly streaming path for chat replies. GET exists
            # for browser EventSource clients, so attachments stay POST-only.
            stream_input = body if method == "POST" else query
            if "person_id" not in stream_input or not stream_input["person_id"]:
                raise ValueError("stream requires person_id")
            if "message" not in stream_input or not stream_input["message"]:
                raise ValueError("stream requires message")
            if method == "GET" and "attachment_ids" in stream_input:
                raise ValueError("GET stream endpoint does not accept attachment_ids")
            stream_settings = stream_input.get("agent_settings")
            if stream_settings is None and method == "GET" and query.get("model_profile"):
                stream_settings = {"model_profile": query["model_profile"]}
            def stream_events() -> Iterable[dict[str, Any]]:
                events: queue.Queue[dict[str, Any]] = queue.Queue()
                result: dict[str, Any] = {}

                def run_chat() -> None:
                    try:
                        response = self.service.chat(
                            person_id=str(stream_input["person_id"]),
                            message=str(stream_input["message"]),
                            today=date.fromisoformat(str(stream_input["today"])) if stream_input.get("today") else date.today(),
                            agent_settings=stream_settings,
                            attachment_ids=stream_input.get("attachment_ids") if method == "POST" else None,
                            intent=str(stream_input["intent"]) if stream_input.get("intent") is not None else None,
                            stream_event_sink=events.put,
                        )
                        result["response"] = response
                    except Exception as exc:
                        result["error"] = exc

                yield {"event": "run_started", "data": {"status": "started"}}
                thread = threading.Thread(target=run_chat, daemon=True)
                thread.start()
                while thread.is_alive() or not events.empty():
                    try:
                        yield events.get(timeout=0.25)
                    except queue.Empty:
                        continue
                thread.join()
                if "error" in result:
                    raise result["error"]
                response = result["response"]
                final = agent_chat_response_to_dict(response, self.service)
                yield {"event": "text_delta", "data": {"text": response.message}}
                yield {"event": "final", "data": final}

            return HttpStreamResponse(
                status_code=200,
                body={},
                events=(),
                event_iter=stream_events,
            )

        if method == "GET" and path == "/api/memory-notes":
            notes = self.service.memory_notes_for_person(query["person_id"])
            return HttpResponse(200, [memory_note_to_dict(note) for note in notes])

        if method == "DELETE" and path.startswith("/api/memory-notes/"):
            note = self.service.delete_memory_note(path.removeprefix("/api/memory-notes/"))
            return HttpResponse(200, memory_note_to_dict(note))

        if method == "POST" and path == "/api/agent/new-chat-session":
            session_id = self.service.start_new_chat_session(person_id=body["person_id"])
            return HttpResponse(201, {"session_id": session_id})

        if method == "GET" and path == "/api/agent/chat-sessions":
            sessions = self.service.chat_sessions_for_person(query["person_id"])
            return HttpResponse(200, sessions)

        if method == "POST" and path == "/api/agent/chat-sessions/activate":
            session_id = self.service.activate_chat_session(
                person_id=body["person_id"],
                session_id=body["session_id"],
            )
            return HttpResponse(200, {"session_id": session_id})

        if method == "POST" and path == "/api/agent/onboarding-chat":
            turn = self.service.onboarding_chat(
                session_id=body["session_id"],
                message=body["message"],
                household_id=body.get("household_id"),
                agent_settings=body.get("agent_settings"),
            )
            return HttpResponse(201, onboarding_turn_to_dict(turn))

        if method == "GET" and path == "/api/agent/onboarding-history":
            turns = self.service.onboarding_turns_for_session(query["session_id"])
            return HttpResponse(200, [onboarding_turn_to_dict(turn) for turn in turns])

        if method == "GET" and path == "/api/agent/chat-history":
            turns = self.service.chat_turns_for_person(query["person_id"])
            if query.get("session_id"):
                turns = tuple(turn for turn in turns if turn.session_id == query["session_id"])
            return HttpResponse(200, [agent_chat_turn_to_dict(turn) for turn in turns])

        if method == "GET" and path == "/api/proposals":
            proposals = self.service.list_proposals(
                person_id=query.get("person_id"),
                status=query.get("status"),
            )
            return HttpResponse(200, [proposal_to_dict(proposal, self.service) for proposal in proposals])

        if method == "GET" and path.startswith("/api/proposals/"):
            proposal_id = path.removeprefix("/api/proposals/")
            proposal = self.service.get_proposal(proposal_id)
            return HttpResponse(200, proposal_to_dict(proposal, self.service))

        if method == "POST" and path.startswith("/api/proposals/") and path.endswith("/confirm"):
            proposal_id = path.removeprefix("/api/proposals/").removesuffix("/confirm")
            proposal = self.service.confirm_proposal(proposal_id)
            return HttpResponse(200, proposal_to_dict(proposal, self.service))

        if method == "PATCH" and path.startswith("/api/proposals/") and "/entries/" in path:
            proposal_part, entry_id = path.removeprefix("/api/proposals/").split("/entries/", maxsplit=1)
            proposal = self.service.update_proposal_entry(
                proposal_id=proposal_part,
                entry_id=entry_id,
                food_version_id=body.get("food_version_id"),
                quantity_g=float(body["quantity_g"]) if body.get("quantity_g") is not None else None,
                meal_type=body.get("meal_type"),
            )
            return HttpResponse(200, proposal_to_dict(proposal, self.service))

        if method == "POST" and path.startswith("/api/proposals/") and path.endswith("/reject"):
            proposal_id = path.removeprefix("/api/proposals/").removesuffix("/reject")
            proposal = self.service.reject_proposal(proposal_id)
            return HttpResponse(200, proposal_to_dict(proposal, self.service))

        return HttpResponse(
            404,
            {"error": {"type": "NotFound", "message": f"no route for {method} {path}"}},
        )


def household_to_dict(household: Household) -> dict[str, Any]:
    return {
        "id": household.id,
        "name": household.name,
        "created_at": household.created_at.isoformat(),
    }


def person_to_dict(person: Person) -> dict[str, Any]:
    return {
        "id": person.id,
        "household_id": person.household_id,
        "name": person.name,
        "timezone": person.timezone,
        "birth_date": person.birth_date.isoformat() if person.birth_date is not None else None,
        "sex": person.sex,
        "height_cm": person.height_cm,
        "activity_level": person.activity_level,
        "created_at": person.created_at.isoformat(),
    }


def goal_profile_to_dict(goal: GoalProfile) -> dict[str, Any]:
    return {
        "id": goal.id,
        "person_id": goal.person_id,
        "starts_on": goal.starts_on.isoformat(),
        "ends_on": goal.ends_on.isoformat() if goal.ends_on is not None else None,
        "targets": nutrients_to_dict(goal.targets),
        "notes": goal.notes,
        "created_at": goal.created_at.isoformat(),
    }


def attachment_to_dict(attachment: AttachmentObject, *, include_content: bool = True) -> dict[str, Any]:
    payload = {
        "id": attachment.id,
        "household_id": attachment.household_id,
        "created_by_person_id": attachment.created_by_person_id,
        "object_type": attachment.object_type,
        "mime_type": attachment.mime_type,
        "byte_size": attachment.byte_size,
        "sha256": attachment.sha256,
        "filename": attachment.filename,
        "storage_status": attachment.storage_status,
        "retention_policy": attachment.retention_policy,
        "linked_record_type": attachment.linked_record_type,
        "linked_record_id": attachment.linked_record_id,
        "created_at": attachment.created_at.isoformat(),
    }
    if include_content:
        payload["content_base64"] = base64.b64encode(attachment.content).decode("ascii")
    return payload


def entity_type_for_path(path: str) -> str | None:
    if path.startswith("/api/proposals/"):
        return "proposal"
    if path.startswith("/api/jobs"):
        return "job"
    if path.startswith("/api/agent/"):
        return "agent_run"
    if path.startswith("/api/lookups/"):
        return "lookup"
    return None


def entity_id_for_path(path: str, body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    if path.startswith("/api/jobs") and body.get("id") is not None:
        return str(body["id"])
    if path.startswith("/api/proposals/") and body.get("id") is not None:
        return str(body["id"])
    if path.startswith("/api/agent/"):
        run_id = body.get("run_id") or body.get("source_agent_run_id")
        if run_id is None and isinstance(body.get("agent_run"), dict):
            run_id = body["agent_run"].get("id")
        return str(run_id) if run_id is not None else None
    return None


def person_id_from_job_payload(job: dict[str, Any]) -> str | None:
    payload = job.get("payload")
    if not isinstance(payload, dict):
        return None
    person_id = payload.get("person_id")
    return str(person_id) if person_id is not None else None


def food_to_dict(food: Food) -> dict[str, Any]:
    return {
        "id": food.id,
        "household_id": food.household_id,
        "name": food.name,
        "brand": food.brand,
        "default_version_id": food.default_version_id,
        "archived": food.archived,
    }


def food_response_to_dict(
    service: HealthMonitorService,
    food: Food,
    version: FoodVersion,
    *,
    person_id: str | None = None,
) -> dict[str, Any]:
    return {
        "food": food_to_dict(food),
        "version": food_version_to_dict(version),
        "aliases": food_aliases_for_response(service, food),
        "barcodes": food_barcodes_for_response(service, food, version),
        "is_default": food.default_version_id == version.id,
        "last_used_at": food_last_used_at_for_response(service, food, person_id),
        "attachments": [
            attachment_to_dict(attachment, include_content=False)
            for attachment in service.attachments_for_record(
                linked_record_type="food_version",
                linked_record_id=version.id,
            )
        ],
    }


def food_aliases_for_response(service: HealthMonitorService, food: Food) -> list[str]:
    return sorted(
        alias.phrase
        for alias in service.catalog.aliases.values()
        if alias.household_id == food.household_id and alias.food_id == food.id
    )


def food_last_used_at_for_response(
    service: HealthMonitorService,
    food: Food,
    person_id: str | None,
) -> str | None:
    if person_id is None:
        return None
    latest = None
    for entry in service.diary.entries.values():
        if entry.person_id != person_id or entry.deleted_at is not None:
            continue
        version = service.catalog.versions.get(entry.food_version_id)
        if version is None or version.food_id != food.id:
            continue
        if latest is None or entry.logged_at > latest:
            latest = entry.logged_at
    return latest.isoformat() if latest is not None else None


def food_barcodes_for_response(
    service: HealthMonitorService,
    food: Food,
    version: FoodVersion,
) -> list[str]:
    return sorted(
        association.barcode
        for association in service.catalog.barcode_associations.values()
        if association.household_id == food.household_id
        and association.food_id == food.id
        and not association.archived
        and (
            association.food_version_id is None
            or association.food_version_id == version.id
        )
    )


def food_version_to_dict(version: FoodVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "food_id": version.food_id,
        "label": version.label,
        "nutrients_per_100g": nutrients_to_dict(version.nutrients_per_100g),
        "source": version.source,
        "serving_size_g": version.serving_size_g,
        "confidence": version.confidence,
        "created_at": version.created_at.isoformat(),
        "archived": version.archived,
    }


def food_resolution_to_dict(resolution: FoodResolution) -> dict[str, Any]:
    return {
        "food_id": resolution.food_id,
        "food_version_id": resolution.food_version_id,
        "reason": resolution.reason,
        "confidence": resolution.confidence,
        "needs_clarification": resolution.needs_clarification,
    }


def food_lookup_candidate_to_dict(candidate: FoodLookupCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "source_type": candidate.source_type,
        "source_name": candidate.source_name,
        "source_id": candidate.source_id,
        "source_url": candidate.source_url,
        "product_name": candidate.product_name,
        "brand": candidate.brand,
        "barcode": candidate.barcode,
        "food_id": candidate.food_id,
        "food_version_id": candidate.food_version_id,
        "serving_size_g": candidate.serving_size_g,
        "nutrients_per_100g": nutrients_to_dict(candidate.nutrients_per_100g.rounded()),
        "confidence": candidate.confidence,
        "warnings": list(candidate.warnings),
        "research_prompt": candidate.research_prompt,
        "source_claims": [dict(claim) for claim in candidate.source_claims],
    }


def diary_entry_to_dict(entry: DiaryEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "person_id": entry.person_id,
        "logged_at": entry.logged_at.isoformat(),
        "meal_type": entry.meal_type,
        "food_version_id": entry.food_version_id,
        "quantity_g": entry.quantity_g,
        "source": entry.source,
        "deleted_at": entry.deleted_at.isoformat() if entry.deleted_at is not None else None,
    }


def day_summary_to_dict(summary: DaySummary) -> dict[str, Any]:
    return {
        "person_id": summary.person_id,
        "day": summary.day.isoformat(),
        "totals": nutrients_to_dict(summary.totals.rounded()),
        "target": nutrients_to_dict(summary.target) if summary.target is not None else None,
        "target_delta": nutrients_to_dict(summary.target_delta.rounded())
        if summary.target_delta is not None
        else None,
        "meals": {
            meal_type: [day_summary_entry_to_dict(entry) for entry in entries]
            for meal_type, entries in summary.meals.items()
        },
    }


def day_summary_entry_to_dict(entry: DaySummaryEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "logged_at": entry.logged_at.isoformat(),
        "meal_type": entry.meal_type,
        "food_id": entry.food_id,
        "food_name": entry.food_name,
        "brand": entry.brand,
        "food_version_id": entry.food_version_id,
        "food_version_label": entry.food_version_label,
        "quantity_g": entry.quantity_g,
        "nutrients": nutrients_to_dict(entry.nutrients.rounded()),
        "source": entry.source,
        "evidence_status": entry.evidence_status,
        "confidence": entry.confidence,
    }


def weight_entry_to_dict(entry: WeightEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "person_id": entry.person_id,
        "measured_at": entry.measured_at.isoformat(),
        "weight_kg": entry.weight_kg,
        "note": entry.note,
        "source": entry.source,
    }


def weight_trend_to_dict(trend: WeightTrend) -> dict[str, Any]:
    return {
        "person_id": trend.person_id,
        "entries": [weight_entry_to_dict(entry) for entry in trend.entries],
        "latest_kg": trend.latest_kg,
        "delta_kg": trend.delta_kg,
    }


def week_summary_to_dict(summary: WeekSummary) -> dict[str, Any]:
    return {
        "person_id": summary.person_id,
        "start": summary.start.isoformat(),
        "end": summary.end.isoformat(),
        "daily": {
            day.isoformat(): nutrients_to_dict(nutrients.rounded())
            for day, nutrients in summary.daily.items()
        },
        "daily_targets": {
            day.isoformat(): nutrients_to_dict(nutrients)
            for day, nutrients in summary.daily_targets.items()
        },
        "totals": nutrients_to_dict(summary.totals.rounded()),
        "averages": nutrients_to_dict(summary.averages.rounded()),
        "weight_delta_kg": summary.weight_delta_kg,
    }


def rolling_summary_to_dict(summary: RollingSummary) -> dict[str, Any]:
    return {
        "person_id": summary.person_id,
        "start": summary.start.isoformat(),
        "end": summary.end.isoformat(),
        "days": summary.days,
        "days_with_data": summary.days_with_data,
        "daily": {
            day.isoformat(): nutrients_to_dict(nutrients.rounded())
            for day, nutrients in summary.daily.items()
        },
        "averages": nutrients_to_dict(summary.averages),
        "stddev": nutrients_to_dict(summary.stddev),
    }


def review_note_to_dict(note: ReviewNote) -> dict[str, Any]:
    return {
        "id": note.id,
        "person_id": note.person_id,
        "note_type": note.note_type,
        "title": note.title,
        "body": note.body,
        "starts_on": note.starts_on.isoformat() if note.starts_on is not None else None,
        "ends_on": note.ends_on.isoformat() if note.ends_on is not None else None,
        "source": note.source,
        "source_agent_run_id": note.source_agent_run_id,
        "source_proposal_id": note.source_proposal_id,
        "source_record_refs": list(note.source_record_refs),
        "created_at": note.created_at.isoformat(),
    }


def proposal_to_dict(
    proposal: CreateDiaryEntriesProposal,
    service: HealthMonitorService,
) -> dict[str, Any]:
    entries = []
    pending_versions = {
        str(item["food_version_id"]): dict(item)
        for item in proposal.payload.get("estimated_food_versions", [])
    }
    for entry in proposal.entries:
        pending = pending_versions.get(entry.food_version_id)
        item = diary_entry_to_dict(entry)
        if pending is not None:
            nutrients = nutrients_from_dict(dict(pending["nutrients_per_100g"]))
            item.update(
                {
                    "food_id": pending["food_id"],
                    "food_name": pending["food_name"],
                    "brand": pending.get("brand"),
                    "food_version_label": pending["version_label"],
                    "nutrients": nutrients_to_dict(nutrients.scale(entry.quantity_g / 100).rounded()),
                }
            )
        else:
            version = service.catalog.get_version(entry.food_version_id)
            food = service.catalog.foods[version.food_id]
            item.update(
                {
                    "food_id": food.id,
                    "food_name": food.name,
                    "brand": food.brand,
                    "food_version_label": version.label,
                    "nutrients": nutrients_to_dict(
                        version.nutrients_per_100g.scale(entry.quantity_g / 100).rounded()
                    ),
                }
            )
        entries.append(item)
    return {
        "id": proposal.id,
        "person_id": proposal.person_id,
        "proposal_type": proposal.proposal_type,
        "status": proposal.status,
        "summary": proposal.summary,
        "payload": proposal.payload,
        "totals": nutrients_to_dict(proposal.totals.rounded()),
        "evidence": list(proposal.evidence),
        "source_agent_run_id": proposal.source_agent_run_id,
        "agent_run": agent_run_to_dict(service, proposal.source_agent_run_id),
        "applied_record_ids": list(proposal.applied_record_ids),
        "created_at": proposal.created_at.isoformat(),
        "confirmed_at": proposal.confirmed_at.isoformat()
        if proposal.confirmed_at is not None
        else None,
        "rejected_at": proposal.rejected_at.isoformat()
        if proposal.rejected_at is not None
        else None,
        "entries": entries,
    }


def agent_chat_response_to_dict(
    response: AgentChatResponse,
    service: HealthMonitorService,
) -> dict[str, Any]:
    proposal = service.get_proposal(response.proposal_id) if response.proposal_id else None
    return {
        "run_id": response.run_id,
        "person_id": response.person_id,
        "message": response.message,
        "behavior_label": response.behavior_label,
        "citations": list(response.citations),
        "proposal_id": response.proposal_id,
        "proposal": proposal_to_dict(proposal, service) if proposal is not None else None,
    }


def memory_note_to_dict(note: MemoryNote) -> dict[str, Any]:
    return {
        "id": note.id,
        "person_id": note.person_id,
        "title": note.title,
        "body": note.body,
        "source": note.source,
        "source_proposal_id": note.source_proposal_id,
        "created_at": note.created_at.isoformat(),
        "updated_at": note.updated_at.isoformat(),
    }


def agent_chat_turn_to_dict(turn: AgentChatTurn) -> dict[str, Any]:
    return {
        "id": turn.id,
        "person_id": turn.person_id,
        "agent_run_id": turn.agent_run_id,
        "user_message": turn.user_message,
        "assistant_message": turn.assistant_message,
        "behavior_label": turn.behavior_label,
        "citations": [dict(item) for item in turn.citations],
        "proposal_id": turn.proposal_id,
        "created_at": turn.created_at.isoformat(),
        "session_id": turn.session_id,
    }


def onboarding_turn_to_dict(turn: OnboardingTurn) -> dict[str, Any]:
    return {
        "id": turn.id,
        "session_id": turn.session_id,
        "household_id": turn.household_id,
        "user_message": turn.user_message,
        "assistant_message": turn.assistant_message,
        "proposal_id": turn.proposal_id,
        "created_at": turn.created_at.isoformat(),
    }


def agent_run_to_dict(
    service: HealthMonitorService,
    agent_run_id: str | None,
) -> dict[str, Any] | None:
    if agent_run_id is None:
        return None
    run = service.get_agent_run(agent_run_id)
    return {
        "id": run.id,
        "person_id": run.person_id,
        "input_text": run.input_text,
        "settings": run.settings,
        "status": run.status,
        "proposal_id": run.proposal_id,
        "runtime": run.runtime,
        "model_name": run.model_name,
        "tool_loop_count": run.tool_loop_count,
        "fallback_reason": run.fallback_reason,
        "created_at": run.created_at.isoformat(),
        "tool_calls": [
            agent_tool_call_to_dict(call)
            for call in service.agent_tool_calls_for_run(run.id)
        ],
    }


def agent_tool_call_to_dict(call: AgentToolCall) -> dict[str, Any]:
    return {
        "id": call.id,
        "agent_run_id": call.agent_run_id,
        "person_id": call.person_id,
        "tool_name": call.tool_name,
        "input_summary": call.input_summary,
        "output_summary": call.output_summary,
        "status": call.status,
        "source_record_ids": list(call.source_record_ids),
        "error": call.error,
        "started_at": call.started_at.isoformat(),
        "completed_at": call.completed_at.isoformat()
        if call.completed_at is not None
        else None,
    }


def job_to_dict(job: BackgroundJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "payload": job.payload,
        "client_request_id": job.client_request_id,
        "result": job.result,
        "last_error": job.last_error,
        "attempts": job.attempts,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at is not None else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at is not None else None,
    }


def nutrients_from_dict(value: dict[str, Any]) -> Nutrients:
    return Nutrients(
        calories_kcal=float(value.get("calories_kcal", 0)),
        protein_g=float(value.get("protein_g", 0)),
        carbs_g=float(value.get("carbs_g", 0)),
        fat_g=float(value.get("fat_g", 0)),
        fiber_g=float(value.get("fiber_g", 0)),
        sodium_mg=float(value.get("sodium_mg", 0)),
    )


def nutrients_to_dict(nutrients: Nutrients) -> dict[str, float]:
    return {
        "calories_kcal": nutrients.calories_kcal,
        "protein_g": nutrients.protein_g,
        "carbs_g": nutrients.carbs_g,
        "fat_g": nutrients.fat_g,
        "fiber_g": nutrients.fiber_g,
        "sodium_mg": nutrients.sodium_mg,
    }
