from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from health_monitor.domain.diary import Diary, DiaryEntry
from health_monitor.domain.food_resolution import FoodResolution, FoodResolver
from health_monitor.domain.foods import BarcodeAssociation, Food, FoodAlias, FoodCatalog, FoodVersion
from health_monitor.domain.nutrients import Nutrients
from health_monitor.domain.proposals import CreateDiaryEntriesProposal, ProposalService
from health_monitor.lookup.estimates import FoodEstimator, NutritionEstimate
from health_monitor.persistence.sqlite_state import StateRepository


@dataclass(frozen=True)
class Household:
    id: str
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Person:
    id: str
    household_id: str
    name: str
    timezone: str
    birth_date: date | None = None
    sex: str | None = None
    height_cm: float | None = None
    activity_level: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class GoalProfile:
    id: str
    person_id: str
    starts_on: date
    targets: Nutrients
    notes: str | None = None
    ends_on: date | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class DaySummaryEntry:
    id: str
    logged_at: datetime
    meal_type: str
    food_id: str
    food_name: str
    brand: str | None
    food_version_id: str
    food_version_label: str
    quantity_g: float
    nutrients: Nutrients
    source: str


@dataclass(frozen=True)
class DaySummary:
    person_id: str
    day: date
    totals: Nutrients
    meals: dict[str, list[DaySummaryEntry]]
    target: Nutrients | None = None
    target_delta: Nutrients | None = None


@dataclass(frozen=True)
class WeightEntry:
    id: str
    person_id: str
    measured_at: datetime
    weight_kg: float
    note: str | None
    source: str


@dataclass(frozen=True)
class WeightTrend:
    person_id: str
    entries: tuple[WeightEntry, ...]
    latest_kg: float | None
    delta_kg: float | None


@dataclass(frozen=True)
class WeekSummary:
    person_id: str
    start: date
    end: date
    daily: dict[date, Nutrients]
    daily_targets: dict[date, Nutrients]
    totals: Nutrients
    averages: Nutrients
    weight_delta_kg: float | None


@dataclass(frozen=True)
class AgentRun:
    id: str
    person_id: str
    input_text: str
    settings: dict[str, Any]
    status: str
    proposal_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ParsedMealItem:
    phrase: str
    quantity_g: float
    source_text: str
    evidence: dict[str, object]


@dataclass(frozen=True)
class ParsedNutritionLabel:
    food_name: str
    brand: str | None
    serving_size_g: float
    nutrients_per_100g: Nutrients
    barcode: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedRecipeIngredient:
    phrase: str
    quantity_g: float
    source_text: str


@dataclass(frozen=True)
class ParsedRecipe:
    name: str
    yield_g: float
    ingredients: tuple[ParsedRecipeIngredient, ...]


