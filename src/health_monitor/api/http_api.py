from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

from health_monitor.application.service import (
    AgentChatResponse,
    DaySummary,
    DaySummaryEntry,
    GoalProfile,
    HealthMonitorService,
    Household,
    Person,
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


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: dict[str, Any]


class HttpApi:
    def __init__(self, service: HealthMonitorService) -> None:
        self.service = service

    def handle(self, method: str, target: str, body: dict[str, Any] | None) -> HttpResponse:
        try:
            return self._handle(method.upper(), target, body or {})
        except (KeyError, TypeError, ValueError) as exc:
            return HttpResponse(
                status_code=400,
                body={"error": {"type": type(exc).__name__, "message": str(exc)}},
            )

    def _handle(self, method: str, target: str, body: dict[str, Any]) -> HttpResponse:
        parsed = urlparse(target)
        path = parsed.path
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}

        if method == "GET" and path == "/api/health":
            return HttpResponse(200, {"status": "ok"})

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
                {"food": food_to_dict(food), "version": food_version_to_dict(version)},
            )

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
                quantity_g=float(body["quantity_g"]),
                source=body["source"],
                meal_type=body.get("meal_type"),
            )
            return HttpResponse(201, diary_entry_to_dict(entry))

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

        if method == "POST" and path == "/api/weights":
            entry = self.service.log_weight(
                person_id=body["person_id"],
                measured_at_local=body["measured_at_local"],
                weight_kg=float(body["weight_kg"]),
                note=body.get("note"),
                source=body["source"],
            )
            return HttpResponse(201, weight_entry_to_dict(entry))

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

        if method == "GET" and path == "/api/exports/full":
            return HttpResponse(200, self.service.export_data())

        if method == "POST" and path == "/api/imports/full":
            imported = self.service.import_data(body)
            return HttpResponse(201, {"imported": imported})

        if method == "POST" and path == "/api/agent/text-meal":
            proposal = self.service.propose_text_meal(
                person_id=body["person_id"],
                logged_at_local=body["logged_at_local"],
                text=body["text"],
                agent_settings=body.get("agent_settings"),
            )
            return HttpResponse(201, proposal_to_dict(proposal, self.service))

        if method == "POST" and path == "/api/agent/label-scan":
            proposal = self.service.propose_label_scan(
                household_id=body["household_id"],
                person_id=body["person_id"],
                table_text=body["table_text"],
                set_as_default=bool(body.get("set_as_default", True)),
            )
            return HttpResponse(201, proposal_to_dict(proposal, self.service))

        if method == "POST" and path == "/api/agent/recipe":
            proposal = self.service.propose_recipe(
                household_id=body["household_id"],
                person_id=body["person_id"],
                recipe_text=body["recipe_text"],
            )
            return HttpResponse(201, proposal_to_dict(proposal, self.service))

        if method == "POST" and path == "/api/agent/chat":
            response = self.service.chat(
                person_id=body["person_id"],
                message=body["message"],
                today=date.fromisoformat(body["today"]) if body.get("today") else date.today(),
                agent_settings=body.get("agent_settings"),
            )
            return HttpResponse(201, agent_chat_response_to_dict(response, self.service))

        if method == "POST" and path.startswith("/api/proposals/") and path.endswith("/confirm"):
            proposal_id = path.removeprefix("/api/proposals/").removesuffix("/confirm")
            proposal = self.service.confirm_proposal(proposal_id)
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


def food_to_dict(food: Food) -> dict[str, Any]:
    return {
        "id": food.id,
        "household_id": food.household_id,
        "name": food.name,
        "brand": food.brand,
        "default_version_id": food.default_version_id,
        "archived": food.archived,
    }


def food_version_to_dict(version: FoodVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "food_id": version.food_id,
        "label": version.label,
        "nutrients_per_100g": nutrients_to_dict(version.nutrients_per_100g),
        "source": version.source,
        "serving_size_g": version.serving_size_g,
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
                    "brand": None,
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
        "created_at": run.created_at.isoformat(),
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
