from __future__ import annotations

from datetime import date, datetime
from typing import Any

from health_monitor.agent.runtime import AgentDeps
from health_monitor.domain.nutrients import Nutrients


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
        phrase = _normalized_tool_phrase(phrase)
        try:
            resolution = deps.service.resolve_food_reference(
                household_id=deps.household_id,
                person_id=deps.person_id,
                phrase=phrase,
                barcode=barcode,
            )
        except ValueError:
            return {
                "resolved": False,
                "phrase": phrase,
                "barcode": barcode,
            }
        catalog = deps.service.catalog
        version = catalog.get_version(resolution.food_version_id)
        food = catalog.foods[resolution.food_id]
        return {
            "resolved": True,
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

    def search_foods(self, deps: AgentDeps, *, query: str) -> dict[str, Any]:
        normalized = query.casefold().strip()
        catalog = deps.service.catalog
        foods = [
            food
            for food in catalog.foods.values()
            if food.household_id == deps.household_id
            and not food.archived
            and deps.service._food_matches_query(food, normalized)
        ]
        foods.sort(key=lambda food: food.name.casefold())
        return {
            "query": query,
            "foods": [
                {
                    "food_id": food.id,
                    "food_name": food.name,
                    "brand": food.brand,
                    "default_version_id": food.default_version_id,
                }
                for food in foods[:20]
            ],
        }

    def get_food_details(self, deps: AgentDeps, *, phrase: str) -> dict[str, Any]:
        history = self.food_version_history(deps, phrase=phrase)
        if not history["found"]:
            return history
        return history

    def list_open_proposals(self, deps: AgentDeps) -> dict[str, Any]:
        proposals = [
            proposal
            for proposal in deps.service.proposals.proposals.values()
            if proposal.person_id == deps.person_id and proposal.status in {"draft", "needs_clarification"}
        ]
        proposals.sort(key=lambda proposal: proposal.created_at, reverse=True)
        return {
            "proposals": [
                {
                    "proposal_id": proposal.id,
                    "proposal_type": proposal.proposal_type,
                    "status": proposal.status,
                    "summary": proposal.summary,
                    "entry_count": len(proposal.entries),
                    "created_at": proposal.created_at.isoformat(),
                }
                for proposal in proposals
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

    def extract_label_text_from_attachment(
        self,
        deps: AgentDeps,
        *,
        attachment_id: str,
    ) -> dict[str, Any]:
        result = deps.service.extract_label_text_from_attachment(attachment_id=attachment_id)
        return {
            "attachment_id": str(result["attachment_id"]),
            "filename": None if result.get("filename") is None else str(result["filename"]),
            "text": str(result["text"]),
            "source": str(result["source"]),
            "confidence": float(result["confidence"]),
            "warnings": [str(item) for item in result.get("warnings", [])],
        }

    def draft_meal_proposal(
        self,
        deps: AgentDeps,
        *,
        items: list[dict[str, Any]],
        day: str,
        time: str | None = None,
        meal_type: str | None = None,
        source_text: str = "",
    ) -> dict[str, Any]:
        normalized_items = [_normalize_meal_item(item) for item in items]
        proposal = deps.service.draft_structured_meal_proposal(
            person_id=deps.person_id,
            items=normalized_items,
            day=date.fromisoformat(day),
            time_text=_normalized_time_text(time),
            meal_type=_optional_text(meal_type),
            agent_settings=deps.settings,
            source_text=source_text or "structured meal draft from agent",
        )
        return self._proposal_payload(proposal)

    def amend_meal_proposal(
        self,
        deps: AgentDeps,
        *,
        proposal_id: str,
        add: list[dict[str, Any]] | None = None,
        remove: list[dict[str, Any]] | None = None,
        set_quantity: list[dict[str, Any]] | None = None,
        source_text: str = "",
    ) -> dict[str, Any]:
        proposal = deps.service.amend_structured_meal_proposal(
            proposal_id=proposal_id,
            person_id=deps.person_id,
            add=add or [],
            remove=remove or [],
            set_quantity=set_quantity or [],
            agent_settings=deps.settings,
            source_text=source_text or "structured meal amendment from agent",
        )
        return self._proposal_payload(proposal)

    def log_weight(
        self,
        deps: AgentDeps,
        *,
        weight_kg: float,
        measured_at: str | None = None,
    ) -> dict[str, Any]:
        measured_at_local = measured_at or datetime.combine(deps.today, datetime.min.time()).replace(hour=8).isoformat()
        entry = deps.service.log_weight(
            person_id=deps.person_id,
            measured_at_local=measured_at_local,
            weight_kg=weight_kg,
            note="Criado pelo agente.",
            source="agent_chat",
        )
        return {
            "weight_entry_id": entry.id,
            "weight_kg": entry.weight_kg,
            "measured_at": entry.measured_at.isoformat(),
        }

    def repeat_meal(
        self,
        deps: AgentDeps,
        *,
        source_day: str,
        meal_type: str,
        target_time: str | None = None,
    ) -> dict[str, Any]:
        proposal = deps.service.repeat_meal(
            person_id=deps.person_id,
            source_day=date.fromisoformat(source_day),
            meal_type=meal_type,
            logged_at_local=f"{deps.today.isoformat()}T{_normalized_time_text(target_time) or '12:00:00'}",
        )
        return self._proposal_payload(proposal)

    def draft_range_estimate(
        self,
        deps: AgentDeps,
        *,
        label: str,
        low_kcal: float,
        high_kcal: float,
        meal_type: str | None = None,
        day: str | None = None,
    ) -> dict[str, Any]:
        proposal = deps.service.draft_range_estimate_proposal(
            person_id=deps.person_id,
            label=label,
            low_kcal=low_kcal,
            high_kcal=high_kcal,
            meal_type=meal_type,
            day=date.fromisoformat(day) if day else deps.today,
            agent_settings=deps.settings,
        )
        return self._proposal_payload(proposal)

    def draft_recipe_proposal(
        self,
        deps: AgentDeps,
        *,
        name: str,
        aliases: list[str] | None = None,
        ingredients: list[dict[str, Any]],
        total_cooked_weight_g: float,
        quantity_g: float | None = None,
        meal_type: str | None = None,
    ) -> dict[str, Any]:
        recipe_text = "\n".join(
            [
                f"Recipe: {name}",
                *(f"Alias: {alias}" for alias in aliases or []),
                f"Yield: {total_cooked_weight_g:g} g",
                "Ingredients:",
                *(
                    f"{float(item['quantity_g']):g}g {item['phrase']}"
                    for item in ingredients
                ),
            ]
        )
        proposal = deps.service.propose_recipe(
            household_id=deps.household_id,
            person_id=deps.person_id,
            recipe_text=recipe_text,
            logged_at_local=f"{deps.today.isoformat()}T12:00:00" if quantity_g is not None else None,
            quantity_g=quantity_g,
            meal_type=meal_type,
        )
        return self._proposal_payload(proposal)

    def draft_diary_correction_proposal(
        self,
        deps: AgentDeps,
        *,
        quantity_g: float,
        entry_id: str | None = None,
        day: str | None = None,
        phrase: str | None = None,
        source_text: str = "",
    ) -> dict[str, Any]:
        proposal = deps.service.draft_diary_correction_proposal(
            person_id=deps.person_id,
            entry_id=entry_id,
            day=date.fromisoformat(day) if day else None,
            phrase=phrase,
            quantity_g=quantity_g,
            source_text=source_text or "structured correction from agent",
            agent_settings=deps.settings,
        )
        return self._proposal_payload(proposal)

    def draft_review_note_proposal(
        self,
        deps: AgentDeps,
        *,
        body: str,
        title: str | None = None,
        starts_on: str | None = None,
        ends_on: str | None = None,
        source_text: str = "",
    ) -> dict[str, Any]:
        proposal = deps.service.draft_review_note_proposal(
            person_id=deps.person_id,
            body=body,
            title=title,
            starts_on=date.fromisoformat(starts_on) if starts_on else None,
            ends_on=date.fromisoformat(ends_on) if ends_on else None,
            source_text=source_text or "structured review note from agent",
            agent_settings=deps.settings,
        )
        return self._proposal_payload(proposal)

    def draft_profile_update_proposal(
        self,
        deps: AgentDeps,
        *,
        changes: dict[str, Any],
        source_text: str,
    ) -> dict[str, Any]:
        proposal = deps.service.propose_profile_update(
            person_id=deps.person_id,
            changes=changes,
            source_text=source_text,
        )
        return self._proposal_payload(proposal)

    def draft_goal_profile_proposal(
        self,
        deps: AgentDeps,
        *,
        starts_on: str,
        calories_kcal: float,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        fiber_g: float,
        sodium_mg: float,
        notes: str | None,
        source_text: str,
    ) -> dict[str, Any]:
        proposal = deps.service.propose_goal_profile_update(
            person_id=deps.person_id,
            starts_on=date.fromisoformat(starts_on),
            targets=Nutrients(
                calories_kcal=calories_kcal,
                protein_g=protein_g,
                carbs_g=carbs_g,
                fat_g=fat_g,
                fiber_g=fiber_g,
                sodium_mg=sodium_mg,
            ),
            notes=notes,
            source_text=source_text,
        )
        return self._proposal_payload(proposal)

    def draft_onboarding_proposal(
        self,
        deps: AgentDeps,
        *,
        session_id: str,
        household_name: str | None = None,
        household_id: str | None = None,
        person: dict[str, Any],
        targets: dict[str, Any],
        starts_on: str | None = None,
        notes: str | None = None,
        source_text: str = "",
    ) -> dict[str, Any]:
        if household_id and str(household_id).startswith("onboarding-household:"):
            raise ValueError("placeholder onboarding household ids are not valid")
        proposal = deps.service.draft_onboarding_proposal(
            session_id=session_id,
            household_name=household_name,
            household_id=household_id,
            person=person,
            targets=targets,
            starts_on=date.fromisoformat(starts_on) if starts_on is not None else deps.today,
            notes=notes,
            source_text=source_text,
        )
        return self._proposal_payload(proposal)

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


def _normalized_tool_phrase(phrase: str | None) -> str | None:
    if phrase is None:
        return None
    cleaned = str(phrase).strip()
    if not cleaned:
        return cleaned
    try:
        _quantity_g, parsed_phrase = _parse_single_gram_food_reference(cleaned)
    except ValueError:
        return cleaned
    return parsed_phrase


def _normalize_meal_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    phrase = str(
        normalized.get("phrase")
        or normalized.get("food_name")
        or normalized.get("food")
        or normalized.get("name")
        or ""
    ).strip()
    quantity_g = _coerce_float(
        normalized.get("quantity_g"),
        normalized.get("quantity"),
        normalized.get("grams"),
        normalized.get("amount_g"),
    )
    source_text = str(normalized.get("source_text") or normalized.get("text") or "").strip()
    parse_target = phrase or source_text
    parsed_phrase: str | None = None
    parsed_quantity_g: float | None = None
    if parse_target:
        try:
            parsed_quantity_g, parsed_phrase = _parse_single_gram_food_reference(parse_target)
        except ValueError:
            parsed_phrase = None
            parsed_quantity_g = None
    if not phrase and parsed_phrase:
        phrase = parsed_phrase
    phrase = _normalized_tool_phrase(phrase) or phrase
    if quantity_g is None and parsed_quantity_g is not None:
        quantity_g = parsed_quantity_g
    if phrase:
        normalized["phrase"] = phrase
    if quantity_g is not None:
        normalized["quantity_g"] = quantity_g
    if source_text:
        normalized["source_text"] = source_text
    return normalized


def _coerce_float(*values: Any) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.casefold() in {"null", "none", "undefined"}:
        return None
    return text


def _normalized_time_text(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if "T" in text:
        return text.split("T", 1)[1] or None
    return text


def _parse_single_gram_food_reference(text: str) -> tuple[float, str]:
    from health_monitor.application.service import parse_single_gram_food_reference

    return parse_single_gram_food_reference(text)