class HealthMonitorService:
    def __init__(
        self,
        repository: StateRepository | None = None,
        estimator: FoodEstimator | None = None,
    ) -> None:
        self.repository = repository
        self.estimator = estimator
        self.households: dict[str, Household] = {}
        self.people: dict[str, Person] = {}
        self.goal_profiles: dict[str, GoalProfile] = {}
        self.catalog = FoodCatalog()
        self.diary = Diary(self.catalog)
        self.weights: dict[str, WeightEntry] = {}
        self.resolver = FoodResolver(self.catalog)
        self.proposals = ProposalService(self.diary)
        self.agent_runs: dict[str, AgentRun] = {}
        self._ids: dict[str, int] = {}
        if self.repository is not None:
            snapshot = self.repository.load()
            if snapshot is not None:
                self._restore_snapshot(snapshot)

    def create_household(self, *, name: str) -> Household:
        household = Household(id=self._next_id("household"), name=name)
        self.households[household.id] = household
        self._persist()
        return household

    def create_person(
        self,
        *,
        household_id: str,
        name: str,
        timezone: str,
        birth_date: date | None = None,
        sex: str | None = None,
        height_cm: float | None = None,
        activity_level: str | None = None,
    ) -> Person:
        self._require_household(household_id)
        ZoneInfo(timezone)
        person = Person(
            id=self._next_id("person"),
            household_id=household_id,
            name=name,
            timezone=timezone,
            birth_date=birth_date,
            sex=sex,
            height_cm=float(height_cm) if height_cm is not None else None,
            activity_level=activity_level,
        )
        self.people[person.id] = person
        self._persist()
        return person

    def people_for_household(self, household_id: str) -> tuple[Person, ...]:
        self._require_household(household_id)
        people = [person for person in self.people.values() if person.household_id == household_id]
        people.sort(key=lambda person: person.created_at)
        return tuple(people)

    def create_goal_profile(
        self,
        *,
        person_id: str,
        starts_on: date,
        targets: Nutrients,
        notes: str | None = None,
    ) -> GoalProfile:
        self._require_person(person_id)
        if targets.calories_kcal <= 0:
            raise ValueError("daily calorie target must be positive")
        updated_profiles: dict[str, GoalProfile] = {}
        previous_day = starts_on - timedelta(days=1)
        for profile in self.goal_profiles.values():
            if profile.person_id != person_id:
                updated_profiles[profile.id] = profile
                continue
            if profile.starts_on < starts_on and (
                profile.ends_on is None or profile.ends_on >= starts_on
            ):
                updated_profiles[profile.id] = GoalProfile(
                    id=profile.id,
                    person_id=profile.person_id,
                    starts_on=profile.starts_on,
                    targets=profile.targets,
                    notes=profile.notes,
                    ends_on=previous_day,
                    created_at=profile.created_at,
                )
            else:
                updated_profiles[profile.id] = profile
        self.goal_profiles = updated_profiles
        profile = GoalProfile(
            id=self._next_id("goal_profile"),
            person_id=person_id,
            starts_on=starts_on,
            targets=targets,
            notes=notes,
        )
        self.goal_profiles[profile.id] = profile
        self._persist()
        return profile

    def active_goal_profile(self, *, person_id: str, day: date) -> GoalProfile | None:
        self._require_person(person_id)
        candidates = [
            profile
            for profile in self.goal_profiles.values()
            if profile.person_id == person_id
            and profile.starts_on <= day
            and (profile.ends_on is None or profile.ends_on >= day)
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda profile: profile.starts_on, reverse=True)
        return candidates[0]

    def create_food_with_version(
        self,
        *,
        household_id: str,
        name: str,
        brand: str | None,
        version_label: str,
        nutrients_per_100g: Nutrients,
        source: str,
        aliases: list[str] | None = None,
        barcode: str | None = None,
        serving_size_g: float | None = None,
    ) -> tuple[Food, FoodVersion]:
        food, version = self._create_food_with_version(
            household_id=household_id,
            name=name,
            brand=brand,
            version_label=version_label,
            nutrients_per_100g=nutrients_per_100g,
            source=source,
            aliases=aliases,
            barcode=barcode,
            serving_size_g=serving_size_g,
        )
        self._persist()
        return food, version

    def _create_food_with_version(
        self,
        *,
        household_id: str,
        name: str,
        brand: str | None,
        version_label: str,
        nutrients_per_100g: Nutrients,
        source: str,
        aliases: list[str] | None = None,
        barcode: str | None = None,
        serving_size_g: float | None = None,
        food_id: str | None = None,
        version_id: str | None = None,
    ) -> tuple[Food, FoodVersion]:
        self._require_household(household_id)
        food = self.catalog.add_food(
            Food(
                id=food_id or self._next_id("food"),
                household_id=household_id,
                name=name,
                brand=brand,
            )
        )
        version = self.catalog.add_version(
            FoodVersion(
                id=version_id or self._next_id("food_version"),
                food_id=food.id,
                label=version_label,
                nutrients_per_100g=nutrients_per_100g,
                source=source,
                serving_size_g=serving_size_g,
            ),
            make_default=True,
        )
        food = self.catalog.foods[food.id]
        for phrase in aliases or []:
            self.catalog.add_alias(
                FoodAlias(
                    id=self._next_id("food_alias"),
                    household_id=household_id,
                    phrase=phrase,
                    food_id=food.id,
                )
            )
        if barcode is not None:
            self.catalog.associate_barcode(
                BarcodeAssociation(
                    id=self._next_id("barcode_association"),
                    household_id=household_id,
                    barcode=barcode,
                    food_id=food.id,
                    food_version_id=version.id,
                    source=source,
                    confirmed_at=datetime.now(timezone.utc),
                )
            )
        return food, version

    def resolve_food_reference(
        self,
        *,
        household_id: str,
        person_id: str,
        phrase: str | None = None,
        barcode: str | None = None,
    ) -> FoodResolution:
        self._require_household(household_id)
        self._require_person(person_id)
        resolution = None
        if barcode is not None:
            resolution = self.resolver.resolve_barcode(barcode)
        if resolution is None and phrase is not None:
            resolution = self.resolver.resolve_phrase(phrase, person_id=person_id)
        if resolution is None:
            raise ValueError("food reference could not be resolved")
        food = self.catalog.foods[resolution.food_id]
        if food.household_id != household_id:
            raise ValueError("resolved food belongs to a different household")
        return resolution

    def log_diary_entry(
        self,
        *,
        person_id: str,
        logged_at_local: str,
        food_version_id: str,
        quantity_g: float,
        source: str,
        meal_type: str | None = None,
    ) -> DiaryEntry:
        person = self._require_person(person_id)
        logged_at = self._parse_person_datetime(logged_at_local, person)
        entry = DiaryEntry(
            id=self._next_id("diary_entry"),
            person_id=person_id,
            logged_at=logged_at,
            meal_type=meal_type or infer_meal_type(logged_at),
            food_version_id=food_version_id,
            quantity_g=quantity_g,
            source=source,
        )
        created = self.diary.add_entry(entry)
        self._persist()
        return created

    def update_diary_entry(
        self,
        *,
        entry_id: str,
        logged_at_local: str | None = None,
        food_version_id: str | None = None,
        quantity_g: float | None = None,
        meal_type: str | None = None,
    ) -> DiaryEntry:
        entry = self.diary.entries[entry_id]
        person = self._require_person(entry.person_id)
        logged_at = (
            self._parse_person_datetime(logged_at_local, person)
            if logged_at_local is not None
            else None
        )
        updated = self.diary.update_entry(
            entry_id,
            logged_at=logged_at,
            meal_type=meal_type,
            food_version_id=food_version_id,
            quantity_g=quantity_g,
        )
        self._persist()
        return updated

    def delete_diary_entry(self, entry_id: str) -> DiaryEntry:
        deleted = self.diary.delete_entry(
            entry_id,
            deleted_at=datetime.now(timezone.utc),
        )
        self._persist()
        return deleted

    def restore_diary_entry(self, entry_id: str) -> DiaryEntry:
        restored = self.diary.restore_entry(entry_id)
        self._persist()
        return restored

    def day_summary(self, person_id: str, day: date) -> DaySummary:
        self._require_person(person_id)
        meals: dict[str, list[DaySummaryEntry]] = {}
        totals = Nutrients()
        for entry in self.diary.entries_for_day(person_id, day):
            version = self.catalog.get_version(entry.food_version_id)
            food = self.catalog.foods[version.food_id]
            nutrients = version.nutrients_per_100g.scale(entry.quantity_g / 100)
            totals += nutrients
            meals.setdefault(entry.meal_type, []).append(
                DaySummaryEntry(
                    id=entry.id,
                    logged_at=entry.logged_at,
                    meal_type=entry.meal_type,
                    food_id=food.id,
                    food_name=food.name,
                    brand=food.brand,
                    food_version_id=version.id,
                    food_version_label=version.label,
                    quantity_g=entry.quantity_g,
                    nutrients=nutrients,
                    source=entry.source,
                )
            )
        target_profile = self.active_goal_profile(person_id=person_id, day=day)
        target = target_profile.targets if target_profile is not None else None
        target_delta = totals + target.scale(-1) if target is not None else None
        return DaySummary(
            person_id=person_id,
            day=day,
            totals=totals,
            meals=meals,
            target=target,
            target_delta=target_delta,
        )

    def log_weight(
        self,
        *,
        person_id: str,
        measured_at_local: str,
        weight_kg: float,
        note: str | None,
        source: str,
    ) -> WeightEntry:
        person = self._require_person(person_id)
        measured_at = self._parse_person_datetime(measured_at_local, person)
        entry = WeightEntry(
            id=self._next_id("weight_entry"),
            person_id=person_id,
            measured_at=measured_at,
            weight_kg=round(float(weight_kg), 2),
            note=note,
            source=source,
        )
        self.weights[entry.id] = entry
        self._persist()
        return entry

    def weight_trend(
        self,
        *,
        person_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> WeightTrend:
        self._require_person(person_id)
        entries = [
            entry
            for entry in self.weights.values()
            if entry.person_id == person_id
            and (start is None or entry.measured_at.date() >= start)
            and (end is None or entry.measured_at.date() <= end)
        ]
        entries.sort(key=lambda entry: entry.measured_at)
        latest = entries[-1].weight_kg if entries else None
        delta = round(entries[-1].weight_kg - entries[0].weight_kg, 2) if len(entries) >= 2 else None
        return WeightTrend(
            person_id=person_id,
            entries=tuple(entries),
            latest_kg=latest,
            delta_kg=delta,
        )

    def week_summary(self, *, person_id: str, start: date, end: date) -> WeekSummary:
        self._require_person(person_id)
        if end < start:
            raise ValueError("end date must be on or after start date")
        daily: dict[date, Nutrients] = {}
        daily_targets: dict[date, Nutrients] = {}
        totals = Nutrients()
        current = start
        day_count = 0
        while current <= end:
            day_summary = self.day_summary(person_id, current)
            day_total = day_summary.totals
            daily[current] = day_total
            if day_summary.target is not None:
                daily_targets[current] = day_summary.target
            totals += day_total
            day_count += 1
            current += timedelta(days=1)
        trend = self.weight_trend(person_id=person_id, start=start, end=end)
        return WeekSummary(
            person_id=person_id,
            start=start,
            end=end,
            daily=daily,
            daily_targets=daily_targets,
            totals=totals,
            averages=totals.scale(1 / day_count if day_count else 0),
            weight_delta_kg=trend.delta_kg,
        )

    def propose_text_meal(
        self,
        *,
        person_id: str,
        logged_at_local: str,
        text: str,
        agent_settings: dict[str, Any] | None = None,
    ) -> CreateDiaryEntriesProposal:
        settings = dict(agent_settings or {})
        person = self._require_person(person_id)
        logged_at = self._parse_person_datetime(logged_at_local, person)
        parsed_logged_at, items = parse_text_meal_items(text, default_logged_at=logged_at)
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=text,
            settings=settings,
            status="started",
        )
        self.agent_runs[run.id] = run
        entries: list[DiaryEntry] = []
        evidence: list[dict[str, object]] = []
        estimated_food_versions: list[dict[str, object]] = []
        totals = Nutrients()
        for item in items:
            resolution: FoodResolution | None = None
            estimate: NutritionEstimate | None = None
            try:
                resolution = self.resolve_food_reference(
                    household_id=person.household_id,
                    person_id=person.id,
                    phrase=item.phrase,
                )
                version = self.catalog.get_version(resolution.food_version_id)
                food_version_id = resolution.food_version_id
                source = "agent_proposal"
                resolution_reason = resolution.reason
                confidence = resolution.confidence
            except ValueError:
                if not settings.get("external_lookup", True) or self.estimator is None:
                    raise
                estimate = self.estimator.estimate(item.phrase)
                if estimate is None:
                    raise ValueError(f"food reference could not be resolved or estimated: {item.phrase}")
                food_id = self._next_id("food")
                food_version_id = self._next_id("food_version")
                version = FoodVersion(
                    id=food_version_id,
                    food_id=food_id,
                    label="model estimate",
                    nutrients_per_100g=estimate.nutrients_per_100g,
                    source=estimate.source,
                )
                estimated_food_versions.append(
                    {
                        "food_id": food_id,
                        "food_version_id": food_version_id,
                        "household_id": person.household_id,
                        "food_name": estimate.food_name,
                        "phrase": item.phrase,
                        "version_label": "model estimate",
                        "nutrients_per_100g": nutrients_to_snapshot(
                            estimate.nutrients_per_100g.rounded()
                        ),
                        "source": estimate.source,
                        "confidence": estimate.confidence,
                        "notes": estimate.notes,
                    }
                )
                source = "agent_estimate_proposal"
                resolution_reason = "model_estimate"
                confidence = estimate.confidence
            quantity_g = item.quantity_g
            if item.evidence.get("quantity_basis") == "serving_count":
                if version.serving_size_g is None:
                    raise ValueError(f"food version has no serving size: {version.id}")
                quantity_g = float(item.evidence["serving_count"]) * version.serving_size_g
            entry = DiaryEntry(
                id=self._next_id("diary_entry"),
                person_id=person_id,
                logged_at=parsed_logged_at,
                meal_type=infer_meal_type(parsed_logged_at),
                food_version_id=food_version_id,
                quantity_g=quantity_g,
                source=source,
            )
            entries.append(entry)
            totals += version.nutrients_per_100g.scale(quantity_g / 100)
            source_type = "model_estimate" if estimate is not None else "local_food"
            evidence.append(
                {
                    "source_type": source_type,
                    "source_text": item.source_text,
                    "phrase": item.phrase,
                    "quantity_g": quantity_g,
                    "resolution_reason": resolution_reason,
                    "confidence": confidence,
                    "food_version_id": food_version_id,
                    **item.evidence,
                }
            )
        proposal_type = "diary_entries_with_estimates" if estimated_food_versions else "diary_entries"
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=tuple(entries),
                proposal_type=proposal_type,
                summary=f"{len(entries)} diary entries drafted from text meal",
                payload={"estimated_food_versions": estimated_food_versions},
                totals=totals,
                evidence=tuple(evidence),
                source_agent_run_id=run.id,
            )
        )
        self.agent_runs[run.id] = AgentRun(
            id=run.id,
            person_id=run.person_id,
            input_text=run.input_text,
            settings=run.settings,
            status="proposal_created",
            proposal_id=proposal.id,
            created_at=run.created_at,
        )
        self._persist()
        return proposal

    def propose_label_scan(
        self,
        *,
        household_id: str,
        person_id: str,
        table_text: str,
        set_as_default: bool = True,
    ) -> CreateDiaryEntriesProposal:
        self._require_household(household_id)
        self._require_person(person_id)
        parsed = parse_nutrition_label_text(table_text)
        payload = {
            "household_id": household_id,
            "food_name": parsed.food_name,
            "brand": parsed.brand,
            "version_label": "label scan",
            "nutrients_per_100g": nutrients_to_snapshot(parsed.nutrients_per_100g.rounded()),
            "serving_size_g": parsed.serving_size_g,
            "barcode": parsed.barcode,
            "set_as_default": set_as_default,
            "source": "label_scan",
        }
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=(),
                proposal_type="food_version_from_label",
                summary=f"Food version drafted from label: {parsed.food_name}",
                payload=payload,
                evidence=(
                    {
                        "source_type": "nutrition_label_text",
                        "raw_text": table_text,
                        "warnings": list(parsed.warnings),
                    },
                ),
            )
        )
        self._persist()
        return proposal

    def propose_recipe(
        self,
        *,
        household_id: str,
        person_id: str,
        recipe_text: str,
    ) -> CreateDiaryEntriesProposal:
        self._require_household(household_id)
        self._require_person(person_id)
        parsed = parse_recipe_text(recipe_text)
        ingredient_payloads: list[dict[str, object]] = []
        total = Nutrients()
        for ingredient in parsed.ingredients:
            resolution = self.resolve_food_reference(
                household_id=household_id,
                person_id=person_id,
                phrase=ingredient.phrase,
            )
            version = self.catalog.get_version(resolution.food_version_id)
            nutrients = version.nutrients_per_100g.scale(ingredient.quantity_g / 100)
            total += nutrients
            ingredient_payloads.append(
                {
                    "source_text": ingredient.source_text,
                    "phrase": ingredient.phrase,
                    "quantity_g": ingredient.quantity_g,
                    "food_version_id": version.id,
                    "resolution_reason": resolution.reason,
                    "confidence": resolution.confidence,
                    "nutrients": nutrients_to_snapshot(nutrients.rounded()),
                }
            )
        nutrients_per_100g = total.scale(100 / parsed.yield_g).rounded()
        payload = {
            "household_id": household_id,
            "food_name": parsed.name,
            "brand": None,
            "version_label": "recipe batch",
            "yield_g": parsed.yield_g,
            "nutrients_per_100g": nutrients_to_snapshot(nutrients_per_100g),
            "ingredients": ingredient_payloads,
            "source": "recipe",
        }
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=(),
                proposal_type="recipe_food_version",
                summary=f"Recipe food version drafted: {parsed.name}",
                payload=payload,
                evidence=(
                    {
                        "source_type": "recipe_text",
                        "raw_text": recipe_text,
                        "ingredient_count": len(parsed.ingredients),
                    },
                ),
            )
        )
        self._persist()
        return proposal

    def get_proposal(self, proposal_id: str) -> CreateDiaryEntriesProposal:
        return self.proposals.proposals[proposal_id]

    def get_agent_run(self, agent_run_id: str) -> AgentRun:
        return self.agent_runs[agent_run_id]

    def confirm_proposal(self, proposal_id: str) -> CreateDiaryEntriesProposal:
        proposal = self.proposals.proposals[proposal_id]
        if proposal.proposal_type == "food_version_from_label":
            applied = self._apply_food_version_proposal(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        if proposal.proposal_type == "recipe_food_version":
            applied = self._apply_recipe_food_version_proposal(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        if proposal.proposal_type == "diary_entries_with_estimates":
            applied = self._apply_diary_entries_with_estimates(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        proposal = self.proposals.confirm_and_apply(proposal_id)
        self._persist()
        return proposal

    def reject_proposal(self, proposal_id: str) -> CreateDiaryEntriesProposal:
        proposal = self.proposals.reject(proposal_id)
        self._persist()
        return proposal

    def _next_id(self, prefix: str) -> str:
        next_number = self._ids.get(prefix, 1)
        self._ids[prefix] = next_number + 1
        return f"{prefix}_{next_number}"

    def _require_household(self, household_id: str) -> Household:
        try:
            return self.households[household_id]
        except KeyError as exc:
            raise ValueError(f"unknown household_id: {household_id}") from exc

    def _require_person(self, person_id: str) -> Person:
        try:
            return self.people[person_id]
        except KeyError as exc:
            raise ValueError(f"unknown person_id: {person_id}") from exc

    def _parse_person_datetime(self, value: str, person: Person) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=ZoneInfo(person.timezone))
        return parsed.astimezone(ZoneInfo(person.timezone))

    def _apply_food_version_proposal(
        self,
        proposal: CreateDiaryEntriesProposal,
    ) -> CreateDiaryEntriesProposal:
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        payload = proposal.payload
        food, version = self.create_food_with_version(
            household_id=str(payload["household_id"]),
            name=str(payload["food_name"]),
            brand=payload.get("brand") if payload.get("brand") is None else str(payload["brand"]),
            version_label=str(payload["version_label"]),
            nutrients_per_100g=nutrients_from_snapshot(
                dict(payload["nutrients_per_100g"])
            ),
            source=str(payload.get("source", "label_scan")),
            aliases=[str(payload["food_name"]).casefold()],
            barcode=payload.get("barcode") if payload.get("barcode") is None else str(payload["barcode"]),
            serving_size_g=float(payload["serving_size_g"]),
        )
        applied_ids = [food.id, version.id]
        barcode = payload.get("barcode")
        if barcode is not None:
            association = self.catalog.resolve_barcode(str(barcode))
            if association is not None:
                applied_ids.append(association.id)
        return CreateDiaryEntriesProposal(
            id=proposal.id,
            person_id=proposal.person_id,
            entries=proposal.entries,
            proposal_type=proposal.proposal_type,
            status="applied",
            summary=proposal.summary,
            payload=proposal.payload,
            totals=proposal.totals,
            evidence=proposal.evidence,
            source_agent_run_id=proposal.source_agent_run_id,
            applied_record_ids=tuple(applied_ids),
            created_at=proposal.created_at,
        )

    def _apply_recipe_food_version_proposal(
        self,
        proposal: CreateDiaryEntriesProposal,
    ) -> CreateDiaryEntriesProposal:
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        payload = proposal.payload
        food, version = self._create_food_with_version(
            household_id=str(payload["household_id"]),
            name=str(payload["food_name"]),
            brand=payload.get("brand") if payload.get("brand") is None else str(payload["brand"]),
            version_label=str(payload["version_label"]),
            nutrients_per_100g=nutrients_from_snapshot(
                dict(payload["nutrients_per_100g"])
            ),
            source=str(payload.get("source", "recipe")),
            aliases=[str(payload["food_name"]).casefold()],
            barcode=None,
            serving_size_g=None,
        )
        return CreateDiaryEntriesProposal(
            id=proposal.id,
            person_id=proposal.person_id,
            entries=proposal.entries,
            proposal_type=proposal.proposal_type,
            status="applied",
            summary=proposal.summary,
            payload=proposal.payload,
            totals=proposal.totals,
            evidence=proposal.evidence,
            source_agent_run_id=proposal.source_agent_run_id,
            applied_record_ids=(food.id, version.id),
            created_at=proposal.created_at,
        )

    def _apply_diary_entries_with_estimates(
        self,
        proposal: CreateDiaryEntriesProposal,
    ) -> CreateDiaryEntriesProposal:
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        applied_record_ids: list[str] = []
        for estimate in proposal.payload.get("estimated_food_versions", []):
            estimate_payload = dict(estimate)
            food, version = self._create_food_with_version(
                household_id=str(estimate_payload["household_id"]),
                name=str(estimate_payload["food_name"]),
                brand=None,
                version_label=str(estimate_payload["version_label"]),
                nutrients_per_100g=nutrients_from_snapshot(
                    dict(estimate_payload["nutrients_per_100g"])
                ),
                source=str(estimate_payload["source"]),
                aliases=[str(estimate_payload["phrase"])],
                barcode=None,
                serving_size_g=None,
                food_id=str(estimate_payload["food_id"]),
                version_id=str(estimate_payload["food_version_id"]),
            )
            applied_record_ids.extend([food.id, version.id])
        for entry in proposal.entries:
            self.diary.add_entry(entry)
            applied_record_ids.append(entry.id)
        return CreateDiaryEntriesProposal(
            id=proposal.id,
            person_id=proposal.person_id,
            entries=proposal.entries,
            proposal_type=proposal.proposal_type,
            status="applied",
            summary=proposal.summary,
            payload=proposal.payload,
            totals=proposal.totals,
            evidence=proposal.evidence,
            source_agent_run_id=proposal.source_agent_run_id,
            applied_record_ids=tuple(applied_record_ids),
            created_at=proposal.created_at,
        )

    def _persist(self) -> None:
        if self.repository is not None:
            self.repository.save(self._snapshot())

    def _snapshot(self) -> dict[str, Any]:
        return {
            "version": 1,
            "ids": self._ids,
            "households": [household_to_snapshot(item) for item in self.households.values()],
            "people": [person_to_snapshot(item) for item in self.people.values()],
            "goal_profiles": [
                goal_profile_to_snapshot(item) for item in self.goal_profiles.values()
            ],
            "foods": [food_to_snapshot(item) for item in self.catalog.foods.values()],
            "food_versions": [
                food_version_to_snapshot(item) for item in self.catalog.versions.values()
            ],
            "food_aliases": [food_alias_to_snapshot(item) for item in self.catalog.aliases.values()],
            "barcode_associations": [
                barcode_association_to_snapshot(item)
                for item in self.catalog.barcode_associations.values()
            ],
            "diary_entries": [diary_entry_to_snapshot(item) for item in self.diary.entries.values()],
            "weight_entries": [weight_entry_to_snapshot(item) for item in self.weights.values()],
            "proposals": [
                proposal_to_snapshot(item) for item in self.proposals.proposals.values()
            ],
            "agent_runs": [agent_run_to_snapshot(item) for item in self.agent_runs.values()],
        }

    def _restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._ids = {key: int(value) for key, value in snapshot.get("ids", {}).items()}
        self.households = {
            item["id"]: household_from_snapshot(item) for item in snapshot.get("households", [])
        }
        self.people = {item["id"]: person_from_snapshot(item) for item in snapshot.get("people", [])}
        self.goal_profiles = {
            item["id"]: goal_profile_from_snapshot(item)
            for item in snapshot.get("goal_profiles", [])
        }
        self.catalog = FoodCatalog()
        for item in snapshot.get("foods", []):
            self.catalog.add_food(food_from_snapshot(item))
        for item in snapshot.get("food_versions", []):
            version = food_version_from_snapshot(item)
            self.catalog.add_version(version)
        for food_id, food in list(self.catalog.foods.items()):
            if food.default_version_id is not None:
                self.catalog.set_default_version(food_id, food.default_version_id)
        for item in snapshot.get("food_aliases", []):
            self.catalog.add_alias(food_alias_from_snapshot(item))
        for item in snapshot.get("barcode_associations", []):
            self.catalog.associate_barcode(barcode_association_from_snapshot(item))
        self.diary = Diary(self.catalog)
        for item in snapshot.get("diary_entries", []):
            self.diary.add_entry(diary_entry_from_snapshot(item))
        self.weights = {
            item["id"]: weight_entry_from_snapshot(item)
            for item in snapshot.get("weight_entries", [])
        }
        self.resolver = FoodResolver(self.catalog)
        self.proposals = ProposalService(self.diary)
        for item in snapshot.get("proposals", []):
            proposal = proposal_from_snapshot(item)
            self.proposals.proposals[proposal.id] = proposal
        self.agent_runs = {
            item["id"]: agent_run_from_snapshot(item) for item in snapshot.get("agent_runs", [])
        }


def infer_meal_type(logged_at: datetime) -> str:
    hour = logged_at.hour
    if 5 <= hour < 11:
        return "breakfast"
    if 11 <= hour < 15:
        return "lunch"
    if 15 <= hour < 18:
        return "snack"
    if 18 <= hour < 23:
        return "dinner"
    return "late"


def parse_single_gram_food_reference(text: str) -> tuple[float, str]:
    match = re.fullmatch(r"\s*(\d+(?:[,.]\d+)?)\s*g(?:ramas?)?\s+(.+?)\s*", text, re.I)
    if match is None:
        raise ValueError("expected a single food reference like '100g queijo'")
    quantity = float(match.group(1).replace(",", "."))
    phrase = match.group(2).strip()
    return quantity, phrase


def parse_text_meal_items(text: str, *, default_logged_at: datetime) -> tuple[datetime, list[ParsedMealItem]]:
    fragments = [fragment.strip() for fragment in re.split(r"[,;]\s*", text) if fragment.strip()]
    if not fragments:
        raise ValueError("text meal is empty")

    logged_at = default_logged_at
    first_time = parse_time_prefix(fragments[0], default_logged_at=default_logged_at)
    if first_time is not None:
        logged_at = first_time
        fragments = fragments[1:]

    items: list[ParsedMealItem] = []
    for fragment in fragments:
        items.append(parse_text_meal_item(fragment))
    if not items:
        raise ValueError("text meal has no food items")
    return logged_at, items


def parse_time_prefix(fragment: str, *, default_logged_at: datetime) -> datetime | None:
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|h)?", fragment, re.I)
    if match is None:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    marker = (match.group(3) or "").casefold()
    if marker == "pm" and hour < 12:
        hour += 12
    if marker == "am" and hour == 12:
        hour = 0
    if marker == "h" and hour == 24:
        hour = 0
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"invalid meal time: {fragment}")
    return default_logged_at.replace(hour=hour, minute=minute, second=0, microsecond=0)


