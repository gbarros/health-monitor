from __future__ import annotations

from datetime import date
from typing import Any

from health_monitor.agent.runtime import AgentDeps


def nutrients_payload(value: Any) -> dict[str, float]:
    rounded = value.rounded()
    return {
        "calories_kcal": rounded.calories_kcal,
        "protein_g": rounded.protein_g,
        "carbs_g": rounded.carbs_g,
        "fat_g": rounded.fat_g,
        "fiber_g": rounded.fiber_g,
        "sodium_mg": rounded.sodium_mg,
    }


class NutritionAgentTools:
    def day_summary(self, deps: AgentDeps, iso_day: str) -> dict[str, Any]:
        day = date.fromisoformat(iso_day)
        summary = deps.service.day_summary(deps.person_id, day)
        entries = [
            {
                "entry_id": entry.id,
                "logged_at": entry.logged_at.isoformat(),
                "meal_type": entry.meal_type,
                "food_id": entry.food_id,
                "food_name": entry.food_name,
                "brand": entry.brand,
                "food_version_id": entry.food_version_id,
                "food_version_label": entry.food_version_label,
                "quantity_g": entry.quantity_g,
                "nutrients": nutrients_payload(entry.nutrients),
                "source": entry.source,
                "evidence_status": entry.evidence_status,
                "confidence": entry.confidence,
            }
            for meal_entries in summary.meals.values()
            for entry in meal_entries
        ]
        return {
            "day": summary.day.isoformat(),
            "totals": nutrients_payload(summary.totals),
            "target": nutrients_payload(summary.target) if summary.target is not None else None,
            "target_delta": nutrients_payload(summary.target_delta)
            if summary.target_delta is not None
            else None,
            "meals": {
                meal: [entry.id for entry in meal_entries]
                for meal, meal_entries in summary.meals.items()
            },
            "entries": entries,
            "citations": [
                {"record_type": "diary_entry", "record_id": entry["entry_id"]}
                for entry in entries
            ],
        }

    def week_summary(self, deps: AgentDeps, start_iso: str, end_iso: str) -> dict[str, Any]:
        start = date.fromisoformat(start_iso)
        end = date.fromisoformat(end_iso)
        summary = deps.service.week_summary(person_id=deps.person_id, start=start, end=end)
        return {
            "start": summary.start.isoformat(),
            "end": summary.end.isoformat(),
            "daily": {
                day.isoformat(): nutrients_payload(nutrients)
                for day, nutrients in summary.daily.items()
            },
            "daily_targets": {
                day.isoformat(): nutrients_payload(nutrients)
                for day, nutrients in summary.daily_targets.items()
            },
            "totals": nutrients_payload(summary.totals),
            "averages": nutrients_payload(summary.averages),
            "weight_delta_kg": summary.weight_delta_kg,
        }

    def weight_trend(
        self,
        deps: AgentDeps,
        start_iso: str | None = None,
        end_iso: str | None = None,
    ) -> dict[str, Any]:
        trend = deps.service.weight_trend(
            person_id=deps.person_id,
            start=date.fromisoformat(start_iso) if start_iso else None,
            end=date.fromisoformat(end_iso) if end_iso else None,
        )
        return {
            "latest_kg": trend.latest_kg,
            "delta_kg": trend.delta_kg,
            "entries": [
                {
                    "id": entry.id,
                    "measured_at": entry.measured_at.isoformat(),
                    "weight_kg": entry.weight_kg,
                    "source": entry.source,
                    "note": entry.note,
                }
                for entry in trend.entries
            ],
        }

    def food_resolution(
        self,
        deps: AgentDeps,
        *,
        phrase: str | None = None,
        barcode: str | None = None,
    ) -> dict[str, Any]:
        resolution = deps.service.resolve_food_reference(
            household_id=deps.household_id,
            person_id=deps.person_id,
            phrase=phrase,
            barcode=barcode,
        )
        catalog = deps.service.catalog
        version = catalog.get_version(resolution.food_version_id)
        food = catalog.foods[resolution.food_id]
        return {
            "food_id": food.id,
            "food_version_id": version.id,
            "food_name": food.name,
            "brand": food.brand,
            "version_label": version.label,
            "reason": resolution.reason,
            "confidence": resolution.confidence,
            "nutrients_per_100g": nutrients_payload(version.nutrients_per_100g),
        }

    def food_lookup(
        self,
        deps: AgentDeps,
        *,
        phrase: str | None = None,
        barcode: str | None = None,
    ) -> dict[str, Any]:
        candidates = deps.service.lookup_food_candidates(
            household_id=deps.household_id,
            person_id=deps.person_id,
            phrase=phrase,
            barcode=barcode,
        )
        return {
            "candidates": [
                {
                    "candidate_id": candidate.id,
                    "source_type": candidate.source_type,
                    "source_name": candidate.source_name,
                    "source_id": candidate.source_id,
                    "source_url": candidate.source_url,
                    "food_id": candidate.food_id,
                    "food_version_id": candidate.food_version_id,
                    "food_name": candidate.product_name,
                    "brand": candidate.brand,
                    "barcode": candidate.barcode,
                    "serving_size_g": candidate.serving_size_g,
                    "nutrients_per_100g": nutrients_payload(candidate.nutrients_per_100g),
                    "confidence": candidate.confidence,
                    "warnings": list(candidate.warnings),
                }
                for candidate in candidates
            ]
        }

    def food_version_history(self, deps: AgentDeps, *, phrase: str) -> dict[str, Any]:
        normalized = phrase.casefold().strip()
        catalog = deps.service.catalog
        matches = [
            food
            for food in catalog.foods.values()
            if food.household_id == deps.household_id
            and not food.archived
            and deps.service._food_matches_query(food, normalized)
        ]
        matches.sort(
            key=lambda food: (
                0 if normalized in food.name.casefold() else 1,
                food.name.casefold(),
                food.brand.casefold() if food.brand is not None else "",
            )
        )
        if not matches:
            return {"phrase": phrase, "found": False, "versions": []}
        food = matches[0]
        versions = [
            version
            for version in catalog.versions.values()
            if version.food_id == food.id and not version.archived
        ]
        versions.sort(key=lambda version: version.created_at)
        entries = []
        for entry in deps.service.diary.entries.values():
            if entry.person_id != deps.person_id or entry.deleted_at is not None:
                continue
            version = catalog.versions.get(entry.food_version_id)
            if version is None or version.food_id != food.id:
                continue
            entries.append((entry, version))
        entries.sort(key=lambda pair: pair[0].logged_at, reverse=True)
        return {
            "phrase": phrase,
            "found": True,
            "food_id": food.id,
            "food_name": food.name,
            "brand": food.brand,
            "default_version_id": food.default_version_id,
            "versions": [
                {
                    "food_version_id": version.id,
                    "label": version.label,
                    "source": version.source,
                    "serving_size_g": version.serving_size_g,
                    "confidence": version.confidence,
                    "created_at": version.created_at.isoformat(),
                    "is_default": version.id == food.default_version_id,
                    "nutrients_per_100g": nutrients_payload(version.nutrients_per_100g),
                }
                for version in versions
            ],
            "latest_entry": {
                "entry_id": entries[0][0].id,
                "logged_at": entries[0][0].logged_at.isoformat(),
                "quantity_g": entries[0][0].quantity_g,
                "food_version_id": entries[0][1].id,
                "food_version_label": entries[0][1].label,
            }
            if entries
            else None,
        }

    def draft_text_meal_proposal(
        self,
        deps: AgentDeps,
        *,
        logged_at_local: str,
        text: str,
    ) -> dict[str, Any]:
        proposal = deps.service.propose_text_meal(
            person_id=deps.person_id,
            logged_at_local=logged_at_local,
            text=text,
            agent_settings={**deps.settings, "agent_runtime": "deterministic"},
        )
        return self._proposal_payload(proposal)

    def draft_diary_correction_proposal(
        self,
        deps: AgentDeps,
        *,
        message: str,
    ) -> dict[str, Any]:
        response = deps.service.chat(
            person_id=deps.person_id,
            message=message,
            today=deps.today,
            agent_settings={**deps.settings, "agent_runtime": "deterministic"},
        )
        if response.proposal_id is None:
            return {
                "proposal_id": None,
                "proposal_type": None,
                "proposal_status": None,
                "summary": response.message,
                "mutation_applied": False,
            }
        return self._proposal_payload(deps.service.get_proposal(response.proposal_id))

    def draft_review_note_proposal(
        self,
        deps: AgentDeps,
        *,
        message: str,
    ) -> dict[str, Any]:
        response = deps.service.chat(
            person_id=deps.person_id,
            message=message,
            today=deps.today,
            agent_settings={**deps.settings, "agent_runtime": "deterministic"},
        )
        if response.proposal_id is None:
            return {
                "proposal_id": None,
                "proposal_type": None,
                "proposal_status": None,
                "summary": response.message,
                "mutation_applied": False,
            }
        return self._proposal_payload(deps.service.get_proposal(response.proposal_id))

    def _proposal_payload(self, proposal: Any) -> dict[str, Any]:
        return {
            "proposal_id": proposal.id,
            "proposal_type": proposal.proposal_type,
            "proposal_status": proposal.status,
            "summary": proposal.summary,
            "totals": nutrients_payload(proposal.totals),
            "entry_count": len(proposal.entries),
            "evidence_count": len(proposal.evidence),
            "mutation_applied": False,
            "payload": dict(proposal.payload),
            "entries": [
                {
                    "entry_id": entry.id,
                    "logged_at": entry.logged_at.isoformat(),
                    "meal_type": entry.meal_type,
                    "food_version_id": entry.food_version_id,
                    "quantity_g": entry.quantity_g,
                    "source": entry.source,
                }
                for entry in proposal.entries
            ],
        }