def parse_text_meal_item(fragment: str) -> ParsedMealItem:
    grams = re.fullmatch(r"(\d+(?:[,.]\d+)?)\s*g(?:ramas?)?\s+(.+)", fragment, re.I)
    if grams is not None:
        quantity_g = float(grams.group(1).replace(",", "."))
        phrase = normalize_food_phrase(grams.group(2))
        return ParsedMealItem(
            phrase=phrase,
            quantity_g=quantity_g,
            source_text=fragment,
            evidence={"quantity_basis": "grams"},
        )

    count = re.fullmatch(r"(\d+(?:[,.]\d+)?)\s+(.+)", fragment, re.I)
    if count is not None:
        servings = float(count.group(1).replace(",", "."))
        phrase = normalize_food_phrase(count.group(2))
        return ParsedMealItem(
            phrase=phrase,
            quantity_g=servings,
            source_text=fragment,
            evidence={"quantity_basis": "serving_count", "serving_count": servings},
        )

    raise ValueError(f"could not parse food item: {fragment}")


def normalize_food_phrase(value: str) -> str:
    return value.strip().casefold()


def parse_nutrition_label_text(text: str) -> ParsedNutritionLabel:
    fields = parse_label_fields(text)
    food_name = fields.get("produto") or fields.get("product") or fields.get("nome")
    if not food_name:
        raise ValueError("label text is missing product name")
    brand = fields.get("marca") or fields.get("brand")
    serving_text = fields.get("porcao") or fields.get("porção") or fields.get("serving")
    if serving_text is None:
        raise ValueError("label text is missing serving size")
    serving_size_g = parse_grams(serving_text)
    if serving_size_g <= 0:
        raise ValueError("serving size must be positive")

    calories = parse_number_from_field(fields, ("valor energetico", "valor energético", "calorias", "calories", "energy"))
    protein = parse_number_from_field(fields, ("proteinas", "proteínas", "protein"))
    carbs = parse_number_from_field(fields, ("carboidratos", "carbs", "carbohydrate"))
    fat = parse_number_from_field(fields, ("gorduras totais", "gordura total", "fat", "total fat"))
    fiber = parse_number_from_field(fields, ("fibra alimentar", "fibras", "fiber"), default=0)
    sodium = parse_number_from_field(fields, ("sodio", "sódio", "sodium"), default=0)
    barcode = fields.get("codigo de barras") or fields.get("código de barras") or fields.get("barcode")
    factor = 100 / serving_size_g
    return ParsedNutritionLabel(
        food_name=food_name.strip(),
        brand=brand.strip() if brand else None,
        serving_size_g=serving_size_g,
        nutrients_per_100g=Nutrients(
            calories_kcal=round(calories * factor, 2),
            protein_g=round(protein * factor, 2),
            carbs_g=round(carbs * factor, 2),
            fat_g=round(fat * factor, 2),
            fiber_g=round(fiber * factor, 2),
            sodium_mg=round(sodium * factor, 2),
        ),
        barcode=barcode.strip() if barcode else None,
    )


def parse_recipe_text(text: str) -> ParsedRecipe:
    name: str | None = None
    yield_g: float | None = None
    ingredient_lines: list[str] = []
    in_ingredients = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        field = re.fullmatch(r"([^:]+):\s*(.*)", line)
        if field is not None:
            key = normalize_label_key(field.group(1))
            value = field.group(2).strip()
            if key in {"recipe", "receita", "name", "nome"}:
                name = value
                in_ingredients = False
                continue
            if key in {"yield", "rendimento", "peso final", "final weight"}:
                yield_g = parse_grams(value)
                in_ingredients = False
                continue
            if key in {"ingredients", "ingredientes"}:
                in_ingredients = True
                if value:
                    ingredient_lines.append(value)
                continue
        if in_ingredients:
            ingredient_lines.append(line)

    if not name:
        raise ValueError("recipe is missing name")
    if yield_g is None:
        raise ValueError("recipe is missing yield")
    if yield_g <= 0:
        raise ValueError("recipe yield must be positive")
    ingredients = tuple(parse_recipe_ingredient(line) for line in ingredient_lines)
    if not ingredients:
        raise ValueError("recipe is missing ingredients")
    return ParsedRecipe(name=name, yield_g=yield_g, ingredients=ingredients)


def parse_recipe_ingredient(line: str) -> ParsedRecipeIngredient:
    item = parse_text_meal_item(line)
    if item.evidence.get("quantity_basis") != "grams":
        raise ValueError(f"recipe ingredient must include grams: {line}")
    return ParsedRecipeIngredient(
        phrase=item.phrase,
        quantity_g=item.quantity_g,
        source_text=line,
    )


def parse_label_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.fullmatch(r"([^:]+):\s*(.+)", line)
        if match is None:
            continue
        fields[normalize_label_key(match.group(1))] = match.group(2).strip()
    return fields


def normalize_label_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def parse_number_from_field(
    fields: dict[str, str],
    keys: tuple[str, ...],
    *,
    default: float | None = None,
) -> float:
    for key in keys:
        value = fields.get(normalize_label_key(key))
        if value is not None:
            return parse_decimal(value)
    if default is not None:
        return default
    raise ValueError(f"label text is missing nutrient field: {keys[0]}")


def parse_grams(value: str) -> float:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*g\b", value, re.I)
    if match is None:
        raise ValueError(f"could not parse grams from: {value}")
    return float(match.group(1).replace(",", "."))


def parse_decimal(value: str) -> float:
    match = re.search(r"(\d+(?:[,.]\d+)?)", value)
    if match is None:
        raise ValueError(f"could not parse number from: {value}")
    return float(match.group(1).replace(",", "."))


def household_to_snapshot(household: Household) -> dict[str, Any]:
    return {
        "id": household.id,
        "name": household.name,
        "created_at": household.created_at.isoformat(),
    }


def household_from_snapshot(value: dict[str, Any]) -> Household:
    return Household(
        id=value["id"],
        name=value["name"],
        created_at=datetime.fromisoformat(value["created_at"]),
    )


def person_to_snapshot(person: Person) -> dict[str, Any]:
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


def person_from_snapshot(value: dict[str, Any]) -> Person:
    return Person(
        id=value["id"],
        household_id=value["household_id"],
        name=value["name"],
        timezone=value["timezone"],
        birth_date=date.fromisoformat(value["birth_date"]) if value.get("birth_date") else None,
        sex=value.get("sex"),
        height_cm=float(value["height_cm"]) if value.get("height_cm") is not None else None,
        activity_level=value.get("activity_level"),
        created_at=datetime.fromisoformat(value["created_at"]),
    )


def goal_profile_to_snapshot(profile: GoalProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "person_id": profile.person_id,
        "starts_on": profile.starts_on.isoformat(),
        "ends_on": profile.ends_on.isoformat() if profile.ends_on is not None else None,
        "targets": nutrients_to_snapshot(profile.targets),
        "notes": profile.notes,
        "created_at": profile.created_at.isoformat(),
    }


def goal_profile_from_snapshot(value: dict[str, Any]) -> GoalProfile:
    return GoalProfile(
        id=value["id"],
        person_id=value["person_id"],
        starts_on=date.fromisoformat(value["starts_on"]),
        ends_on=date.fromisoformat(value["ends_on"]) if value.get("ends_on") else None,
        targets=nutrients_from_snapshot(value["targets"]),
        notes=value.get("notes"),
        created_at=datetime.fromisoformat(value["created_at"]),
    )


def nutrients_to_snapshot(nutrients: Nutrients) -> dict[str, float]:
    return {
        "calories_kcal": nutrients.calories_kcal,
        "protein_g": nutrients.protein_g,
        "carbs_g": nutrients.carbs_g,
        "fat_g": nutrients.fat_g,
        "fiber_g": nutrients.fiber_g,
        "sodium_mg": nutrients.sodium_mg,
    }


def nutrients_from_snapshot(value: dict[str, Any]) -> Nutrients:
    return Nutrients(
        calories_kcal=float(value.get("calories_kcal", 0)),
        protein_g=float(value.get("protein_g", 0)),
        carbs_g=float(value.get("carbs_g", 0)),
        fat_g=float(value.get("fat_g", 0)),
        fiber_g=float(value.get("fiber_g", 0)),
        sodium_mg=float(value.get("sodium_mg", 0)),
    )


def food_to_snapshot(food: Food) -> dict[str, Any]:
    return {
        "id": food.id,
        "household_id": food.household_id,
        "name": food.name,
        "brand": food.brand,
        "default_version_id": food.default_version_id,
        "archived": food.archived,
    }


def food_from_snapshot(value: dict[str, Any]) -> Food:
    return Food(
        id=value["id"],
        household_id=value["household_id"],
        name=value["name"],
        brand=value.get("brand"),
        default_version_id=value.get("default_version_id"),
        archived=bool(value.get("archived", False)),
    )


def food_version_to_snapshot(version: FoodVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "food_id": version.food_id,
        "label": version.label,
        "nutrients_per_100g": nutrients_to_snapshot(version.nutrients_per_100g),
        "source": version.source,
        "serving_size_g": version.serving_size_g,
        "created_at": version.created_at.isoformat(),
        "archived": version.archived,
    }


def food_version_from_snapshot(value: dict[str, Any]) -> FoodVersion:
    return FoodVersion(
        id=value["id"],
        food_id=value["food_id"],
        label=value["label"],
        nutrients_per_100g=nutrients_from_snapshot(value["nutrients_per_100g"]),
        source=value["source"],
        serving_size_g=value.get("serving_size_g"),
        created_at=datetime.fromisoformat(value["created_at"]),
        archived=bool(value.get("archived", False)),
    )


def food_alias_to_snapshot(alias: FoodAlias) -> dict[str, Any]:
    return {
        "id": alias.id,
        "household_id": alias.household_id,
        "phrase": alias.phrase,
        "food_id": alias.food_id,
        "person_id": alias.person_id,
        "confidence": alias.confidence,
    }


def food_alias_from_snapshot(value: dict[str, Any]) -> FoodAlias:
    return FoodAlias(
        id=value["id"],
        household_id=value["household_id"],
        phrase=value["phrase"],
        food_id=value["food_id"],
        person_id=value.get("person_id"),
        confidence=float(value.get("confidence", 1.0)),
    )


def barcode_association_to_snapshot(association: BarcodeAssociation) -> dict[str, Any]:
    return {
        "id": association.id,
        "household_id": association.household_id,
        "barcode": association.barcode,
        "food_id": association.food_id,
        "food_version_id": association.food_version_id,
        "source": association.source,
        "confidence": association.confidence,
        "confirmed_at": association.confirmed_at.isoformat()
        if association.confirmed_at is not None
        else None,
        "archived": association.archived,
    }


def barcode_association_from_snapshot(value: dict[str, Any]) -> BarcodeAssociation:
    confirmed_at = value.get("confirmed_at")
    return BarcodeAssociation(
        id=value["id"],
        household_id=value["household_id"],
        barcode=value["barcode"],
        food_id=value["food_id"],
        food_version_id=value["food_version_id"],
        source=value["source"],
        confidence=float(value.get("confidence", 1.0)),
        confirmed_at=datetime.fromisoformat(confirmed_at) if confirmed_at else None,
        archived=bool(value.get("archived", False)),
    )


def diary_entry_to_snapshot(entry: DiaryEntry) -> dict[str, Any]:
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


def diary_entry_from_snapshot(value: dict[str, Any]) -> DiaryEntry:
    return DiaryEntry(
        id=value["id"],
        person_id=value["person_id"],
        logged_at=datetime.fromisoformat(value["logged_at"]),
        meal_type=value["meal_type"],
        food_version_id=value["food_version_id"],
        quantity_g=float(value["quantity_g"]),
        source=value["source"],
        deleted_at=datetime.fromisoformat(value["deleted_at"]) if value.get("deleted_at") else None,
    )


def weight_entry_to_snapshot(entry: WeightEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "person_id": entry.person_id,
        "measured_at": entry.measured_at.isoformat(),
        "weight_kg": entry.weight_kg,
        "note": entry.note,
        "source": entry.source,
    }


def weight_entry_from_snapshot(value: dict[str, Any]) -> WeightEntry:
    return WeightEntry(
        id=value["id"],
        person_id=value["person_id"],
        measured_at=datetime.fromisoformat(value["measured_at"]),
        weight_kg=float(value["weight_kg"]),
        note=value.get("note"),
        source=value["source"],
    )


def proposal_to_snapshot(proposal: CreateDiaryEntriesProposal) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "person_id": proposal.person_id,
        "entries": [diary_entry_to_snapshot(entry) for entry in proposal.entries],
        "proposal_type": proposal.proposal_type,
        "status": proposal.status,
        "summary": proposal.summary,
        "payload": proposal.payload,
        "totals": nutrients_to_snapshot(proposal.totals),
        "evidence": list(proposal.evidence),
        "source_agent_run_id": proposal.source_agent_run_id,
        "applied_record_ids": list(proposal.applied_record_ids),
        "created_at": proposal.created_at.isoformat(),
    }


def proposal_from_snapshot(value: dict[str, Any]) -> CreateDiaryEntriesProposal:
    return CreateDiaryEntriesProposal(
        id=value["id"],
        person_id=value["person_id"],
        entries=tuple(diary_entry_from_snapshot(entry) for entry in value.get("entries", [])),
        proposal_type=value.get("proposal_type", "diary_entries"),
        status=value["status"],
        summary=value.get("summary", ""),
        payload=dict(value.get("payload", {})),
        totals=nutrients_from_snapshot(value.get("totals", {})),
        evidence=tuple(value.get("evidence", [])),
        source_agent_run_id=value.get("source_agent_run_id"),
        applied_record_ids=tuple(value.get("applied_record_ids", [])),
        created_at=datetime.fromisoformat(value["created_at"]),
    )


def agent_run_to_snapshot(run: AgentRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "person_id": run.person_id,
        "input_text": run.input_text,
        "settings": run.settings,
        "status": run.status,
        "proposal_id": run.proposal_id,
        "created_at": run.created_at.isoformat(),
    }


def agent_run_from_snapshot(value: dict[str, Any]) -> AgentRun:
    return AgentRun(
        id=value["id"],
        person_id=value["person_id"],
        input_text=value["input_text"],
        settings=dict(value.get("settings", {})),
        status=value["status"],
        proposal_id=value.get("proposal_id"),
        created_at=datetime.fromisoformat(value["created_at"]),
    )
