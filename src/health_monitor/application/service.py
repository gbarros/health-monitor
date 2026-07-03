from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo

from health_monitor.agent import AgentDeps, PydanticAINutritionAgent, PydanticAIUnavailable
from health_monitor.domain.diary import Diary, DiaryEntry
from health_monitor.domain.food_resolution import FoodResolution, FoodResolver
from health_monitor.domain.foods import BarcodeAssociation, Food, FoodAlias, FoodCatalog, FoodVersion
from health_monitor.domain.nutrients import Nutrients
from health_monitor.domain.proposals import CreateDiaryEntriesProposal, ProposalService
from health_monitor.lookup.estimates import FoodEstimator, NutritionEstimate
from health_monitor.lookup.foods import FoodLookupCandidate, FoodLookupProvider
from health_monitor.lookup.labels import LabelTextExtraction, LabelTextExtractor
from health_monitor.persistence.sqlite_state import StateRepository


class ModelUnavailableError(RuntimeError):
    """The configured model runtime is unreachable and deterministic fallback is disabled.

    Carries the original user message so clients can offer a replay once the
    model is back.
    """

    def __init__(self, message: str, *, replay_message: str | None = None) -> None:
        super().__init__(message)
        self.replay_message = replay_message


AGENT_INTENT_TEMPLATES: dict[str, str] = {
    "log_food": (
        "The user opened the registrar alimento helper. Treat the message as food logging context; "
        "fields may be missing, so ask concise follow-up questions when needed before drafting."
    ),
    "recipe": (
        "The user opened the receita/lote helper. Extract a recipe name, aliases, structured "
        "ingredients with grams, and total cooked weight if present; ask for missing essentials."
    ),
    "label_scan": (
        "The user opened the rotulo helper. Use attachment OCR tools when attachment ids are present, "
        "then ask for missing product/portion details or draft a food-version proposal."
    ),
    "weight": "The user opened the peso helper. If a numeric weight is present, call log_weight.",
    "repeat_meal": (
        "The user opened the repetir refeicao helper. Extract source day and meal type, then call "
        "repeat_meal or ask for the missing source meal."
    ),
    "review": "The user opened the review helper. Draft review notes only via structured tools.",
}


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
    evidence_status: str
    confidence: float


@dataclass(frozen=True)
class DaySummary:
    person_id: str
    day: date
    totals: Nutrients
    meals: dict[str, list[DaySummaryEntry]]
    target: Nutrients | None = None
    target_delta: Nutrients | None = None


@dataclass(frozen=True)
class AmbiguousFoodReference:
    phrase: str
    candidates: tuple[dict[str, object], ...]


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
class RollingSummary:
    person_id: str
    start: date
    end: date
    days: int
    days_with_data: int
    daily: dict[date, Nutrients]
    averages: Nutrients
    stddev: Nutrients


@dataclass(frozen=True)
class AgentRun:
    id: str
    person_id: str
    input_text: str
    settings: dict[str, Any]
    status: str
    proposal_id: str | None = None
    runtime: str | None = None
    model_name: str | None = None
    tool_loop_count: int = 0
    fallback_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class AgentToolCall:
    id: str
    agent_run_id: str
    person_id: str
    tool_name: str
    input_summary: str
    output_summary: str
    status: str
    source_record_ids: tuple[str, ...] = ()
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


@dataclass(frozen=True)
class AgentChatTurn:
    id: str
    person_id: str
    agent_run_id: str
    user_message: str
    assistant_message: str
    behavior_label: str
    citations: tuple[dict[str, str], ...] = ()
    proposal_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class OnboardingTurn:
    id: str
    session_id: str
    user_message: str
    assistant_message: str
    household_id: str | None = None
    proposal_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class BackgroundJob:
    id: str
    job_type: str
    status: str
    payload: dict[str, Any]
    client_request_id: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    last_error: str | None = None
    attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class RecipeIngredient:
    food_id: str
    food_version_id: str
    food_name: str
    quantity_g: float
    nutrients: Nutrients


@dataclass(frozen=True)
class RecipeVersion:
    id: str
    household_id: str
    food_id: str
    food_version_id: str
    name: str
    yield_g: float
    ingredients: tuple[RecipeIngredient, ...]
    source_proposal_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class AgentChatResponse:
    run_id: str
    person_id: str
    message: str
    behavior_label: str
    citations: tuple[dict[str, str], ...] = ()
    proposal_id: str | None = None


@dataclass(frozen=True)
class ReviewNote:
    id: str
    person_id: str
    note_type: str
    title: str
    body: str
    starts_on: date | None = None
    ends_on: date | None = None
    source: str = "manual"
    source_agent_run_id: str | None = None
    source_proposal_id: str | None = None
    source_record_refs: tuple[dict[str, str], ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class AttachmentObject:
    id: str
    household_id: str
    created_by_person_id: str
    object_type: str
    mime_type: str
    byte_size: int
    sha256: str
    content: bytes
    filename: str | None = None
    storage_status: str = "stored"
    retention_policy: str = "keep"
    linked_record_type: str | None = None
    linked_record_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ParsedMealItem:
    phrase: str
    quantity_g: float
    source_text: str
    evidence: dict[str, object]


@dataclass(frozen=True)
class ParsedMealRemoval:
    phrase: str
    quantity_g: float
    source_text: str


@dataclass(frozen=True)
class ResolvedMealFood:
    food_version_id: str
    version: FoodVersion
    food_name: str
    source: str
    resolution_reason: str
    confidence: float
    evidence_source_type: str
    evidence_source_details: dict[str, object]
    pending_version: dict[str, object] | None


@dataclass(frozen=True)
class ParsedRangeEstimate:
    label: str
    low_kcal: float
    high_kcal: float
    source_text: str


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
    yield_g: float | None
    ingredients: tuple[ParsedRecipeIngredient, ...]


class HealthMonitorService:
    def __init__(
        self,
        repository: StateRepository | None = None,
        estimator: FoodEstimator | None = None,
        food_lookup_provider: FoodLookupProvider | None = None,
        research_lookup_provider: FoodLookupProvider | None = None,
        label_text_extractor: LabelTextExtractor | None = None,
        agent_runtime: str = "deterministic",
        model_provider: str = "deterministic",
        agent_model: str | None = None,
        ollama_base_url: str = "http://127.0.0.1:11434",
        require_model: bool = True,
        model_health_checker: Callable[[], bool] | None = None,
    ) -> None:
        self.repository = repository
        self.estimator = estimator
        self.food_lookup_provider = food_lookup_provider
        self.research_lookup_provider = research_lookup_provider
        self.label_text_extractor = label_text_extractor
        self.agent_runtime = agent_runtime
        self.model_provider = model_provider
        self.agent_model = agent_model
        self.ollama_base_url = ollama_base_url
        self.require_model = require_model
        self.model_health_checker = model_health_checker
        self._model_health_cache: tuple[float, bool] | None = None
        self.households: dict[str, Household] = {}
        self.people: dict[str, Person] = {}
        self.goal_profiles: dict[str, GoalProfile] = {}
        self.catalog = FoodCatalog()
        self.diary = Diary(self.catalog)
        self.weights: dict[str, WeightEntry] = {}
        self.resolver = FoodResolver(self.catalog)
        self.proposals = ProposalService(self.diary)
        self.agent_runs: dict[str, AgentRun] = {}
        self.agent_tool_calls: dict[str, AgentToolCall] = {}
        self.chat_turns: dict[str, AgentChatTurn] = {}
        self.onboarding_turns: dict[str, OnboardingTurn] = {}
        self.review_notes: dict[str, ReviewNote] = {}
        self.lookup_candidates: dict[str, FoodLookupCandidate] = {}
        self.attachments: dict[str, AttachmentObject] = {}
        self.jobs: dict[str, BackgroundJob] = {}
        self.recipe_versions: dict[str, RecipeVersion] = {}
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

    def update_person(
        self,
        *,
        person_id: str,
        name: str | None = None,
        timezone: str | None = None,
        birth_date: date | None = None,
        sex: str | None = None,
        height_cm: float | None = None,
        activity_level: str | None = None,
    ) -> Person:
        person = self._require_person(person_id)
        next_timezone = timezone if timezone is not None else person.timezone
        ZoneInfo(next_timezone)
        updated = Person(
            id=person.id,
            household_id=person.household_id,
            name=name if name is not None else person.name,
            timezone=next_timezone,
            birth_date=birth_date if birth_date is not None else person.birth_date,
            sex=sex if sex is not None else person.sex,
            height_cm=float(height_cm) if height_cm is not None else person.height_cm,
            activity_level=activity_level if activity_level is not None else person.activity_level,
            created_at=person.created_at,
        )
        self.people[person_id] = updated
        self._persist()
        return updated

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

    def propose_profile_update(
        self,
        *,
        person_id: str,
        changes: dict[str, Any],
        source_text: str,
        source_agent_run_id: str | None = None,
    ) -> CreateDiaryEntriesProposal:
        person = self._require_person(person_id)
        allowed = {"name", "timezone", "birth_date", "sex", "height_cm", "activity_level"}
        payload = {key: value for key, value in changes.items() if key in allowed and value not in (None, "")}
        if "timezone" in payload:
            ZoneInfo(str(payload["timezone"]))
        if "birth_date" in payload:
            date.fromisoformat(str(payload["birth_date"]))
        if "height_cm" in payload:
            payload["height_cm"] = float(payload["height_cm"])
        if not payload:
            raise ValueError("profile update proposal has no supported changes")
        proposal = CreateDiaryEntriesProposal(
            id=self._next_id("proposal"),
            person_id=person_id,
            entries=(),
            proposal_type="profile_update",
            summary=f"Update profile for {person.name}",
            payload=payload,
            evidence=(
                {
                    "source_type": "agent_chat",
                    "raw_text": source_text,
                },
            ),
            source_agent_run_id=source_agent_run_id,
        )
        self.proposals.create(proposal)
        self._persist()
        return proposal

    def propose_goal_profile_update(
        self,
        *,
        person_id: str,
        starts_on: date,
        targets: Nutrients,
        notes: str | None,
        source_text: str,
        source_agent_run_id: str | None = None,
    ) -> CreateDiaryEntriesProposal:
        self._require_person(person_id)
        if targets.calories_kcal <= 0:
            raise ValueError("daily calorie target must be positive")
        proposal = CreateDiaryEntriesProposal(
            id=self._next_id("proposal"),
            person_id=person_id,
            entries=(),
            proposal_type="goal_profile",
            summary=f"Create goal profile starting {starts_on.isoformat()}",
            payload={
                "starts_on": starts_on.isoformat(),
                "targets": nutrients_to_snapshot(targets),
                "notes": notes,
            },
            evidence=(
                {
                    "source_type": "agent_chat",
                    "raw_text": source_text,
                },
            ),
            source_agent_run_id=source_agent_run_id,
        )
        self.proposals.create(proposal)
        self._persist()
        return proposal

    def create_attachment(
        self,
        *,
        household_id: str,
        person_id: str,
        object_type: str,
        mime_type: str,
        content: bytes,
        filename: str | None = None,
        retention_policy: str = "keep",
    ) -> AttachmentObject:
        self._require_household(household_id)
        person = self._require_person(person_id)
        if person.household_id != household_id:
            raise ValueError("attachment person belongs to a different household")
        if not content:
            raise ValueError("attachment content is empty")
        attachment = AttachmentObject(
            id=self._next_id("attachment"),
            household_id=household_id,
            created_by_person_id=person_id,
            object_type=object_type,
            mime_type=mime_type,
            byte_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            content=content,
            filename=filename,
            retention_policy=retention_policy,
        )
        self.attachments[attachment.id] = attachment
        self._persist()
        return attachment

    def get_attachment(self, attachment_id: str) -> AttachmentObject:
        return self.attachments[attachment_id]

    def attachments_for_record(
        self,
        *,
        linked_record_type: str,
        linked_record_id: str,
    ) -> tuple[AttachmentObject, ...]:
        return tuple(
            sorted(
                (
                    attachment
                    for attachment in self.attachments.values()
                    if attachment.linked_record_type == linked_record_type
                    and attachment.linked_record_id == linked_record_id
                ),
                key=lambda attachment: attachment.created_at,
            )
        )

    def _link_attachment(
        self,
        attachment_id: str,
        *,
        linked_record_type: str,
        linked_record_id: str,
    ) -> AttachmentObject:
        attachment = self.attachments[attachment_id]
        linked = AttachmentObject(
            id=attachment.id,
            household_id=attachment.household_id,
            created_by_person_id=attachment.created_by_person_id,
            object_type=attachment.object_type,
            mime_type=attachment.mime_type,
            byte_size=attachment.byte_size,
            sha256=attachment.sha256,
            content=attachment.content,
            filename=attachment.filename,
            storage_status=attachment.storage_status,
            retention_policy=attachment.retention_policy,
            linked_record_type=linked_record_type,
            linked_record_id=linked_record_id,
            created_at=attachment.created_at,
        )
        self.attachments[attachment.id] = linked
        return linked

    def extract_label_text_from_attachment(self, *, attachment_id: str) -> dict[str, Any]:
        attachment = self.get_attachment(attachment_id)
        if self.label_text_extractor is None:
            raise ValueError("label text extractor is not configured")
        extraction = self.label_text_extractor.extract(
            image_bytes=attachment.content,
            mime_type=attachment.mime_type,
            filename=attachment.filename,
        )
        if extraction is None or not extraction.text.strip():
            raise ValueError("could not extract nutrition label text from attachment")
        return {
            "attachment_id": attachment.id,
            "filename": attachment.filename,
            "text": extraction.text.strip(),
            "source": extraction.source,
            "confidence": extraction.confidence,
            "warnings": list(extraction.warnings),
        }

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
        food_id: str | None = None,
        version_id: str | None = None,
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
            food_id=food_id,
            version_id=version_id,
        )
        self._persist()
        return food, version

    def create_custom_food_and_log_entry(
        self,
        *,
        household_id: str,
        person_id: str,
        name: str,
        brand: str | None,
        version_label: str,
        nutrients_per_100g: Nutrients,
        logged_at_local: str,
        quantity_g: float,
        aliases: list[str] | None = None,
        serving_size_g: float | None = None,
        barcode: str | None = None,
        meal_type: str | None = None,
    ) -> tuple[Food, FoodVersion, DiaryEntry]:
        self._require_household(household_id)
        person = self._require_person(person_id)
        if person.household_id != household_id:
            raise ValueError("person belongs to a different household")
        if quantity_g <= 0:
            raise ValueError("quantity_g must be positive")

        food, version = self._create_food_with_version(
            household_id=household_id,
            name=name,
            brand=brand,
            version_label=version_label,
            nutrients_per_100g=nutrients_per_100g,
            source="manual_quick_custom",
            aliases=aliases,
            barcode=barcode,
            serving_size_g=serving_size_g,
        )
        logged_at = self._parse_person_datetime(logged_at_local, person)
        entry = self.diary.add_entry(
            DiaryEntry(
                id=self._next_id("diary_entry"),
                person_id=person_id,
                logged_at=logged_at,
                meal_type=meal_type or infer_meal_type(logged_at),
                food_version_id=version.id,
                quantity_g=float(quantity_g),
                source="manual_quick_custom",
            )
        )
        self._persist()
        return food, version, entry

    def list_food_versions(
        self,
        *,
        household_id: str,
        person_id: str | None = None,
        query: str | None = None,
    ) -> tuple[tuple[Food, FoodVersion], ...]:
        self._require_household(household_id)
        if person_id is not None:
            person = self._require_person(person_id)
            if person.household_id != household_id:
                raise ValueError("person belongs to a different household")

        normalized_query = query.casefold().strip() if query is not None else ""
        latest_logged_by_food: dict[str, datetime] = {}
        if person_id is not None:
            for entry in self.diary.entries.values():
                if entry.person_id != person_id or entry.deleted_at is not None:
                    continue
                version = self.catalog.versions.get(entry.food_version_id)
                if version is None:
                    continue
                current_latest = latest_logged_by_food.get(version.food_id)
                if current_latest is None or entry.logged_at > current_latest:
                    latest_logged_by_food[version.food_id] = entry.logged_at

        rows: list[tuple[Food, FoodVersion]] = []
        for food in self.catalog.foods.values():
            if food.household_id != household_id or food.archived or food.default_version_id is None:
                continue
            version = self.catalog.versions.get(food.default_version_id)
            if version is None or version.archived:
                continue
            if normalized_query and not self._food_matches_query(food, normalized_query):
                continue
            rows.append((food, version))

        rows.sort(
            key=lambda row: (
                0 if row[0].id in latest_logged_by_food else 1,
                -latest_logged_by_food[row[0].id].timestamp()
                if row[0].id in latest_logged_by_food
                else 0,
                row[0].name.casefold(),
                row[0].brand.casefold() if row[0].brand is not None else "",
            )
        )
        return tuple(rows)

    def _food_matches_query(self, food: Food, normalized_query: str) -> bool:
        haystacks = [food.name, food.brand or ""]
        haystacks.extend(
            alias.phrase
            for alias in self.catalog.aliases.values()
            if alias.food_id == food.id and alias.household_id == food.household_id
        )
        return any(normalized_query in value.casefold() for value in haystacks)

    def archive_food(self, food_id: str) -> Food:
        food = self.catalog.foods[food_id]
        archived = self.catalog.archive_food(food_id)
        for barcode, association in list(self.catalog.barcode_associations.items()):
            if association.food_id != food.id:
                continue
            self.catalog.barcode_associations[barcode] = BarcodeAssociation(
                id=association.id,
                household_id=association.household_id,
                barcode=association.barcode,
                food_id=association.food_id,
                food_version_id=association.food_version_id,
                source=association.source,
                confidence=association.confidence,
                confirmed_at=association.confirmed_at,
                archived=True,
            )
        self._persist()
        return archived

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
        confidence: float = 1.0,
        food_id: str | None = None,
        version_id: str | None = None,
    ) -> tuple[Food, FoodVersion]:
        self._require_household(household_id)
        if food_id is not None and food_id in self.catalog.foods:
            food = self.catalog.foods[food_id]
            if food.household_id != household_id:
                raise ValueError("food belongs to a different household")
        else:
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
                confidence=confidence,
            ),
            make_default=True,
        )
        food = self.catalog.foods[food.id]
        for phrase in aliases or []:
            self._add_alias_if_missing(
                household_id=household_id,
                phrase=phrase,
                food_id=food.id,
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

    def _add_alias_if_missing(self, *, household_id: str, phrase: str, food_id: str) -> None:
        normalized = phrase.casefold().strip()
        for alias in self.catalog.aliases.values():
            if alias.household_id != household_id:
                continue
            if alias.food_id != food_id:
                continue
            if alias.phrase.casefold().strip() == normalized:
                return
        self.catalog.add_alias(
            FoodAlias(
                id=self._next_id("food_alias"),
                household_id=household_id,
                phrase=phrase,
                food_id=food_id,
            )
        )

    def _find_food_by_name(
        self,
        *,
        household_id: str,
        name: str,
        brand: str | None,
    ) -> Food | None:
        normalized_name = name.casefold().strip()
        normalized_brand = brand.casefold().strip() if brand is not None else None
        for food in self.catalog.foods.values():
            if food.household_id != household_id or food.archived:
                continue
            food_brand = food.brand.casefold().strip() if food.brand is not None else None
            if food.name.casefold().strip() == normalized_name and food_brand == normalized_brand:
                return food
        return None

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
            resolution = self._resolve_phrase_by_recent_use(
                household_id=household_id,
                person_id=person_id,
                phrase=phrase,
            )
        if resolution is None and phrase is not None:
            resolution = self.resolver.resolve_phrase(phrase, person_id=person_id)
        if resolution is None:
            raise ValueError("food reference could not be resolved")
        food = self.catalog.foods[resolution.food_id]
        if food.household_id != household_id:
            raise ValueError("resolved food belongs to a different household")
        return resolution

    def _resolve_phrase_by_recent_use(
        self,
        *,
        household_id: str,
        person_id: str,
        phrase: str,
    ) -> FoodResolution | None:
        normalized = phrase.casefold().strip()
        matching_food_ids = {
            alias.food_id
            for alias in self.catalog.aliases.values()
            if alias.household_id == household_id
            and alias.phrase.casefold().strip() == normalized
            and (alias.person_id is None or alias.person_id == person_id)
            and alias.food_id in self.catalog.foods
            and not self.catalog.foods[alias.food_id].archived
        }
        if len(matching_food_ids) <= 1:
            return None

        latest_entry: DiaryEntry | None = None
        for entry in self.diary.entries.values():
            if entry.person_id != person_id or entry.deleted_at is not None:
                continue
            version = self.catalog.versions.get(entry.food_version_id)
            if version is None or version.archived:
                continue
            if version.food_id not in matching_food_ids:
                continue
            if latest_entry is None or entry.logged_at > latest_entry.logged_at:
                latest_entry = entry
        if latest_entry is None:
            return None

        version = self.catalog.get_version(latest_entry.food_version_id)
        return FoodResolution(
            food_id=version.food_id,
            food_version_id=version.id,
            reason="alias_recently_logged_version",
            confidence=0.98,
        )

    def lookup_food_candidates(
        self,
        *,
        household_id: str,
        person_id: str,
        phrase: str | None = None,
        barcode: str | None = None,
    ) -> tuple[FoodLookupCandidate, ...]:
        self._require_household(household_id)
        self._require_person(person_id)
        candidates: list[FoodLookupCandidate] = []
        if barcode is not None:
            association = self.catalog.resolve_barcode(barcode)
            if association is not None:
                food = self.catalog.foods[association.food_id]
                version = self.catalog.get_version(association.food_version_id)
                candidates.append(
                    FoodLookupCandidate(
                        id=self._next_id("lookup_candidate"),
                        source_type="local_barcode",
                        source_name="Local library",
                        source_id=association.id,
                        product_name=food.name,
                        brand=food.brand,
                        barcode=association.barcode,
                        food_id=food.id,
                        food_version_id=version.id,
                        serving_size_g=version.serving_size_g,
                        nutrients_per_100g=version.nutrients_per_100g,
                        confidence=association.confidence,
                    )
                )
        if phrase is not None:
            resolution = self._resolve_phrase_by_recent_use(
                household_id=household_id,
                person_id=person_id,
                phrase=phrase,
            )
            if resolution is None:
                resolution = self.resolver.resolve_phrase(phrase, person_id=person_id)
            if resolution is not None:
                food = self.catalog.foods[resolution.food_id]
                version = self.catalog.get_version(resolution.food_version_id)
                candidates.append(
                    FoodLookupCandidate(
                        id=self._next_id("lookup_candidate"),
                        source_type="local_phrase",
                        source_name="Local library",
                        source_id=resolution.reason,
                        product_name=food.name,
                        brand=food.brand,
                        barcode=None,
                        food_id=food.id,
                        food_version_id=version.id,
                        serving_size_g=version.serving_size_g,
                        nutrients_per_100g=version.nutrients_per_100g,
                        confidence=resolution.confidence,
                    )
                )
        if self.food_lookup_provider is not None:
            for candidate in self.food_lookup_provider.lookup(phrase=phrase, barcode=barcode):
                candidates.append(
                    FoodLookupCandidate(
                        id=self._next_id("lookup_candidate"),
                        source_type=candidate.source_type,
                        source_name=candidate.source_name,
                        source_id=candidate.source_id,
                        source_url=candidate.source_url,
                        product_name=candidate.product_name,
                        brand=candidate.brand,
                        barcode=candidate.barcode,
                        food_id=candidate.food_id,
                        food_version_id=candidate.food_version_id,
                        serving_size_g=candidate.serving_size_g,
                        nutrients_per_100g=candidate.nutrients_per_100g,
                        confidence=candidate.confidence,
                        warnings=candidate.warnings,
                        research_prompt=candidate.research_prompt,
                        source_claims=candidate.source_claims,
                    )
                )
        for candidate in candidates:
            self.lookup_candidates[candidate.id] = candidate
        return tuple(candidates)

    def propose_food_lookup_candidate(
        self,
        *,
        household_id: str,
        person_id: str,
        candidate_id: str,
    ) -> CreateDiaryEntriesProposal:
        self._require_household(household_id)
        self._require_person(person_id)
        candidate = self.lookup_candidates[candidate_id]
        if candidate.source_type.startswith("local_"):
            raise ValueError("local lookup candidates are already saved")
        payload = {
            "household_id": household_id,
            "food_name": candidate.product_name,
            "brand": candidate.brand,
            "version_label": f"{candidate.source_name} lookup",
            "nutrients_per_100g": nutrients_to_snapshot(candidate.nutrients_per_100g.rounded()),
            "serving_size_g": candidate.serving_size_g,
            "barcode": candidate.barcode,
            "set_as_default": True,
            "source": "external_lookup",
            "source_name": candidate.source_name,
            "source_id": candidate.source_id,
            "source_url": candidate.source_url,
            "confidence": candidate.confidence,
            "research_prompt": candidate.research_prompt,
            "source_claims": [dict(claim) for claim in candidate.source_claims],
        }
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=(),
                proposal_type="food_version_from_lookup",
                summary=f"Food version drafted from {candidate.source_name}: {candidate.product_name}",
                payload=payload,
                evidence=(
                    {
                        "source_type": candidate.source_type,
                        "source_name": candidate.source_name,
                        "source_id": candidate.source_id,
                        "source_url": candidate.source_url,
                        "warnings": list(candidate.warnings),
                        "confidence": candidate.confidence,
                        "research_prompt": candidate.research_prompt,
                        "source_claims": [dict(claim) for claim in candidate.source_claims],
                    },
                ),
            )
        )
        self._persist()
        return proposal

    def _lookup_first_external_food_candidate(self, phrase: str) -> FoodLookupCandidate | None:
        if self.food_lookup_provider is None:
            return None
        for candidate in self.food_lookup_provider.lookup(phrase=phrase, barcode=None):
            if candidate.food_id is not None or candidate.food_version_id is not None:
                continue
            return candidate
        return None

    def _lookup_first_research_food_candidate(self, phrase: str) -> FoodLookupCandidate | None:
        if self.research_lookup_provider is None:
            return None
        for candidate in self.research_lookup_provider.lookup(phrase=phrase, barcode=None):
            if candidate.food_id is not None or candidate.food_version_id is not None:
                continue
            return candidate
        return None

    def _prepare_lookup_candidate_food_version(
        self,
        *,
        household_id: str,
        phrase: str,
        candidate: FoodLookupCandidate,
        source: str,
        resolution_reason: str,
    ) -> tuple[str, str, FoodVersion, dict[str, object], dict[str, object]]:
        food_id = self._next_id("food")
        food_version_id = self._next_id("food_version")
        version_label = f"{candidate.source_name} lookup"
        version = FoodVersion(
            id=food_version_id,
            food_id=food_id,
            label=version_label,
            nutrients_per_100g=candidate.nutrients_per_100g,
            source=source,
            serving_size_g=candidate.serving_size_g,
            confidence=candidate.confidence,
        )
        pending_lookup_version: dict[str, object] = {
            "food_id": food_id,
            "food_version_id": food_version_id,
            "household_id": household_id,
            "food_name": candidate.product_name,
            "brand": candidate.brand,
            "phrase": phrase,
            "version_label": version_label,
            "nutrients_per_100g": nutrients_to_snapshot(
                candidate.nutrients_per_100g.rounded()
            ),
            "source": source,
            "source_type": candidate.source_type,
            "source_name": candidate.source_name,
            "source_id": candidate.source_id,
            "source_url": candidate.source_url,
            "barcode": candidate.barcode,
            "serving_size_g": candidate.serving_size_g,
            "confidence": candidate.confidence,
            "warnings": list(candidate.warnings),
            "research_prompt": candidate.research_prompt,
            "source_claims": [dict(claim) for claim in candidate.source_claims],
        }
        evidence_source_details: dict[str, object] = {
            "source_name": candidate.source_name,
            "source_id": candidate.source_id,
            "source_url": candidate.source_url,
            "warnings": list(candidate.warnings),
            "research_prompt": candidate.research_prompt,
            "source_claims": [dict(claim) for claim in candidate.source_claims],
            "resolution_reason": resolution_reason,
        }
        return food_id, food_version_id, version, pending_lookup_version, evidence_source_details

    def log_diary_entry(
        self,
        *,
        person_id: str,
        logged_at_local: str,
        food_version_id: str,
        quantity_g: float | None = None,
        serving_count: float | None = None,
        source: str,
        meal_type: str | None = None,
    ) -> DiaryEntry:
        person = self._require_person(person_id)
        logged_at = self._parse_person_datetime(logged_at_local, person)
        resolved_quantity_g = self._resolve_log_quantity_g(
            food_version_id=food_version_id,
            quantity_g=quantity_g,
            serving_count=serving_count,
        )
        entry = DiaryEntry(
            id=self._next_id("diary_entry"),
            person_id=person_id,
            logged_at=logged_at,
            meal_type=meal_type or infer_meal_type(logged_at),
            food_version_id=food_version_id,
            quantity_g=resolved_quantity_g,
            source=source,
        )
        created = self.diary.add_entry(entry)
        self._persist()
        return created

    def _resolve_log_quantity_g(
        self,
        *,
        food_version_id: str,
        quantity_g: float | None,
        serving_count: float | None,
    ) -> float:
        if quantity_g is None and serving_count is None:
            raise ValueError("quantity_g or serving_count is required")
        if quantity_g is not None and serving_count is not None:
            raise ValueError("provide either quantity_g or serving_count, not both")
        if quantity_g is not None:
            if quantity_g <= 0:
                raise ValueError("quantity_g must be positive")
            return float(quantity_g)

        assert serving_count is not None
        if serving_count <= 0:
            raise ValueError("serving_count must be positive")
        version = self.catalog.get_version(food_version_id)
        if version.serving_size_g is None:
            raise ValueError("serving_size_g is required to log by serving count")
        return float(serving_count) * version.serving_size_g

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

    def update_proposal_entry(
        self,
        *,
        proposal_id: str,
        entry_id: str,
        food_version_id: str | None = None,
        quantity_g: float | None = None,
        meal_type: str | None = None,
    ) -> CreateDiaryEntriesProposal:
        proposal = self.proposals.proposals[proposal_id]
        if proposal.status != "draft":
            raise ValueError("only draft proposals can be edited")
        if not proposal.entries:
            raise ValueError("proposal has no editable diary entries")
        if food_version_id is not None:
            self.catalog.get_version(food_version_id)
        if quantity_g is not None and quantity_g <= 0:
            raise ValueError("quantity_g must be positive")

        found = False
        updated_entries: list[DiaryEntry] = []
        for entry in proposal.entries:
            if entry.id != entry_id:
                updated_entries.append(entry)
                continue
            found = True
            updated_entries.append(
                DiaryEntry(
                    id=entry.id,
                    person_id=entry.person_id,
                    logged_at=entry.logged_at,
                    meal_type=meal_type or entry.meal_type,
                    food_version_id=food_version_id or entry.food_version_id,
                    quantity_g=float(quantity_g) if quantity_g is not None else entry.quantity_g,
                    source=entry.source,
                    deleted_at=entry.deleted_at,
                )
            )
        if not found:
            raise ValueError(f"proposal entry not found: {entry_id}")

        totals = self._proposal_entries_total(
            tuple(updated_entries),
            payload=proposal.payload,
        )
        evidence = tuple(
            self._updated_proposal_evidence_item(
                item,
                old_entries=proposal.entries,
                updated_entries=tuple(updated_entries),
                item_index=index,
            )
            for index, item in enumerate(proposal.evidence)
        )
        payload = dict(proposal.payload)
        if len(updated_entries) == 1:
            payload["quantity_g"] = updated_entries[0].quantity_g
            payload["meal_type"] = updated_entries[0].meal_type

        updated = CreateDiaryEntriesProposal(
            id=proposal.id,
            person_id=proposal.person_id,
            entries=tuple(updated_entries),
            proposal_type=proposal.proposal_type,
            status=proposal.status,
            summary=proposal.summary,
            payload=payload,
            totals=totals,
            evidence=evidence,
            source_agent_run_id=proposal.source_agent_run_id,
            applied_record_ids=proposal.applied_record_ids,
            created_at=proposal.created_at,
            confirmed_at=proposal.confirmed_at,
            rejected_at=proposal.rejected_at,
        )
        self.proposals.proposals[proposal_id] = updated
        self._persist()
        return updated

    def resolve_text_meal_food_clarification(
        self,
        *,
        proposal_id: str,
        unresolved_index: int,
        food_version_id: str,
    ) -> CreateDiaryEntriesProposal:
        proposal = self.proposals.proposals[proposal_id]
        if proposal.status == "superseded":
            raise ValueError("proposal is superseded")
        if proposal.status != "needs_clarification":
            raise ValueError("only clarification proposals can be resolved")
        unresolved_items = list(proposal.payload.get("unresolved_items", []))
        if unresolved_index < 0 or unresolved_index >= len(unresolved_items):
            raise ValueError("unresolved_index is out of range")
        unresolved = dict(unresolved_items[unresolved_index])
        candidates = [dict(item) for item in unresolved.get("candidates", [])]
        candidate = next(
            (item for item in candidates if str(item.get("food_version_id")) == food_version_id),
            None,
        )
        if candidate is None:
            raise ValueError("food_version_id is not a candidate for this clarification")
        if unresolved.get("quantity_basis") not in {None, "grams"}:
            raise ValueError("only gram-based food clarifications can be resolved here")

        version = self.catalog.get_version(food_version_id)
        food = self.catalog.foods[version.food_id]
        logged_at = datetime.fromisoformat(str(proposal.payload["logged_at_local"]))
        quantity_g = float(unresolved["quantity"])
        if quantity_g <= 0:
            raise ValueError("quantity_g must be positive")
        entry = DiaryEntry(
            id=self._next_id("diary_entry"),
            person_id=proposal.person_id,
            logged_at=logged_at,
            meal_type=infer_meal_type(logged_at),
            food_version_id=version.id,
            quantity_g=quantity_g,
            source="agent_clarification_proposal",
        )
        totals = version.nutrients_per_100g.scale(quantity_g / 100)
        resolved = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=proposal.person_id,
                entries=(entry,),
                proposal_type="diary_entries",
                status="draft",
                summary=f"1 diary entry drafted after clarification: {food.name}",
                payload={
                    "resolved_from_proposal_id": proposal.id,
                    "raw_text": proposal.payload.get("raw_text"),
                    "quantity_g": quantity_g,
                    "meal_type": entry.meal_type,
                },
                totals=totals,
                evidence=(
                    {
                        "source_type": "text_meal_clarification",
                        "source_proposal_id": proposal.id,
                        "phrase": unresolved.get("phrase"),
                        "quantity_g": quantity_g,
                        "food_version_id": version.id,
                        "resolution_reason": "user_selected_candidate",
                    },
                ),
                source_agent_run_id=proposal.source_agent_run_id,
            )
        )
        self.proposals.supersede(
            proposal.id,
            superseded_by_proposal_id=resolved.id,
        )
        if proposal.source_agent_run_id is not None and proposal.source_agent_run_id in self.agent_runs:
            run = self.agent_runs[proposal.source_agent_run_id]
            self.agent_runs[run.id] = replace(
                run,
                status="proposal_created",
                proposal_id=resolved.id,
                tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            )
        self._persist()
        return resolved

    def _proposal_entries_total(
        self,
        entries: tuple[DiaryEntry, ...],
        *,
        payload: dict[str, Any],
    ) -> Nutrients:
        total = Nutrients()
        pending_versions = {
            str(item["food_version_id"]): dict(item)
            for item in payload.get("estimated_food_versions", [])
        }
        for entry in entries:
            pending = pending_versions.get(entry.food_version_id)
            if pending is not None:
                nutrients = nutrients_from_snapshot(dict(pending["nutrients_per_100g"]))
            else:
                nutrients = self.catalog.get_version(entry.food_version_id).nutrients_per_100g
            total += nutrients.scale(entry.quantity_g / 100)
        return total

    def _updated_proposal_evidence_item(
        self,
        item: dict[str, object],
        *,
        old_entries: tuple[DiaryEntry, ...],
        updated_entries: tuple[DiaryEntry, ...],
        item_index: int,
    ) -> dict[str, object]:
        updated = dict(item)
        food_version_id = item.get("food_version_id")
        if food_version_id is None:
            return updated

        if (
            item_index < len(old_entries)
            and old_entries[item_index].food_version_id == food_version_id
            and item_index < len(updated_entries)
        ):
            entry = updated_entries[item_index]
            updated["quantity_g"] = entry.quantity_g
            updated["meal_type"] = entry.meal_type
            updated["food_version_id"] = entry.food_version_id
            if entry.food_version_id != food_version_id:
                updated["previous_food_version_id"] = str(food_version_id)
                updated["resolution_reason"] = "user_edited_food_match"
            return updated

        for entry in updated_entries:
            if entry.food_version_id == food_version_id:
                updated["quantity_g"] = entry.quantity_g
                updated["meal_type"] = entry.meal_type
                break
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

    def export_data(self) -> dict[str, Any]:
        return {
            "format": "health-monitor.snapshot",
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "data": self._snapshot(),
        }

    def import_data(self, payload: dict[str, Any]) -> dict[str, int]:
        if not self._is_empty():
            raise ValueError("import target must be empty")
        if payload.get("format") != "health-monitor.snapshot":
            raise ValueError("unsupported import format")
        if int(payload.get("version", 0)) != 1:
            raise ValueError("unsupported import version")
        snapshot = dict(payload.get("data") or {})
        if int(snapshot.get("version", 0)) != 1:
            raise ValueError("unsupported snapshot version")
        self._restore_snapshot(snapshot)
        self._persist()
        return {
            "households": len(self.households),
            "people": len(self.people),
            "goal_profiles": len(self.goal_profiles),
            "foods": len(self.catalog.foods),
            "food_versions": len(self.catalog.versions),
            "food_aliases": len(self.catalog.aliases),
            "barcode_associations": len(self.catalog.barcode_associations),
            "diary_entries": len(self.diary.entries),
            "weight_entries": len(self.weights),
            "proposals": len(self.proposals.proposals),
            "agent_runs": len(self.agent_runs),
            "agent_tool_calls": len(self.agent_tool_calls),
            "agent_chat_turns": len(self.chat_turns),
            "jobs": len(self.jobs),
            "review_notes": len(self.review_notes),
            "attachment_objects": len(self.attachments),
            "recipe_versions": len(self.recipe_versions),
        }

    def recipe_version_for_food_version(self, food_version_id: str) -> RecipeVersion | None:
        return self.recipe_versions.get(food_version_id)

    def review_notes_for_person(self, person_id: str) -> tuple[ReviewNote, ...]:
        self._require_person(person_id)
        notes = [note for note in self.review_notes.values() if note.person_id == person_id]
        notes.sort(key=lambda note: (note.starts_on or date.min, note.created_at))
        return tuple(notes)

    def day_summary(self, person_id: str, day: date) -> DaySummary:
        self._require_person(person_id)
        meals: dict[str, list[DaySummaryEntry]] = {}
        totals = Nutrients()
        for entry in self.diary.entries_for_day(person_id, day):
            version = self.catalog.get_version(entry.food_version_id)
            food = self.catalog.foods[version.food_id]
            nutrients = version.nutrients_per_100g.scale(entry.quantity_g / 100)
            totals += nutrients
            evidence_status = day_summary_evidence_status(entry.source, version.source)
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
                    evidence_status=evidence_status,
                    confidence=day_summary_confidence(
                        evidence_status=evidence_status,
                        version_confidence=version.confidence,
                    ),
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

    def diary_entries_range(self, person_id: str, start: date, end: date) -> tuple[DaySummaryEntry, ...]:
        self._require_person(person_id)
        if end < start:
            raise ValueError("end must be on or after start")

        entries: list[DaySummaryEntry] = []
        current = start
        while current <= end:
            summary = self.day_summary(person_id, current)
            for meal_entries in summary.meals.values():
                entries.extend(meal_entries)
            current += timedelta(days=1)
        entries.sort(key=lambda entry: entry.logged_at)
        return tuple(entries)

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

    def update_weight_entry(
        self,
        *,
        entry_id: str,
        measured_at_local: str | None = None,
        weight_kg: float | None = None,
        note: str | None = None,
    ) -> WeightEntry:
        entry = self.weights[entry_id]
        person = self._require_person(entry.person_id)
        measured_at = (
            self._parse_person_datetime(measured_at_local, person)
            if measured_at_local is not None
            else entry.measured_at
        )
        updated = WeightEntry(
            id=entry.id,
            person_id=entry.person_id,
            measured_at=measured_at,
            weight_kg=round(float(weight_kg), 2) if weight_kg is not None else entry.weight_kg,
            note=note,
            source=entry.source,
        )
        self.weights[entry_id] = updated
        self._persist()
        return updated

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

    def rolling_summary(self, *, person_id: str, end: date, days: int = 7) -> RollingSummary:
        self._require_person(person_id)
        if days < 1:
            raise ValueError("days must be at least 1")
        start = end - timedelta(days=days - 1)
        daily: dict[date, Nutrients] = {}
        current = start
        while current <= end:
            summary = self.day_summary(person_id, current)
            if any(entries for entries in summary.meals.values()):
                daily[current] = summary.totals
            current += timedelta(days=1)

        # Mean and population standard deviation over days that have entries —
        # empty days would drag averages toward zero and hide the real pattern.
        values = list(daily.values())
        nutrient_fields = ("calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg")
        means: dict[str, float] = {}
        deviations: dict[str, float] = {}
        for field_name in nutrient_fields:
            data = [float(getattr(nutrients, field_name) or 0) for nutrients in values]
            if data:
                mean = sum(data) / len(data)
                variance = sum((value - mean) ** 2 for value in data) / len(data)
            else:
                mean = 0.0
                variance = 0.0
            means[field_name] = round(mean, 1)
            deviations[field_name] = round(variance ** 0.5, 1)
        return RollingSummary(
            person_id=person_id,
            start=start,
            end=end,
            days=days,
            days_with_data=len(values),
            daily=daily,
            averages=Nutrients(**means),
            stddev=Nutrients(**deviations),
        )

    def _model_available(self) -> bool:
        now = time.monotonic()
        if self._model_health_cache is not None and now - self._model_health_cache[0] < 10:
            return self._model_health_cache[1]
        if self.model_health_checker is not None:
            available = bool(self.model_health_checker())
        else:
            try:
                request = urllib.request.urlopen(
                    f"{self.ollama_base_url.rstrip('/')}/api/tags", timeout=1.5
                )
                with request as response:
                    json.loads(response.read().decode("utf-8"))
                available = True
            except Exception:
                available = False
        self._model_health_cache = (now, available)
        return available

    def _ensure_model_available(self, settings: dict[str, Any], *, replay_message: str) -> None:
        if not self.require_model:
            return
        if settings.get("agent_runtime") != "pydantic-ai":
            return
        if self._model_available():
            return
        raise ModelUnavailableError(
            "model runtime is unavailable and deterministic fallback is disabled "
            f"(require_model=true, ollama={self.ollama_base_url})",
            replay_message=replay_message,
        )

    def _agent_settings(self, agent_settings: dict[str, Any] | None) -> dict[str, Any]:
        settings = dict(agent_settings or {})
        settings.setdefault("agent_runtime", self.agent_runtime)
        settings.setdefault("model_provider", self.model_provider)
        settings.setdefault("max_tool_loops", 6)
        settings.setdefault("effort", "normal")
        if self.agent_model is not None:
            settings.setdefault("model_name", self.agent_model)
        elif "model_profile" in settings:
            settings.setdefault("model_name", settings["model_profile"])
        else:
            settings.setdefault("model_name", "deterministic")
        return settings

    def _run_metadata(self, settings: dict[str, Any]) -> dict[str, Any]:
        return {
            "runtime": str(settings.get("agent_runtime") or "deterministic"),
            "model_name": str(settings.get("model_name") or settings.get("model_profile") or "deterministic"),
        }

    def _current_fallback_reason(self, run: AgentRun) -> str | None:
        current = self.agent_runs.get(run.id)
        return current.fallback_reason if current is not None else run.fallback_reason

    def _build_agent_context(self, person_id: str, today: date) -> dict[str, Any]:
        person = self._require_person(person_id)
        active_goal = self.active_goal_profile(person_id=person_id, day=today)
        recent_turns = self.chat_turns_for_person(person_id)[-10:]
        open_proposals = [
            proposal
            for proposal in self.list_proposals(person_id=person_id)
            if proposal.status in {"draft", "needs_clarification"}
        ][:10]
        day_summaries: list[dict[str, Any]] = []
        first_day = today - timedelta(days=13)
        current = first_day
        full_days_start = today - timedelta(days=4)
        while current <= today:
            summary = self.day_summary(person_id, current)
            entries = [entry for meal_entries in summary.meals.values() for entry in meal_entries]
            base: dict[str, Any] = {
                "day": current.isoformat(),
                "totals": self._nutrients_context(summary.totals.rounded()),
                "target": self._nutrients_context(summary.target) if summary.target is not None else None,
                "entries_count": len(entries),
            }
            if current >= full_days_start:
                base["meals"] = {
                    meal_type: [
                        {
                            "logged_at": entry.logged_at.isoformat(),
                            "meal_type": entry.meal_type,
                            "food_name": entry.food_name,
                            "brand": entry.brand,
                            "food_version_label": entry.food_version_label,
                            "quantity_g": entry.quantity_g,
                            "nutrients": self._nutrients_context(entry.nutrients.rounded()),
                            "source": entry.source,
                            "evidence_status": entry.evidence_status,
                            "confidence": entry.confidence,
                        }
                        for entry in meal_entries
                    ]
                    for meal_type, meal_entries in summary.meals.items()
                }
            else:
                base["foods"] = sorted({entry.food_name for entry in entries})[:8]
            day_summaries.append(base)
            current += timedelta(days=1)

        return {
            "today": today.isoformat(),
            "person": {
                "id": person.id,
                "household_id": person.household_id,
                "name": person.name,
                "timezone": person.timezone,
                "birth_date": person.birth_date.isoformat() if person.birth_date is not None else None,
                "sex": person.sex,
                "height_cm": person.height_cm,
                "activity_level": person.activity_level,
            },
            "active_goal": {
                "id": active_goal.id,
                "starts_on": active_goal.starts_on.isoformat(),
                "ends_on": active_goal.ends_on.isoformat() if active_goal.ends_on is not None else None,
                "targets": self._nutrients_context(active_goal.targets),
                "notes": active_goal.notes,
            }
            if active_goal is not None
            else None,
            "recent_chat_turns": [
                {
                    "created_at": turn.created_at.isoformat(),
                    "user": turn.user_message,
                    "assistant": turn.assistant_message,
                    "behavior_label": turn.behavior_label,
                    "proposal_id": turn.proposal_id,
                }
                for turn in recent_turns
            ],
            "open_proposals": [
                {
                    "id": proposal.id,
                    "status": proposal.status,
                    "proposal_type": proposal.proposal_type,
                    "summary": proposal.summary,
                    "created_at": proposal.created_at.isoformat(),
                    "entries_count": len(proposal.entries),
                    "totals": self._nutrients_context(proposal.totals.rounded()),
                }
                for proposal in open_proposals
            ],
            "day_summaries": day_summaries,
        }

    def _agent_context_message(self, person_id: str, today: date, message: str) -> str:
        context = self._build_agent_context(person_id, today)
        return (
            "Agent context JSON:\n"
            f"{json.dumps(context, ensure_ascii=False, sort_keys=True)}\n\n"
            "User message:\n"
            f"{message}"
        )

    def _nutrients_context(self, nutrients: Nutrients) -> dict[str, float]:
        rounded = nutrients.rounded()
        return {
            "calories_kcal": rounded.calories_kcal,
            "protein_g": rounded.protein_g,
            "carbs_g": rounded.carbs_g,
            "fat_g": rounded.fat_g,
            "fiber_g": rounded.fiber_g,
            "sodium_mg": rounded.sodium_mg,
        }

    def _try_pydantic_ai_chat(
        self,
        *,
        person_id: str,
        message: str,
        today: date,
        run: AgentRun,
        settings: dict[str, Any],
    ) -> AgentChatResponse | None:
        if settings.get("agent_runtime") != "pydantic-ai":
            return None
        metadata = self._run_metadata(settings)
        person = self._require_person(person_id)
        agent = PydanticAINutritionAgent(
            model_name=metadata["model_name"],
            ollama_base_url=self.ollama_base_url,
        )
        try:
            response = agent.answer(
                deps=AgentDeps(
                    service=self,
                    person_id=person_id,
                    household_id=person.household_id,
                    today=today,
                    settings=settings,
                    source_config={
                        "openfoodfacts_enabled": self.food_lookup_provider is not None,
                        "research_lookup_enabled": self.research_lookup_provider is not None,
                        "ocr_enabled": self.label_text_extractor is not None,
                    },
                ),
                message=message,
            )
        except PydanticAIUnavailable as exc:
            fallback_reason = f"pydantic_ai unavailable: {exc}"
            self._record_agent_tool_call(
                run=run,
                tool_name="pydantic_ai_chat",
                input_summary="runtime=pydantic-ai",
                output_summary="pydantic_ai unavailable; using deterministic fallback",
                status="failed",
                error=str(exc),
            )
            self.agent_runs[run.id] = replace(
                run,
                status="fallback",
                runtime=metadata["runtime"],
                model_name=metadata["model_name"],
                tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
                fallback_reason=fallback_reason,
            )
            if self.require_model:
                raise ModelUnavailableError(fallback_reason, replay_message=message)
            return None
        except Exception as exc:
            fallback_reason = f"pydantic_ai failed: {exc}"
            self._record_agent_tool_call(
                run=run,
                tool_name="pydantic_ai_chat",
                input_summary="runtime=pydantic-ai",
                output_summary="pydantic_ai failed; using deterministic fallback",
                status="failed",
                error=str(exc),
            )
            self.agent_runs[run.id] = replace(
                run,
                status="fallback",
                runtime=metadata["runtime"],
                model_name=metadata["model_name"],
                tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
                fallback_reason=fallback_reason,
            )
            if self.require_model:
                raise ModelUnavailableError(fallback_reason, replay_message=message)
            return None

        self._record_agent_tool_call(
            run=run,
            tool_name="pydantic_ai_chat",
            input_summary="runtime=pydantic-ai",
            output_summary=f"behavior={response.behavior_label}",
        )
        self.agent_runs[run.id] = replace(
            run,
            status="answered",
            runtime=metadata["runtime"],
            model_name=metadata["model_name"],
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            fallback_reason=None,
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=response.message,
            behavior_label=response.behavior_label,
            citations=response.citations,
            proposal_id=response.proposal_id,
        )

    def _try_pydantic_ai_text_meal(
        self,
        *,
        person_id: str,
        logged_at_local: str,
        text: str,
        run: AgentRun,
        settings: dict[str, Any],
    ) -> CreateDiaryEntriesProposal | None:
        if settings.get("agent_runtime") != "pydantic-ai":
            return None
        metadata = self._run_metadata(settings)
        person = self._require_person(person_id)
        agent = PydanticAINutritionAgent(
            model_name=metadata["model_name"],
            ollama_base_url=self.ollama_base_url,
        )
        try:
            response = agent.draft_text_meal(
                deps=AgentDeps(
                    service=self,
                    person_id=person_id,
                    household_id=person.household_id,
                    today=self._parse_person_datetime(logged_at_local, person).date(),
                    settings=settings,
                    source_config={
                        "openfoodfacts_enabled": self.food_lookup_provider is not None,
                        "research_lookup_enabled": self.research_lookup_provider is not None,
                        "ocr_enabled": self.label_text_extractor is not None,
                    },
                ),
                logged_at_local=logged_at_local,
                text=text,
            )
        except PydanticAIUnavailable as exc:
            fallback_reason = f"pydantic_ai unavailable: {exc}"
            self._record_agent_tool_call(
                run=run,
                tool_name="pydantic_ai_text_meal",
                input_summary="runtime=pydantic-ai",
                output_summary="pydantic_ai unavailable; using deterministic fallback",
                status="failed",
                error=str(exc),
            )
            self.agent_runs[run.id] = replace(
                run,
                status="fallback",
                runtime=metadata["runtime"],
                model_name=metadata["model_name"],
                tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
                fallback_reason=fallback_reason,
            )
            if self.require_model:
                raise ModelUnavailableError(fallback_reason, replay_message=text)
            return None
        except Exception as exc:
            fallback_reason = f"pydantic_ai failed: {exc}"
            self._record_agent_tool_call(
                run=run,
                tool_name="pydantic_ai_text_meal",
                input_summary="runtime=pydantic-ai",
                output_summary="pydantic_ai failed; using deterministic fallback",
                status="failed",
                error=str(exc),
            )
            self.agent_runs[run.id] = replace(
                run,
                status="fallback",
                runtime=metadata["runtime"],
                model_name=metadata["model_name"],
                tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
                fallback_reason=fallback_reason,
            )
            if self.require_model:
                raise ModelUnavailableError(fallback_reason, replay_message=text)
            return None

        if response.proposal_id is None:
            self._record_agent_tool_call(
                run=run,
                tool_name="pydantic_ai_text_meal",
                input_summary="runtime=pydantic-ai",
                output_summary="live model did not draft a proposal; using deterministic fallback",
                status="failed",
                error="missing proposal_id",
            )
            self.agent_runs[run.id] = replace(
                run,
                status="fallback",
                runtime=metadata["runtime"],
                model_name=metadata["model_name"],
                tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
                fallback_reason="pydantic_ai text meal returned no proposal_id",
            )
            return None

        proposal = self.get_proposal(response.proposal_id)
        updated = replace(
            proposal,
            payload={
                **proposal.payload,
                "live_agent_orchestration": {
                    "runtime": metadata["runtime"],
                    "model_name": metadata["model_name"],
                    "deterministic_source_agent_run_id": proposal.source_agent_run_id,
                },
            },
            source_agent_run_id=run.id,
        )
        self.proposals.proposals[updated.id] = updated
        self._record_agent_tool_call(
            run=run,
            tool_name="pydantic_ai_text_meal",
            input_summary="runtime=pydantic-ai",
            output_summary=f"proposal={updated.id}; behavior={response.behavior_label}",
            source_record_ids=(updated.id,),
        )
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=updated.id,
            runtime=metadata["runtime"],
            model_name=metadata["model_name"],
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            fallback_reason=None,
        )
        self._persist()
        return updated

    def chat(
        self,
        *,
        person_id: str,
        message: str,
        today: date,
        agent_settings: dict[str, Any] | None = None,
        attachment_ids: Sequence[str] | None = None,
        intent: str | None = None,
    ) -> AgentChatResponse:
        settings = self._agent_settings(agent_settings)
        self._ensure_model_available(settings, replay_message=message)
        person = self._require_person(person_id)
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=message,
            settings=settings,
            status="started",
            **self._run_metadata(settings),
        )
        self.agent_runs[run.id] = run

        def finish(response: AgentChatResponse) -> AgentChatResponse:
            self._record_agent_chat_turn(
                run=run,
                user_message=message,
                response=response,
            )
            self._persist()
            return response

        intent_block = AGENT_INTENT_TEMPLATES.get(str(intent)) if intent is not None else None
        user_payload = message
        if attachment_ids:
            user_payload = (
                f"{message}\n\nAttachment ids available to inspect: "
                f"{', '.join(str(item) for item in attachment_ids)}"
            ).strip()
        if intent_block:
            user_payload = f"Intent context: {intent_block}\n\nUser message: {user_payload}"
        agent_message = self._agent_context_message(person_id, today, user_payload)

        pydantic_response = self._try_pydantic_ai_chat(
            person_id=person_id,
            message=agent_message,
            today=today,
            run=run,
            settings=settings,
        )
        if pydantic_response is not None:
            return finish(pydantic_response)

        response = AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=(
                "O agente configurado não retornou uma resposta. Tente novamente quando "
                "o runtime de modelo estiver disponível."
            ),
            behavior_label="answer_question",
        )
        self.agent_runs[run.id] = replace(
            run,
            status="answered",
            runtime=self._run_metadata(settings)["runtime"],
            model_name=self._run_metadata(settings)["model_name"],
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            fallback_reason=self._current_fallback_reason(run),
        )
        return finish(response)

    def _create_range_estimate_proposal(
        self,
        *,
        person_id: str,
        message: str,
        today: date,
        run: AgentRun,
        range_estimate: ParsedRangeEstimate,
    ) -> CreateDiaryEntriesProposal:
        person = self._require_person(person_id)
        logged_at = chat_default_logged_at(message, today=today)
        low_kcal = range_estimate.low_kcal
        high_kcal = range_estimate.high_kcal
        midpoint_kcal = (low_kcal + high_kcal) / 2
        food_id = self._next_id("food")
        food_version_id = self._next_id("food_version")
        entry = DiaryEntry(
            id=self._next_id("diary_entry"),
            person_id=person_id,
            logged_at=logged_at,
            meal_type=infer_meal_type(logged_at),
            food_version_id=food_version_id,
            quantity_g=100,
            source="range_estimate_proposal",
        )
        estimate_range = {
            "low_kcal": low_kcal,
            "high_kcal": high_kcal,
            "midpoint_kcal": midpoint_kcal,
        }
        pending_version = {
            "household_id": person.household_id,
            "food_id": food_id,
            "food_version_id": food_version_id,
            "food_name": range_estimate.label,
            "brand": None,
            "version_label": "faixa estimada",
            "nutrients_per_100g": nutrients_to_snapshot(
                Nutrients(calories_kcal=midpoint_kcal).rounded()
            ),
            "source": "range_estimate",
            "source_type": "range_estimate",
            "source_name": "User-provided calorie range",
            "phrase": normalize_food_phrase(range_estimate.label),
            "barcode": None,
            "serving_size_g": None,
            "confidence": 0.45,
            "estimate_range": dict(estimate_range),
        }
        payload: dict[str, Any] = {
            "estimated_food_versions": [pending_version],
            "estimate_range": dict(estimate_range),
            "raw_text": message,
        }
        superseded_target = self._find_open_range_estimate_target(
            person_id=person_id,
            logged_at=logged_at,
        )
        if superseded_target is not None:
            original = self.proposals.proposals[superseded_target]
            payload["amended_from_proposal_id"] = original.id
            payload["previous_estimate_range"] = original.payload.get("estimate_range")

        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=(entry,),
                proposal_type="diary_entries_with_estimates",
                summary=(
                    f"{range_estimate.label}: "
                    f"{low_kcal:g}-{high_kcal:g} kcal estimadas"
                ),
                payload=payload,
                totals=self._proposal_entries_total((entry,), payload=payload),
                evidence=(
                    {
                        "source_type": "range_estimate",
                        "source_text": range_estimate.source_text,
                        "food_version_id": food_version_id,
                        "quantity_g": 100,
                        "estimate_range": dict(estimate_range),
                        "confidence": 0.45,
                    },
                ),
                source_agent_run_id=run.id,
            )
        )
        if superseded_target is not None:
            self.proposals.supersede(superseded_target, superseded_by_proposal_id=proposal.id)
        self._persist()
        return proposal

    def _find_open_range_estimate_target(
        self,
        *,
        person_id: str,
        logged_at: datetime,
    ) -> str | None:
        candidates: list[CreateDiaryEntriesProposal] = []
        for proposal in self.proposals.proposals.values():
            if proposal.person_id != person_id or proposal.status != "draft" or not proposal.entries:
                continue
            if proposal.proposal_type != "diary_entries_with_estimates":
                continue
            if not proposal.payload.get("estimate_range"):
                continue
            latest_entry_time = max(entry.logged_at for entry in proposal.entries)
            if latest_entry_time.date() != logged_at.date():
                continue
            if abs((logged_at - latest_entry_time).total_seconds()) > 4 * 60 * 60:
                continue
            candidates.append(proposal)
        if not candidates:
            return None
        candidates.sort(key=lambda proposal: (proposal.created_at, proposal.id), reverse=True)
        return candidates[0].id

    def draft_range_estimate_proposal(
        self,
        *,
        person_id: str,
        label: str,
        low_kcal: float,
        high_kcal: float,
        day: date,
        meal_type: str | None = None,
        agent_settings: dict[str, Any] | None = None,
    ) -> CreateDiaryEntriesProposal:
        settings = self._agent_settings(agent_settings)
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=f"{label}: {low_kcal:g}-{high_kcal:g} kcal",
            settings=settings,
            status="started",
            **self._run_metadata(settings),
        )
        self.agent_runs[run.id] = run
        estimate = ParsedRangeEstimate(
            label=label,
            low_kcal=float(low_kcal),
            high_kcal=float(high_kcal),
            source_text=run.input_text,
        )
        proposal = self._create_range_estimate_proposal(
            person_id=person_id,
            message=f"{meal_type or ''} {run.input_text}".strip(),
            today=day,
            run=run,
            range_estimate=estimate,
        )
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=proposal.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            fallback_reason=self._current_fallback_reason(run),
        )
        self._persist()
        return proposal

    def draft_structured_meal_proposal(
        self,
        *,
        person_id: str,
        items: Sequence[dict[str, Any]],
        day: date,
        time_text: str | None = None,
        meal_type: str | None = None,
        agent_settings: dict[str, Any] | None = None,
        source_text: str = "structured meal draft",
    ) -> CreateDiaryEntriesProposal:
        settings = self._agent_settings(agent_settings)
        person = self._require_person(person_id)
        logged_at = self._structured_logged_at(person, day=day, time_text=time_text)
        default_meal_type = normalize_meal_type(meal_type) if meal_type else infer_meal_type(logged_at)
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=source_text,
            settings=settings,
            status="started",
            **self._run_metadata(settings),
        )
        self.agent_runs[run.id] = run
        entries, evidence, totals, estimated_food_versions = self._draft_structured_meal_entries(
            person=person,
            run=run,
            items=items,
            logged_at=logged_at,
            default_meal_type=default_meal_type,
            settings=settings,
        )
        proposal_type = "diary_entries_with_estimates" if estimated_food_versions else "diary_entries"
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=tuple(entries),
                proposal_type=proposal_type,
                summary=f"{len(entries)} diary entries drafted from structured meal items",
                payload={
                    "estimated_food_versions": estimated_food_versions,
                    "raw_text": source_text,
                    "structured_items": [dict(item) for item in items],
                },
                totals=totals,
                evidence=tuple(evidence),
                source_agent_run_id=run.id,
            )
        )
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=proposal.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            fallback_reason=self._current_fallback_reason(run),
        )
        self._persist()
        return proposal

    def amend_structured_meal_proposal(
        self,
        *,
        proposal_id: str,
        person_id: str,
        add: Sequence[dict[str, Any]] = (),
        remove: Sequence[dict[str, Any]] = (),
        set_quantity: Sequence[dict[str, Any]] = (),
        agent_settings: dict[str, Any] | None = None,
        source_text: str = "structured meal amendment",
    ) -> CreateDiaryEntriesProposal:
        settings = self._agent_settings(agent_settings)
        original = self.proposals.proposals[proposal_id]
        if original.person_id != person_id:
            raise ValueError("proposal belongs to a different person")
        if original.status != "draft":
            raise ValueError("only draft proposals can be amended")
        if original.proposal_type not in {"diary_entries", "diary_entries_with_estimates"}:
            raise ValueError(f"proposal type cannot be amended as a meal: {original.proposal_type}")
        logged_at = max((entry.logged_at for entry in original.entries), default=self._structured_logged_at(self._require_person(person_id), day=date.today()))
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=source_text,
            settings=settings,
            status="started",
            **self._run_metadata(settings),
        )
        self.agent_runs[run.id] = run
        pending_versions = {
            str(item["food_version_id"]): dict(item)
            for item in original.payload.get("estimated_food_versions", [])
        }
        updated_entries = [
            DiaryEntry(
                id=self._next_id("diary_entry"),
                person_id=entry.person_id,
                logged_at=entry.logged_at,
                meal_type=entry.meal_type,
                food_version_id=entry.food_version_id,
                quantity_g=entry.quantity_g,
                source=entry.source,
                deleted_at=entry.deleted_at,
            )
            for entry in original.entries
        ]
        evidence = [dict(item) for item in original.evidence]
        warnings: list[str] = []

        for removal in remove:
            phrase = str(removal.get("phrase") or "").strip()
            quantity_g = float(removal.get("quantity_g") or 0)
            match_index = self._structured_entry_index(
                updated_entries,
                phrase=phrase,
                entry_id=str(removal.get("entry_id") or ""),
                pending_versions=pending_versions,
            )
            if match_index is None:
                warnings.append(f"Could not find an open proposal item matching '{phrase}'.")
                continue
            entry = updated_entries[match_index]
            if quantity_g <= 0 or quantity_g >= entry.quantity_g:
                removed = updated_entries.pop(match_index)
                removed_quantity = removed.quantity_g
                action = "remove_entry"
            else:
                removed_quantity = quantity_g
                updated_entries[match_index] = replace(entry, quantity_g=entry.quantity_g - quantity_g)
                action = "subtract_quantity"
            evidence.append(
                {
                    "source_type": "structured_meal_amendment",
                    "source_text": source_text,
                    "action": action,
                    "phrase": phrase,
                    "food_version_id": entry.food_version_id,
                    "quantity_g": removed_quantity,
                    "confidence": 0.9,
                }
            )

        for quantity_update in set_quantity:
            match_index = self._structured_entry_index(
                updated_entries,
                phrase=str(quantity_update.get("phrase") or "").strip(),
                entry_id=str(quantity_update.get("entry_id") or ""),
                pending_versions=pending_versions,
            )
            quantity_g = float(quantity_update.get("quantity_g") or 0)
            if match_index is None or quantity_g <= 0:
                warnings.append("Could not apply one quantity update.")
                continue
            entry = updated_entries[match_index]
            updated_entries[match_index] = replace(entry, quantity_g=quantity_g)
            evidence.append(
                {
                    "source_type": "structured_meal_amendment",
                    "source_text": source_text,
                    "action": "set_quantity",
                    "food_version_id": entry.food_version_id,
                    "previous_quantity_g": entry.quantity_g,
                    "quantity_g": quantity_g,
                    "confidence": 0.95,
                }
            )

        person = self._require_person(person_id)
        added_entries, added_evidence, _added_totals, new_pending_versions = self._draft_structured_meal_entries(
            person=person,
            run=run,
            items=add,
            logged_at=logged_at,
            default_meal_type=original.entries[0].meal_type if original.entries else infer_meal_type(logged_at),
            settings=settings,
            source_type="structured_meal_amendment",
        )
        updated_entries.extend(added_entries)
        evidence.extend(added_evidence)
        if not updated_entries:
            raise ValueError("amendment would leave the proposal empty")
        referenced_version_ids = {entry.food_version_id for entry in updated_entries}
        payload = {
            **original.payload,
            "estimated_food_versions": [
                pending
                for pending in (
                    *original.payload.get("estimated_food_versions", []),
                    *new_pending_versions,
                )
                if str(pending["food_version_id"]) in referenced_version_ids
            ],
            "amended_from_proposal_id": original.id,
            "raw_amendment_text": source_text,
            "structured_amendment": {
                "add": [dict(item) for item in add],
                "remove": [dict(item) for item in remove],
                "set_quantity": [dict(item) for item in set_quantity],
            },
            "amendment_warnings": warnings,
        }
        proposal_type = "diary_entries_with_estimates" if payload.get("estimated_food_versions") else "diary_entries"
        amended = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=tuple(updated_entries),
                proposal_type=proposal_type,
                summary=f"{len(updated_entries)} diary entries drafted after structured meal amendment",
                payload=payload,
                totals=self._proposal_entries_total(tuple(updated_entries), payload=payload),
                evidence=tuple(evidence),
                source_agent_run_id=run.id,
            )
        )
        self.proposals.supersede(original.id, superseded_by_proposal_id=amended.id)
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=amended.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            fallback_reason=self._current_fallback_reason(run),
        )
        self._persist()
        return amended

    def _draft_structured_meal_entries(
        self,
        *,
        person: Person,
        run: AgentRun,
        items: Sequence[dict[str, Any]],
        logged_at: datetime,
        default_meal_type: str,
        settings: dict[str, Any],
        source_type: str = "structured_meal",
    ) -> tuple[list[DiaryEntry], list[dict[str, object]], Nutrients, list[dict[str, object]]]:
        entries: list[DiaryEntry] = []
        evidence: list[dict[str, object]] = []
        estimated_food_versions: list[dict[str, object]] = []
        totals = Nutrients()
        for item in items:
            phrase = str(item.get("phrase") or "").strip()
            quantity_g = float(item.get("quantity_g") or item.get("quantity") or 0)
            if not phrase or quantity_g <= 0:
                raise ValueError("structured meal items require phrase and positive quantity_g")
            resolved = self._resolve_meal_item_food(
                person=person,
                run=run,
                phrase=phrase,
                settings=settings,
            )
            if resolved.pending_version is not None:
                estimated_food_versions.append(resolved.pending_version)
            item_meal_type = normalize_meal_type(str(item.get("meal_type") or default_meal_type))
            entry = DiaryEntry(
                id=self._next_id("diary_entry"),
                person_id=person.id,
                logged_at=logged_at,
                meal_type=item_meal_type,
                food_version_id=resolved.food_version_id,
                quantity_g=quantity_g,
                source="agent_structured_proposal",
            )
            entries.append(entry)
            totals += resolved.version.nutrients_per_100g.scale(quantity_g / 100)
            evidence.append(
                {
                    "source_type": source_type,
                    "source_text": str(item.get("source_text") or phrase),
                    "phrase": phrase,
                    "food_id": resolved.version.food_id,
                    "food_name": resolved.food_name,
                    "food_version_id": resolved.food_version_id,
                    "quantity_g": quantity_g,
                    "resolution_reason": resolved.resolution_reason,
                    "confidence": resolved.confidence,
                }
            )
        return entries, evidence, totals, estimated_food_versions

    def _structured_entry_index(
        self,
        entries: Sequence[DiaryEntry],
        *,
        phrase: str,
        entry_id: str,
        pending_versions: dict[str, dict[str, Any]],
    ) -> int | None:
        if entry_id:
            for index, entry in enumerate(entries):
                if entry.id == entry_id:
                    return index
        if phrase:
            for index, entry in enumerate(entries):
                if self._proposal_entry_matches_phrase(entry, phrase, pending_versions=pending_versions):
                    return index
        return None

    def _structured_logged_at(self, person: Person, *, day: date, time_text: str | None = None) -> datetime:
        cleaned_time = (time_text or "12:00:00").strip()
        if len(cleaned_time) == 5:
            cleaned_time = f"{cleaned_time}:00"
        return self._parse_person_datetime(f"{day.isoformat()}T{cleaned_time}", person)

    def propose_text_meal(
        self,
        *,
        person_id: str,
        logged_at_local: str,
        text: str,
        agent_settings: dict[str, Any] | None = None,
        amend_proposal_id: str | None = None,
    ) -> CreateDiaryEntriesProposal:
        settings = self._agent_settings(agent_settings)
        self._ensure_model_available(settings, replay_message=text)
        person = self._require_person(person_id)
        logged_at = self._parse_person_datetime(logged_at_local, person)
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=text,
            settings=settings,
            status="started",
            **self._run_metadata(settings),
        )
        self.agent_runs[run.id] = run

        amendment_target_id = amend_proposal_id or self._find_open_meal_amendment_target(
            person_id=person_id,
            logged_at=logged_at,
            text=text,
        )
        if amendment_target_id is not None:
            proposal = self._create_amended_text_meal_proposal(
                proposal_id=amendment_target_id,
                person_id=person_id,
                text=text,
                run=run,
                logged_at=logged_at,
                settings=settings,
            )
            self._persist()
            return proposal

        repeated_meal = parse_repeated_meal_reference(text, default_logged_at=logged_at)
        pydantic_proposal = self._try_pydantic_ai_text_meal(
            person_id=person_id,
            logged_at_local=logged_at_local,
            text=text,
            run=run,
            settings=settings,
        )
        if pydantic_proposal is not None:
            return pydantic_proposal
        if repeated_meal is not None:
            source_day, meal_type = repeated_meal
            proposal = self._create_repeated_meal_proposal(
                person_id=person_id,
                text=text,
                run=run,
                target_logged_at=logged_at,
                source_day=source_day,
                meal_type=meal_type,
            )
            self._persist()
            return proposal
        try:
            parsed_logged_at, items = parse_text_meal_items(text, default_logged_at=logged_at)
        except ValueError as exc:
            proposal = self._create_text_meal_clarification_proposal(
                person_id=person_id,
                text=text,
                run=run,
                logged_at=logged_at,
                unresolved_items=(
                    ParsedMealItem(
                        phrase=text.casefold().strip(),
                        quantity_g=0,
                        source_text=text,
                        evidence={
                            "quantity_basis": "unparseable_text",
                            "parse_error": str(exc),
                        },
                    ),
                ),
                missing_fields=("parseable_food_item",),
                summary="Need a clearer food and quantity before logging this meal.",
            )
            self._record_agent_tool_call(
                run=run,
                tool_name="parse_text_meal",
                input_summary="text meal parse",
                output_summary="needs clarification",
                status="failed",
                error=str(exc),
            )
            self._persist()
            return proposal
        unsupported_items = [
            item
            for item in items
            if item.evidence.get("quantity_basis") == "unsupported_unit"
        ]
        if unsupported_items:
            proposal = self._create_text_meal_clarification_proposal(
                person_id=person_id,
                text=text,
                run=run,
                logged_at=parsed_logged_at,
                unresolved_items=unsupported_items,
            )
            self._persist()
            return proposal
        entries: list[DiaryEntry] = []
        evidence: list[dict[str, object]] = []
        estimated_food_versions: list[dict[str, object]] = []
        totals = Nutrients()
        for item in items:
            ambiguity = self._ambiguous_local_food_reference(
                household_id=person.household_id,
                person_id=person.id,
                phrase=item.phrase,
            )
            if ambiguity is not None:
                proposal = self._create_text_meal_clarification_proposal(
                    person_id=person_id,
                    text=text,
                    run=run,
                    logged_at=parsed_logged_at,
                    unresolved_items=(item,),
                    missing_fields=("food_version_id",),
                    summary="Need to know which food to use before logging this meal.",
                    candidate_overrides={item.phrase: ambiguity.candidates},
                )
                self._persist()
                return proposal
            resolved = self._resolve_meal_item_food(
                person=person,
                run=run,
                phrase=item.phrase,
                settings=settings,
            )
            if resolved.pending_version is not None:
                estimated_food_versions.append(resolved.pending_version)
            version = resolved.version
            food_version_id = resolved.food_version_id
            source = resolved.source
            resolution_reason = resolved.resolution_reason
            confidence = resolved.confidence
            evidence_source_type = resolved.evidence_source_type
            evidence_source_details = resolved.evidence_source_details
            quantity_g = item.quantity_g
            if item.evidence.get("quantity_basis") == "serving_count":
                if version.serving_size_g is None:
                    proposal = self._create_text_meal_clarification_proposal(
                        person_id=person_id,
                        text=text,
                        run=run,
                        logged_at=parsed_logged_at,
                        unresolved_items=(item,),
                    )
                    self._persist()
                    return proposal
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
            evidence.append(
                {
                    "source_type": evidence_source_type,
                    "source_text": item.source_text,
                    "phrase": item.phrase,
                    "quantity_g": quantity_g,
                    "resolution_reason": resolution_reason,
                    "confidence": confidence,
                    "food_version_id": food_version_id,
                    **evidence_source_details,
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
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=proposal.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            fallback_reason=self._current_fallback_reason(run),
        )
        self._persist()
        return proposal

    def _resolve_meal_item_food(
        self,
        *,
        person: Person,
        run: AgentRun,
        phrase: str,
        settings: dict[str, Any],
    ) -> ResolvedMealFood:
        try:
            resolution = self.resolve_food_reference(
                household_id=person.household_id,
                person_id=person.id,
                phrase=phrase,
            )
            version = self.catalog.get_version(resolution.food_version_id)
            food = self.catalog.foods[version.food_id]
            self._record_agent_tool_call(
                run=run,
                tool_name="resolve_food_reference",
                input_summary=f"phrase={phrase}",
                output_summary=(
                    f"{food.name} / {version.label}; reason={resolution.reason}; "
                    f"confidence={resolution.confidence}"
                ),
                source_record_ids=(version.food_id, version.id),
            )
            return ResolvedMealFood(
                food_version_id=resolution.food_version_id,
                version=version,
                food_name=food.name,
                source="agent_proposal",
                resolution_reason=resolution.reason,
                confidence=resolution.confidence,
                evidence_source_type="local_food",
                evidence_source_details={},
                pending_version=None,
            )
        except ValueError as exc:
            self._record_agent_tool_call(
                run=run,
                tool_name="resolve_food_reference",
                input_summary=f"phrase={phrase}",
                output_summary="no local match",
                status="failed",
                error=str(exc),
            )
            if not settings.get("external_lookup", True):
                raise

        lookup_candidate = self._lookup_first_external_food_candidate(phrase)
        if lookup_candidate is not None:
            self._record_agent_tool_call(
                run=run,
                tool_name="lookup_external_food",
                input_summary=f"phrase={phrase}",
                output_summary=(
                    f"{lookup_candidate.product_name}; source={lookup_candidate.source_name}; "
                    f"confidence={lookup_candidate.confidence}"
                ),
                source_record_ids=(lookup_candidate.source_id,),
            )
            (
                _food_id,
                food_version_id,
                version,
                pending_lookup_version,
                evidence_source_details,
            ) = self._prepare_lookup_candidate_food_version(
                household_id=person.household_id,
                phrase=phrase,
                candidate=lookup_candidate,
                source="external_lookup",
                resolution_reason="external_lookup",
            )
            return ResolvedMealFood(
                food_version_id=food_version_id,
                version=version,
                food_name=str(pending_lookup_version.get("food_name", lookup_candidate.product_name)),
                source="agent_lookup_proposal",
                resolution_reason="external_lookup",
                confidence=lookup_candidate.confidence,
                evidence_source_type=lookup_candidate.source_type,
                evidence_source_details=evidence_source_details,
                pending_version=pending_lookup_version,
            )
        self._record_agent_tool_call(
            run=run,
            tool_name="lookup_external_food",
            input_summary=f"phrase={phrase}",
            output_summary="no external candidates",
        )

        research_candidate = (
            self._lookup_first_research_food_candidate(phrase)
            if settings.get("research_lookup", True)
            else None
        )
        if research_candidate is not None:
            self._record_agent_tool_call(
                run=run,
                tool_name="lookup_research_food",
                input_summary=f"phrase={phrase}",
                output_summary=(
                    f"{research_candidate.product_name}; source={research_candidate.source_name}; "
                    f"confidence={research_candidate.confidence}"
                ),
                source_record_ids=(research_candidate.source_id,),
            )
            (
                _food_id,
                food_version_id,
                version,
                pending_lookup_version,
                evidence_source_details,
            ) = self._prepare_lookup_candidate_food_version(
                household_id=person.household_id,
                phrase=phrase,
                candidate=research_candidate,
                source="research_lookup",
                resolution_reason="research_lookup",
            )
            return ResolvedMealFood(
                food_version_id=food_version_id,
                version=version,
                food_name=str(pending_lookup_version.get("food_name", research_candidate.product_name)),
                source="agent_research_lookup_proposal",
                resolution_reason="research_lookup",
                confidence=research_candidate.confidence,
                evidence_source_type=research_candidate.source_type,
                evidence_source_details=evidence_source_details,
                pending_version=pending_lookup_version,
            )
        if self.research_lookup_provider is not None and settings.get("research_lookup", True):
            self._record_agent_tool_call(
                run=run,
                tool_name="lookup_research_food",
                input_summary=f"phrase={phrase}",
                output_summary="no research candidates",
            )

        if self.estimator is None:
            raise ValueError(f"food reference could not be resolved or estimated: {phrase}")
        estimate = self.estimator.estimate(phrase)
        if estimate is None:
            self._record_agent_tool_call(
                run=run,
                tool_name="estimate_food",
                input_summary=f"phrase={phrase}",
                output_summary="no model estimate",
                status="failed",
                error="estimator returned no result",
            )
            raise ValueError(f"food reference could not be resolved or estimated: {phrase}")
        self._record_agent_tool_call(
            run=run,
            tool_name="estimate_food",
            input_summary=f"phrase={phrase}",
            output_summary=(
                f"{estimate.food_name}; source={estimate.source}; "
                f"confidence={estimate.confidence}"
            ),
        )
        food_id = self._next_id("food")
        food_version_id = self._next_id("food_version")
        version = FoodVersion(
            id=food_version_id,
            food_id=food_id,
            label="model estimate",
            nutrients_per_100g=estimate.nutrients_per_100g,
            source=estimate.source,
            confidence=estimate.confidence,
        )
        return ResolvedMealFood(
            food_version_id=food_version_id,
            version=version,
            food_name=estimate.food_name,
            source="agent_estimate_proposal",
            resolution_reason="model_estimate",
            confidence=estimate.confidence,
            evidence_source_type="model_estimate",
            evidence_source_details={},
            pending_version={
                "food_id": food_id,
                "food_version_id": food_version_id,
                "household_id": person.household_id,
                "food_name": estimate.food_name,
                "brand": None,
                "phrase": phrase,
                "version_label": "model estimate",
                "nutrients_per_100g": nutrients_to_snapshot(
                    estimate.nutrients_per_100g.rounded()
                ),
                "source": estimate.source,
                "confidence": estimate.confidence,
                "notes": estimate.notes,
            },
        )

    def _find_open_meal_amendment_target(
        self,
        *,
        person_id: str,
        logged_at: datetime,
        text: str,
    ) -> str | None:
        if not text_looks_like_meal_amendment(text):
            return None
        candidates: list[CreateDiaryEntriesProposal] = []
        for proposal in self.proposals.proposals.values():
            if proposal.person_id != person_id or proposal.status != "draft" or not proposal.entries:
                continue
            if proposal.proposal_type not in {"diary_entries", "diary_entries_with_estimates"}:
                continue
            latest_entry_time = max(entry.logged_at for entry in proposal.entries)
            if latest_entry_time.date() != logged_at.date():
                continue
            if abs((logged_at - latest_entry_time).total_seconds()) > 4 * 60 * 60:
                continue
            candidates.append(proposal)
        if not candidates:
            return None
        candidates.sort(key=lambda proposal: (proposal.created_at, proposal.id), reverse=True)
        return candidates[0].id

    def _create_amended_text_meal_proposal(
        self,
        *,
        proposal_id: str,
        person_id: str,
        text: str,
        run: AgentRun,
        logged_at: datetime,
        settings: dict[str, Any] | None = None,
    ) -> CreateDiaryEntriesProposal:
        settings = self._agent_settings(settings)
        original = self.proposals.proposals[proposal_id]
        pending_versions = {
            str(item["food_version_id"]): dict(item)
            for item in original.payload.get("estimated_food_versions", [])
        }
        if original.person_id != person_id:
            raise ValueError("proposal belongs to a different person")
        if original.status != "draft":
            raise ValueError("only draft proposals can be amended")
        if original.proposal_type not in {"diary_entries", "diary_entries_with_estimates"}:
            raise ValueError(f"proposal type cannot be amended as a meal: {original.proposal_type}")

        additions_text, removals = parse_text_meal_amendment(text)
        updated_entries = [
            DiaryEntry(
                id=self._next_id("diary_entry"),
                person_id=entry.person_id,
                logged_at=entry.logged_at,
                meal_type=entry.meal_type,
                food_version_id=entry.food_version_id,
                quantity_g=entry.quantity_g,
                source=entry.source,
                deleted_at=entry.deleted_at,
            )
            for entry in original.entries
        ]
        evidence = [dict(item) for item in original.evidence]
        warnings: list[str] = []

        for removal in removals:
            match_index = next(
                (
                    index
                    for index, entry in enumerate(updated_entries)
                    if self._proposal_entry_matches_phrase(
                        entry, removal.phrase, pending_versions=pending_versions
                    )
                ),
                None,
            )
            if match_index is None:
                warnings.append(f"Could not find an open proposal item matching '{removal.phrase}'.")
                continue
            entry = updated_entries[match_index]
            remaining_quantity = entry.quantity_g - removal.quantity_g
            if remaining_quantity <= 0:
                removed = updated_entries.pop(match_index)
                evidence.append(
                    {
                        "source_type": "text_meal_amendment",
                        "source_text": removal.source_text,
                        "action": "remove_entry",
                        "food_version_id": removed.food_version_id,
                        "quantity_g": removed.quantity_g,
                        "confidence": 0.85,
                    }
                )
            else:
                updated_entries[match_index] = DiaryEntry(
                    id=entry.id,
                    person_id=entry.person_id,
                    logged_at=entry.logged_at,
                    meal_type=entry.meal_type,
                    food_version_id=entry.food_version_id,
                    quantity_g=remaining_quantity,
                    source=entry.source,
                    deleted_at=entry.deleted_at,
                )
                evidence.append(
                    {
                        "source_type": "text_meal_amendment",
                        "source_text": removal.source_text,
                        "action": "subtract_quantity",
                        "food_version_id": entry.food_version_id,
                        "quantity_g": removal.quantity_g,
                        "remaining_quantity_g": remaining_quantity,
                        "confidence": 0.85,
                    }
                )

        added_items: list[ParsedMealItem] = []
        if additions_text:
            try:
                _, added_items = parse_text_meal_items(additions_text, default_logged_at=logged_at)
            except ValueError as exc:
                proposal = self._create_text_meal_clarification_proposal(
                    person_id=person_id,
                    text=text,
                    run=run,
                    logged_at=logged_at,
                    unresolved_items=(
                        ParsedMealItem(
                            phrase=text.casefold().strip(),
                            quantity_g=0,
                            source_text=text,
                            evidence={
                                "quantity_basis": "unparseable_amendment",
                                "parse_error": str(exc),
                            },
                        ),
                    ),
                    missing_fields=("parseable_food_item",),
                    summary="Need a clearer food and quantity before amending this meal.",
                )
                return proposal

        person = self._require_person(person_id)
        new_pending_versions: list[dict[str, object]] = []
        for item in added_items:
            if item.evidence.get("quantity_basis") != "grams":
                proposal = self._create_text_meal_clarification_proposal(
                    person_id=person_id,
                    text=text,
                    run=run,
                    logged_at=logged_at,
                    unresolved_items=(item,),
                    summary="Need grams before amending this meal.",
                )
                return proposal
            ambiguity = self._ambiguous_local_food_reference(
                household_id=person.household_id,
                person_id=person_id,
                phrase=item.phrase,
            )
            if ambiguity is not None:
                proposal = self._create_text_meal_clarification_proposal(
                    person_id=person_id,
                    text=text,
                    run=run,
                    logged_at=logged_at,
                    unresolved_items=(item,),
                    missing_fields=("food_version_id",),
                    summary="Need to know which food to use before amending this meal.",
                    candidate_overrides={item.phrase: ambiguity.candidates},
                )
                return proposal
            resolved = self._resolve_meal_item_food(
                person=person,
                run=run,
                phrase=item.phrase,
                settings=settings,
            )
            if resolved.pending_version is not None:
                new_pending_versions.append(resolved.pending_version)
            entry = DiaryEntry(
                id=self._next_id("diary_entry"),
                person_id=person_id,
                logged_at=logged_at,
                meal_type=original.entries[0].meal_type if original.entries else infer_meal_type(logged_at),
                food_version_id=resolved.food_version_id,
                quantity_g=item.quantity_g,
                source="agent_amendment_proposal",
            )
            updated_entries.append(entry)
            evidence.append(
                {
                    "source_type": "text_meal_amendment",
                    "source_text": item.source_text,
                    "action": "add_entry",
                    "phrase": item.phrase,
                    "food_id": resolved.version.food_id,
                    "food_name": resolved.food_name,
                    "food_version_id": resolved.food_version_id,
                    "quantity_g": item.quantity_g,
                    "resolution_reason": resolved.resolution_reason,
                    "confidence": resolved.confidence,
                    **item.evidence,
                }
            )

        if not updated_entries:
            raise ValueError("amendment would leave the proposal empty")

        referenced_version_ids = {entry.food_version_id for entry in updated_entries}
        payload = {
            **original.payload,
            "estimated_food_versions": [
                pending
                for pending in (
                    *original.payload.get("estimated_food_versions", []),
                    *new_pending_versions,
                )
                if str(pending["food_version_id"]) in referenced_version_ids
            ],
            "amended_from_proposal_id": original.id,
            "raw_amendment_text": text,
            "amendment_warnings": warnings,
        }
        totals = self._proposal_entries_total(tuple(updated_entries), payload=payload)
        proposal_type = "diary_entries_with_estimates" if payload.get("estimated_food_versions") else "diary_entries"
        amended = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=tuple(updated_entries),
                proposal_type=proposal_type,
                summary=f"{len(updated_entries)} diary entries drafted after meal amendment",
                payload=payload,
                totals=totals,
                evidence=tuple(evidence),
                source_agent_run_id=run.id,
            )
        )
        self.proposals.supersede(original.id, superseded_by_proposal_id=amended.id)
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=amended.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            fallback_reason=self._current_fallback_reason(run),
        )
        return amended

    def _proposal_entry_matches_phrase(
        self,
        entry: DiaryEntry,
        phrase: str,
        *,
        pending_versions: dict[str, dict[str, Any]] | None = None,
    ) -> bool:
        normalized = normalize_food_phrase(phrase)
        pending = (pending_versions or {}).get(entry.food_version_id)
        if pending is not None:
            names = {
                str(pending.get("food_name") or "").casefold(),
                str(pending.get("phrase") or "").casefold(),
                str(pending.get("version_label") or "").casefold(),
            }
            names.discard("")
        else:
            version = self.catalog.get_version(entry.food_version_id)
            food = self.catalog.foods[version.food_id]
            names = {food.name.casefold(), version.label.casefold()}
            names.update(
                alias.phrase.casefold()
                for alias in self.catalog.aliases.values()
                if alias.food_id == food.id
            )
        return any(normalized in candidate or candidate in normalized for candidate in names)

    def _ambiguous_local_food_reference(
        self,
        *,
        household_id: str,
        person_id: str,
        phrase: str,
    ) -> AmbiguousFoodReference | None:
        matching_food_ids = {
            alias.food_id
            for alias in self.catalog.aliases.values()
            if alias.household_id == household_id
            and alias.phrase.casefold().strip() == phrase.casefold().strip()
            and (alias.person_id is None or alias.person_id == person_id)
            and alias.food_id in self.catalog.foods
            and not self.catalog.foods[alias.food_id].archived
        }
        if len(matching_food_ids) <= 1:
            return None
        if self._resolve_phrase_by_recent_use(
            household_id=household_id,
            person_id=person_id,
            phrase=phrase,
        ) is not None:
            return None

        candidates: list[dict[str, object]] = []
        for food_id in sorted(matching_food_ids, key=lambda item: self.catalog.foods[item].name.casefold()):
            food = self.catalog.foods[food_id]
            if food.default_version_id is None:
                continue
            version = self.catalog.get_version(food.default_version_id)
            if version.archived:
                continue
            candidates.append(
                {
                    "food_id": food.id,
                    "food_version_id": version.id,
                    "food_name": food.name,
                    "brand": food.brand,
                    "version_label": version.label,
                    "nutrients_per_100g": nutrients_to_snapshot(version.nutrients_per_100g.rounded()),
                    "reason": "matching_alias_without_recent_use",
                }
            )
        if len(candidates) <= 1:
            return None
        return AmbiguousFoodReference(phrase=phrase, candidates=tuple(candidates))

    def _create_text_meal_clarification_proposal(
        self,
        *,
        person_id: str,
        text: str,
        run: AgentRun,
        logged_at: datetime,
        unresolved_items: tuple[ParsedMealItem, ...] | list[ParsedMealItem],
        missing_fields: tuple[str, ...] = ("quantity_g",),
        summary: str = "Need grams or serving size before logging this meal.",
        candidate_overrides: dict[str, tuple[dict[str, object], ...]] | None = None,
    ) -> CreateDiaryEntriesProposal:
        unresolved_payload = [
            {
                "source_text": item.source_text,
                "phrase": item.phrase,
                "unit": item.evidence.get("unit"),
                "quantity": item.evidence.get("unit_quantity", item.quantity_g),
                "quantity_basis": item.evidence.get("quantity_basis"),
                **(
                    {"candidates": list(candidate_overrides[item.phrase])}
                    if candidate_overrides is not None and item.phrase in candidate_overrides
                    else {}
                ),
            }
            for item in unresolved_items
        ]
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=(),
                proposal_type="diary_entries",
                status="needs_clarification",
                summary=summary,
                payload={
                    "logged_at_local": logged_at.isoformat(),
                    "raw_text": text,
                    "missing_fields": list(missing_fields),
                    "unresolved_items": unresolved_payload,
                },
                evidence=(
                    {
                        "source_type": "text_meal",
                        "raw_text": text,
                        "needs_clarification": True,
                        "unresolved_items": unresolved_payload,
                    },
                ),
                source_agent_run_id=run.id,
            )
        )
        self.agent_runs[run.id] = replace(
            run,
            status="needs_clarification",
            proposal_id=proposal.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            fallback_reason=self._current_fallback_reason(run),
        )
        return proposal

    def _create_repeated_meal_proposal(
        self,
        *,
        person_id: str,
        text: str,
        run: AgentRun,
        target_logged_at: datetime,
        source_day: date,
        meal_type: str,
    ) -> CreateDiaryEntriesProposal:
        source_entries = [
            entry
            for entry in self.diary.entries_for_day(person_id, source_day)
            if entry.meal_type == meal_type
        ]
        source_entries.sort(key=lambda entry: entry.logged_at)
        if not source_entries:
            raise ValueError(f"no {meal_type} entries found on {source_day.isoformat()}")

        entries: list[DiaryEntry] = []
        evidence: list[dict[str, object]] = []
        totals = Nutrients()
        for source_entry in source_entries:
            version = self.catalog.get_version(source_entry.food_version_id)
            copied = DiaryEntry(
                id=self._next_id("diary_entry"),
                person_id=person_id,
                logged_at=target_logged_at,
                meal_type=meal_type,
                food_version_id=source_entry.food_version_id,
                quantity_g=source_entry.quantity_g,
                source="agent_copy_proposal",
            )
            entries.append(copied)
            nutrients = version.nutrients_per_100g.scale(copied.quantity_g / 100)
            totals += nutrients
            food = self.catalog.foods[version.food_id]
            evidence.append(
                {
                    "source_type": "copied_diary_entry",
                    "source_text": text,
                    "source_day": source_day.isoformat(),
                    "source_meal_type": meal_type,
                    "source_entry_id": source_entry.id,
                    "food_id": food.id,
                    "food_name": food.name,
                    "food_version_id": version.id,
                    "quantity_g": copied.quantity_g,
                    "resolution_reason": "same_meal_previous_day",
                    "confidence": 1.0,
                }
            )

        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=tuple(entries),
                proposal_type="diary_entries",
                summary=f"{len(entries)} diary entries copied from {meal_type} on {source_day.isoformat()}",
                payload={
                    "raw_text": text,
                    "source_day": source_day.isoformat(),
                    "source_meal_type": meal_type,
                    "copy_mode": "same_meal_previous_day",
                },
                totals=totals,
                evidence=tuple(evidence),
                source_agent_run_id=run.id,
            )
        )
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=proposal.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            fallback_reason=self._current_fallback_reason(run),
        )
        return proposal

    def _chat_explain_day(
        self,
        *,
        person_id: str,
        message: str,
        run: AgentRun,
        day: date,
    ) -> AgentChatResponse:
        summary = self.day_summary(person_id, day)
        entries = [entry for entries in summary.meals.values() for entry in entries]
        if not entries:
            answer = (
                f"There is not enough diary data for {day.isoformat()} to explain that day. "
                "Log meals first, or ask about a date that has entries."
            )
            behavior_label = "answer_question"
            citations: tuple[dict[str, str], ...] = ()
        else:
            entries.sort(key=lambda entry: entry.nutrients.calories_kcal, reverse=True)
            top = entries[0]
            totals = summary.totals.rounded()
            answer = (
                f"{day.isoformat()} totals were {totals.calories_kcal} kcal, "
                f"{totals.protein_g} g protein, {totals.carbs_g} g carbs, and "
                f"{totals.fat_g} g fat. The biggest logged contributor was "
                f"{top.food_name}: {top.quantity_g} g for {top.nutrients.rounded().calories_kcal} kcal. "
                "This answer is based on deterministic diary records, not a model estimate."
            )
            behavior_label = "explain_day"
            citations = tuple(
                {"record_type": "diary_entry", "record_id": entry.id}
                for entry in entries
            )
        self._record_agent_tool_call(
            run=run,
            tool_name="summarize_day",
            input_summary=f"person_id={person_id}; day={day.isoformat()}",
            output_summary=(
                f"{len(entries)} entries; calories={summary.totals.rounded().calories_kcal}"
            ),
            source_record_ids=tuple(item["record_id"] for item in citations),
        )
        self.agent_runs[run.id] = replace(
            run,
            status="answered",
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=answer,
            behavior_label=behavior_label,
            citations=citations,
        )

    def _chat_explain_week(
        self,
        *,
        person_id: str,
        message: str,
        run: AgentRun,
        start: date,
        end: date,
    ) -> AgentChatResponse:
        summary = self.week_summary(person_id=person_id, start=start, end=end)
        current = start
        entries: list[DaySummaryEntry] = []
        while current <= end:
            day = self.day_summary(person_id, current)
            entries.extend(
                entry for meal_entries in day.meals.values() for entry in meal_entries
            )
            current += timedelta(days=1)
        trend = self.weight_trend(person_id=person_id, start=start, end=end)
        if not entries and not trend.entries:
            answer = (
                f"There is not enough diary or weight data for {start.isoformat()} to "
                f"{end.isoformat()} to explain that week. Log meals or weights first."
            )
            behavior_label = "answer_question"
            citations: tuple[dict[str, str], ...] = ()
        else:
            totals = summary.totals.rounded()
            averages = summary.averages.rounded()
            highest_day, highest_nutrients = max(
                summary.daily.items(),
                key=lambda item: item[1].calories_kcal,
            )
            logged_days = sum(1 for nutrients in summary.daily.values() if nutrients.calories_kcal > 0)
            weight_sentence = (
                f" Weight changed {summary.weight_delta_kg:g} kg."
                if summary.weight_delta_kg is not None
                else " Weight trend needs at least two readings in this range."
            )
            target_sentence = ""
            if summary.daily_targets:
                target_kcal = sum(target.calories_kcal for target in summary.daily_targets.values())
                target_protein = sum(target.protein_g for target in summary.daily_targets.values())
                target_sentence = (
                    f" Against stored targets, this is {totals.calories_kcal - target_kcal:g} "
                    f"kcal and {totals.protein_g - target_protein:g} g protein for the target-covered days."
                )
            repeated_sentence = ""
            food_days: dict[str, set[date]] = {}
            for entry in entries:
                food_days.setdefault(entry.food_name, set()).add(entry.logged_at.date())
            repeated = sorted(
                food_days.items(),
                key=lambda item: (-len(item[1]), item[0].casefold()),
            )
            if repeated and len(repeated[0][1]) >= 2:
                repeated_sentence = (
                    f" Repeated pattern: {repeated[0][0]} appeared on "
                    f"{len(repeated[0][1])} logged days."
                )
            answer = (
                f"{start.isoformat()} to {end.isoformat()} totals were "
                f"{totals.calories_kcal} kcal, {totals.protein_g} g protein, "
                f"{totals.carbs_g} g carbs, and {totals.fat_g} g fat. "
                f"That averages {averages.calories_kcal} kcal/day and "
                f"{averages.protein_g} g protein/day across the range. "
                f"The highest calorie day was {highest_day.isoformat()} with "
                f"{highest_nutrients.rounded().calories_kcal} kcal. "
                f"There were {logged_days} days with logged calories."
                f"{target_sentence}{weight_sentence}{repeated_sentence} "
                "This answer is based on deterministic app records, not a model estimate."
            )
            behavior_label = "explain_week"
            citations = tuple(
                [{"record_type": "diary_entry", "record_id": entry.id} for entry in entries]
                + [
                    {"record_type": "weight_entry", "record_id": entry.id}
                    for entry in trend.entries
                ]
            )
        self._record_agent_tool_call(
            run=run,
            tool_name="summarize_week",
            input_summary=(
                f"person_id={person_id}; range={start.isoformat()} to {end.isoformat()}"
            ),
            output_summary=(
                f"{len(entries)} diary entries; {len(trend.entries)} weight entries; "
                f"calories={summary.totals.rounded().calories_kcal}"
            ),
            source_record_ids=tuple(item["record_id"] for item in citations),
        )
        self.agent_runs[run.id] = replace(
            run,
            status="answered",
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=answer,
            behavior_label=behavior_label,
            citations=citations,
        )

    def _chat_explain_food_version_use(
        self,
        *,
        person_id: str,
        run: AgentRun,
        phrase: str,
    ) -> AgentChatResponse:
        person = self._require_person(person_id)
        normalized = phrase.casefold().strip()
        matches = [
            food
            for food in self.catalog.foods.values()
            if food.household_id == person.household_id
            and not food.archived
            and self._food_matches_query(food, normalized)
            and food.default_version_id is not None
        ]
        matches.sort(
            key=lambda food: (
                0 if normalized in food.name.casefold() else 1,
                food.name.casefold(),
                food.brand.casefold() if food.brand is not None else "",
            )
        )
        if not matches:
            self._record_agent_tool_call(
                run=run,
                tool_name="inspect_food_version_usage",
                input_summary=f"person_id={person_id}; phrase={phrase}",
                output_summary="no matching food",
                status="failed",
                error="no matching food in local library",
            )
            self.agent_runs[run.id] = replace(
                run,
                status="answered",
                tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            )
            return AgentChatResponse(
                run_id=run.id,
                person_id=person_id,
                message=(
                    f"I could not find a local food matching '{phrase}', so I cannot tell "
                    "whether a new label is being used yet."
                ),
                behavior_label="answer_question",
            )

        food = matches[0]
        versions = [
            version
            for version in self.catalog.versions.values()
            if version.food_id == food.id and not version.archived
        ]
        versions.sort(key=lambda version: version.created_at)
        current_version = self.catalog.get_version(str(food.default_version_id))
        entries: list[tuple[DiaryEntry, FoodVersion]] = []
        for entry in self.diary.entries.values():
            if entry.person_id != person_id or entry.deleted_at is not None:
                continue
            version = self.catalog.versions.get(entry.food_version_id)
            if version is None or version.food_id != food.id:
                continue
            entries.append((entry, version))
        entries.sort(key=lambda pair: pair[0].logged_at, reverse=True)
        latest_entry = entries[0] if entries else None
        older_logged_versions = [
            version
            for _, version in entries
            if version.id != current_version.id
        ]
        old_version_sentence = ""
        if older_logged_versions:
            seen_labels: list[str] = []
            for version in older_logged_versions:
                if version.label not in seen_labels:
                    seen_labels.append(version.label)
            old_version_sentence = (
                f" Earlier logs also used: {', '.join(seen_labels[:3])}."
            )
        usage_sentence = "I do not see any diary entries for it yet."
        if latest_entry is not None:
            latest_diary_entry, latest_version = latest_entry
            status = (
                "are using the current default"
                if latest_version.id == current_version.id
                else "are still using an older version"
            )
            usage_sentence = (
                f"Recent logs {status}: latest was {latest_diary_entry.logged_at.date().isoformat()} "
                f"with {latest_version.label} for {latest_diary_entry.quantity_g:g} g."
            )
        citations = tuple(
            [{"record_type": "food_version", "record_id": version.id} for version in versions]
            + [
                {"record_type": "diary_entry", "record_id": entry.id}
                for entry, _ in entries
            ]
        )
        self._record_agent_tool_call(
            run=run,
            tool_name="inspect_food_version_usage",
            input_summary=f"person_id={person_id}; phrase={phrase}",
            output_summary=(
                f"food={food.name}; versions={len(versions)}; entries={len(entries)}; "
                f"default={current_version.label}"
            ),
            source_record_ids=tuple(item["record_id"] for item in citations),
        )
        self.agent_runs[run.id] = replace(
            run,
            status="answered",
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=(
                f"{food.name}'s current default is {current_version.label}. "
                f"{usage_sentence}{old_version_sentence} "
                "This answer is based on local food versions and diary records."
            ),
            behavior_label="explain_food_version_use",
            citations=citations,
        )

    def _chat_analyze_micronutrients(
        self,
        *,
        person_id: str,
        message: str,
        today: date,
        run: AgentRun,
    ) -> AgentChatResponse:
        requested_week = parse_chat_week_reference(message, today=today)
        if requested_week is not None:
            start, end = requested_week
        else:
            end = today
            start = today - timedelta(days=13)
        current = start
        entries: list[DaySummaryEntry] = []
        totals = Nutrients()
        logged_days = 0
        while current <= end:
            summary = self.day_summary(person_id, current)
            day_entries = [
                entry for meal_entries in summary.meals.values() for entry in meal_entries
            ]
            if day_entries:
                logged_days += 1
            entries.extend(day_entries)
            totals += summary.totals
            current += timedelta(days=1)
        if not entries:
            answer = (
                f"There is not enough diary data from {start.isoformat()} to {end.isoformat()} "
                "to analyze micronutrient patterns. Log meals with labels or reference foods first."
            )
            behavior_label = "answer_question"
            citations: tuple[dict[str, str], ...] = ()
        else:
            rounded = totals.rounded()
            avg_fiber = round(rounded.fiber_g / logged_days, 2) if logged_days else 0
            avg_sodium = round(rounded.sodium_mg / logged_days, 2) if logged_days else 0
            source_foods = sorted({entry.food_name for entry in entries})
            food_hint = ", ".join(source_foods[:4])
            answer = (
                f"Micronutrient confidence is limited for {start.isoformat()} to "
                f"{end.isoformat()}: the app currently stores macros plus fiber and sodium, "
                "but vitamins and minerals are not stored in diary totals yet. "
                f"From {logged_days} logged day(s), tracked fiber totals {rounded.fiber_g} g "
                f"({avg_fiber} g/day) and tracked sodium totals {rounded.sodium_mg} mg "
                f"({avg_sodium} mg/day). "
                "A low or zero value can mean the label/reference did not include that field, "
                "not necessarily that intake was truly low. "
                f"Logged foods considered include {food_hint}. "
                "This is not a diagnosis or treatment recommendation. To improve confidence, "
                "attach labels, prefer food sources with micronutrient fields, and log vegetables, "
                "fruit, dairy, supplements, and fortified foods when relevant."
            )
            behavior_label = "micronutrient_analysis"
            citations = tuple(
                {"record_type": "diary_entry", "record_id": entry.id} for entry in entries
            )
        self._record_agent_tool_call(
            run=run,
            tool_name="analyze_micronutrients",
            input_summary=(
                f"person_id={person_id}; range={start.isoformat()} to {end.isoformat()}"
            ),
            output_summary=(
                f"{logged_days} logged days; {len(entries)} entries; "
                f"fiber={totals.rounded().fiber_g}; sodium={totals.rounded().sodium_mg}"
            ),
            source_record_ids=tuple(item["record_id"] for item in citations),
        )
        self.agent_runs[run.id] = replace(
            run,
            status="answered",
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=answer,
            behavior_label=behavior_label,
            citations=citations,
        )

    def _chat_draft_review_note(
        self,
        *,
        person_id: str,
        message: str,
        run: AgentRun,
        review_note: dict[str, object],
    ) -> AgentChatResponse:
        body = str(review_note["body"]).strip()
        starts_on = review_note.get("starts_on")
        ends_on = review_note.get("ends_on")
        starts_on_text = starts_on.isoformat() if isinstance(starts_on, date) else None
        ends_on_text = ends_on.isoformat() if isinstance(ends_on, date) else None
        title = "Review note"
        if starts_on_text and ends_on_text:
            title = f"Review note {starts_on_text} to {ends_on_text}"
        elif starts_on_text:
            title = f"Review note {starts_on_text}"
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=(),
                proposal_type="review_note",
                summary=title,
                payload={
                    "note_type": "review",
                    "title": title,
                    "body": body,
                    "starts_on": starts_on_text,
                    "ends_on": ends_on_text,
                    "source": "agent_chat",
                },
                evidence=(
                    {
                        "source_type": "agent_chat",
                        "raw_text": message,
                    },
                ),
                source_agent_run_id=run.id,
            )
        )
        self._record_agent_tool_call(
            run=run,
            tool_name="draft_review_note",
            input_summary=(
                f"range={starts_on_text or 'undated'}"
                f"{f' to {ends_on_text}' if ends_on_text else ''}; chars={len(body)}"
            ),
            output_summary=f"proposal_id={proposal.id}; title={title}",
            source_record_ids=(proposal.id,),
        )
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=proposal.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message="I drafted a review note. Confirm the proposal to save it.",
            behavior_label="draft_review_note",
            proposal_id=proposal.id,
        )

    def _chat_draft_profile_goal_update(
        self,
        *,
        person_id: str,
        message: str,
        run: AgentRun,
        parsed: dict[str, object],
    ) -> AgentChatResponse:
        proposal_type = str(parsed["proposal_type"])
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=(),
                proposal_type=proposal_type,  # type: ignore[arg-type]
                summary=str(parsed["summary"]),
                payload=dict(parsed["payload"]),
                evidence=(
                    {
                        "source_type": "agent_chat",
                        "raw_text": message,
                    },
                ),
                source_agent_run_id=run.id,
            )
        )
        self._record_agent_tool_call(
            run=run,
            tool_name=f"draft_{proposal_type}",
            input_summary=str(parsed["summary"]),
            output_summary=f"proposal_id={proposal.id}; type={proposal_type}",
            source_record_ids=(proposal.id,),
        )
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=proposal.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=f"I drafted a {proposal_type.replace('_', ' ')} proposal. Confirm it before anything changes.",
            behavior_label=f"draft_{proposal_type}",
            proposal_id=proposal.id,
        )

    def _chat_explain_profile_goal_capabilities(
        self,
        *,
        person_id: str,
        run: AgentRun,
    ) -> AgentChatResponse:
        self._record_agent_tool_call(
            run=run,
            tool_name="explain_profile_goal_capabilities",
            input_summary="profile/goal capability question",
            output_summary="profile and goal changes are proposal-gated",
        )
        self.agent_runs[run.id] = replace(
            run,
            status="answered",
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=(
                "Yes. I can help change profile fields and nutrition goals, but I will draft a "
                "proposal first instead of applying changes directly. For example, you can say "
                "'update my height to 181 cm' or 'change my goal to 1900 kcal and 160g protein "
                "starting 2026-07-10', then confirm the proposal if it looks right."
            ),
            behavior_label="answer_profile_goal_capabilities",
        )

    def _chat_draft_diary_correction(
        self,
        *,
        person_id: str,
        message: str,
        today: date,
        run: AgentRun,
        correction: dict[str, object],
    ) -> AgentChatResponse:
        correction_day = correction.get("day")
        day = correction_day if isinstance(correction_day, date) else today
        phrase = str(correction["phrase"]).casefold().strip()
        quantity_g = float(correction["quantity_g"])
        matches = [
            entry
            for entries in self.day_summary(person_id, day).meals.values()
            for entry in entries
            if phrase in entry.food_name.casefold()
            or phrase in (entry.brand or "").casefold()
        ]
        self._record_agent_tool_call(
            run=run,
            tool_name="find_diary_entries",
            input_summary=(
                f"person_id={person_id}; day={day.isoformat()}; phrase={phrase}"
            ),
            output_summary=f"{len(matches)} matches",
            status="completed" if matches else "failed",
            source_record_ids=tuple(entry.id for entry in matches),
            error=None if matches else "no matching diary entries",
        )
        if not matches:
            self.agent_runs[run.id] = replace(
                run,
                status="answered",
                tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
            )
            return AgentChatResponse(
                run_id=run.id,
                person_id=person_id,
                message=(
                    f"I could not find a diary entry matching '{phrase}' on {day.isoformat()}, "
                    "so I did not draft a correction."
                ),
                behavior_label="answer_question",
            )
        matches.sort(key=lambda entry: entry.logged_at)
        selected = matches[0]
        payload = {
            "entry_id": selected.id,
            "quantity_g": quantity_g,
            "previous_quantity_g": selected.quantity_g,
            "day": day.isoformat(),
            "food_name": selected.food_name,
        }
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=(),
                proposal_type="diary_entry_update",
                summary=f"Update {selected.food_name} on {day.isoformat()} to {quantity_g:g} g",
                payload=payload,
                evidence=(
                    {
                        "source_type": "agent_chat",
                        "raw_text": message,
                        "entry_id": selected.id,
                    },
                ),
                source_agent_run_id=run.id,
            )
        )
        self._record_agent_tool_call(
            run=run,
            tool_name="draft_diary_correction",
            input_summary=(
                f"entry_id={selected.id}; previous={selected.quantity_g:g}g; "
                f"new={quantity_g:g}g"
            ),
            output_summary=f"proposal_id={proposal.id}; food={selected.food_name}",
            source_record_ids=(selected.id, proposal.id),
        )
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=proposal.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=(
                f"I drafted a correction for {selected.food_name}: "
                f"{selected.quantity_g:g} g -> {quantity_g:g} g. Confirm the proposal to apply it."
            ),
            behavior_label="draft_diary_correction",
            citations=({"record_type": "diary_entry", "record_id": selected.id},),
            proposal_id=proposal.id,
        )

    def draft_diary_correction_proposal(
        self,
        *,
        person_id: str,
        entry_id: str | None = None,
        day: date | None = None,
        phrase: str | None = None,
        quantity_g: float,
        source_text: str = "structured diary correction",
        agent_settings: dict[str, Any] | None = None,
    ) -> CreateDiaryEntriesProposal:
        settings = self._agent_settings(agent_settings)
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=source_text,
            settings=settings,
            status="started",
            **self._run_metadata(settings),
        )
        self.agent_runs[run.id] = run
        selected: DaySummaryEntry | None = None
        if entry_id is not None:
            for entry in self.diary.entries.values():
                if entry.id == entry_id and entry.person_id == person_id and entry.deleted_at is None:
                    version = self.catalog.get_version(entry.food_version_id)
                    food = self.catalog.foods[version.food_id]
                    selected = DaySummaryEntry(
                        id=entry.id,
                        logged_at=entry.logged_at,
                        meal_type=entry.meal_type,
                        food_id=food.id,
                        food_name=food.name,
                        brand=food.brand,
                        food_version_id=version.id,
                        food_version_label=version.label,
                        quantity_g=entry.quantity_g,
                        nutrients=version.nutrients_per_100g.scale(entry.quantity_g / 100),
                        source=entry.source,
                        evidence_status=version.source,
                        confidence=version.confidence,
                    )
                    break
        if selected is None:
            if day is None or phrase is None:
                raise ValueError("entry_id or day+phrase is required for structured correction")
            normalized = phrase.casefold().strip()
            matches = [
                entry
                for entries in self.day_summary(person_id, day).meals.values()
                for entry in entries
                if normalized in entry.food_name.casefold()
                or normalized in (entry.brand or "").casefold()
            ]
            if not matches:
                raise ValueError(f"no diary entry matching '{phrase}' on {day.isoformat()}")
            matches.sort(key=lambda entry: entry.logged_at)
            selected = matches[0]
        payload = {
            "entry_id": selected.id,
            "quantity_g": float(quantity_g),
            "previous_quantity_g": selected.quantity_g,
            "day": selected.logged_at.date().isoformat(),
            "food_name": selected.food_name,
        }
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=(),
                proposal_type="diary_entry_update",
                summary=(
                    f"Update {selected.food_name} on {selected.logged_at.date().isoformat()} "
                    f"to {float(quantity_g):g} g"
                ),
                payload=payload,
                evidence=(
                    {
                        "source_type": "agent_structured_correction",
                        "raw_text": source_text,
                        "entry_id": selected.id,
                    },
                ),
                source_agent_run_id=run.id,
            )
        )
        self._record_agent_tool_call(
            run=run,
            tool_name="draft_diary_correction",
            input_summary=f"entry_id={selected.id}; new={float(quantity_g):g}g",
            output_summary=f"proposal_id={proposal.id}; food={selected.food_name}",
            source_record_ids=(selected.id, proposal.id),
        )
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=proposal.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
        )
        self._persist()
        return proposal

    def draft_review_note_proposal(
        self,
        *,
        person_id: str,
        body: str,
        title: str | None = None,
        starts_on: date | None = None,
        ends_on: date | None = None,
        source_text: str = "structured review note",
        agent_settings: dict[str, Any] | None = None,
    ) -> CreateDiaryEntriesProposal:
        settings = self._agent_settings(agent_settings)
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=source_text,
            settings=settings,
            status="started",
            **self._run_metadata(settings),
        )
        self.agent_runs[run.id] = run
        starts_on_text = starts_on.isoformat() if starts_on is not None else None
        ends_on_text = ends_on.isoformat() if ends_on is not None else None
        note_title = title or "Review note"
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=(),
                proposal_type="review_note",
                summary=note_title,
                payload={
                    "note_type": "review",
                    "title": note_title,
                    "body": body.strip(),
                    "starts_on": starts_on_text,
                    "ends_on": ends_on_text,
                    "source": "agent_chat",
                },
                evidence=({"source_type": "agent_structured_review", "raw_text": source_text},),
                source_agent_run_id=run.id,
            )
        )
        self._record_agent_tool_call(
            run=run,
            tool_name="draft_review_note",
            input_summary=f"chars={len(body.strip())}",
            output_summary=f"proposal_id={proposal.id}; title={note_title}",
            source_record_ids=(proposal.id,),
        )
        self.agent_runs[run.id] = replace(
            run,
            status="proposal_created",
            proposal_id=proposal.id,
            tool_loop_count=len(self.agent_tool_calls_for_run(run.id)),
        )
        self._persist()
        return proposal

    def propose_label_scan(
        self,
        *,
        household_id: str,
        person_id: str,
        table_text: str | None,
        set_as_default: bool = True,
        attachment_id: str | None = None,
        attachment_ids: Sequence[str] | None = None,
        barcode: str | None = None,
        logged_at_local: str | None = None,
        quantity_g: float | None = None,
        meal_type: str | None = None,
    ) -> CreateDiaryEntriesProposal:
        self._require_household(household_id)
        person = self._require_person(person_id)
        attachment_id_list = tuple(str(item) for item in (attachment_ids or ()) if str(item).strip())
        if attachment_id is not None and str(attachment_id) not in attachment_id_list:
            attachment_id_list = (str(attachment_id), *attachment_id_list)
        primary_attachment_id = attachment_id_list[0] if attachment_id_list else attachment_id
        attachments = tuple(self.get_attachment(item) for item in attachment_id_list)
        for attachment_item in attachments:
            if attachment_item.household_id != household_id:
                raise ValueError("attachment belongs to a different household")
        text_source = "user_text"
        ocr_results: list[dict[str, Any]] = []
        for attachment_item in attachments:
            if self.label_text_extractor is None:
                if not (table_text or "").strip():
                    raise ValueError("label scan with attachments requires label text or an OCR extractor")
                continue
            ocr_results.append(
                self.extract_label_text_from_attachment(attachment_id=attachment_item.id)
            )
        text_parts = []
        if (table_text or "").strip():
            text_parts.append(("user_text", (table_text or "").strip()))
        text_parts.extend(
            (
                f"ocr:{result['attachment_id']}",
                str(result["text"]).strip(),
            )
            for result in ocr_results
            if str(result["text"]).strip()
        )
        if not text_parts:
            raise ValueError("label scan requires label text or attachment OCR")
        normalized_text = "\n\n".join(
            f"[{source}]\n{text}" for source, text in text_parts
        ).strip()
        if ocr_results and table_text and table_text.strip():
            text_source = "user_text_and_ocr"
        elif ocr_results:
            text_source = "ocr"
        parsed = parse_nutrition_label_text(normalized_text)
        scanned_barcode = barcode.strip() if barcode is not None else None
        if scanned_barcode == "":
            scanned_barcode = None
        final_barcode = scanned_barcode or parsed.barcode
        entries: tuple[DiaryEntry, ...] = ()
        totals = Nutrients()
        pending_food_versions: list[dict[str, Any]] = []
        pending_food_id: str | None = None
        pending_version_id: str | None = None
        if logged_at_local is not None or quantity_g is not None:
            if logged_at_local is None or quantity_g is None:
                raise ValueError("logged_at_local and quantity_g must be provided together")
            if quantity_g <= 0:
                raise ValueError("quantity_g must be positive")
            logged_at = self._parse_person_datetime(logged_at_local, person)
            pending_food_id = self._next_id("food")
            pending_version_id = self._next_id("food_version")
            entry = DiaryEntry(
                id=self._next_id("diary_entry"),
                person_id=person_id,
                logged_at=logged_at,
                meal_type=meal_type or infer_meal_type(logged_at),
                food_version_id=pending_version_id,
                quantity_g=quantity_g,
                source="label_scan",
            )
            entries = (entry,)
            totals = parsed.nutrients_per_100g.scale(quantity_g / 100)
            pending_food_versions.append(
                {
                    "food_id": pending_food_id,
                    "food_version_id": pending_version_id,
                    "household_id": household_id,
                    "food_name": parsed.food_name,
                    "brand": parsed.brand,
                    "version_label": "label scan",
                    "nutrients_per_100g": nutrients_to_snapshot(parsed.nutrients_per_100g.rounded()),
                    "source": "label_scan",
                    "confidence": 1.0,
                }
            )
        payload = {
            "household_id": household_id,
            "food_name": parsed.food_name,
            "brand": parsed.brand,
            "version_label": "label scan",
            "food_id": pending_food_id,
            "food_version_id": pending_version_id,
            "nutrients_per_100g": nutrients_to_snapshot(parsed.nutrients_per_100g.rounded()),
            "serving_size_g": parsed.serving_size_g,
            "barcode": final_barcode,
            "barcode_source": "separate_scan" if scanned_barcode is not None else "label_text",
            "set_as_default": set_as_default,
            "source": "label_scan",
            "attachment_id": primary_attachment_id,
            "attachment_ids": list(attachment_id_list),
            "text_source": text_source,
            "ocr_text": "\n\n".join(str(result["text"]) for result in ocr_results) or None,
            "ocr_source": ",".join(str(result["source"]) for result in ocr_results) or None,
            "ocr_confidence": (
                min(float(result["confidence"]) for result in ocr_results)
                if ocr_results
                else None
            ),
            "ocr_warnings": [
                warning
                for result in ocr_results
                for warning in list(result.get("warnings", []))
            ],
            "ocr_results": ocr_results,
            "logged_at_local": logged_at_local,
            "quantity_g": quantity_g,
            "meal_type": entries[0].meal_type if entries else None,
            "estimated_food_versions": pending_food_versions,
        }
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=entries,
                proposal_type="food_version_from_label",
                summary=(
                    f"Food version and diary entry drafted from label: {parsed.food_name}"
                    if entries
                    else f"Food version drafted from label: {parsed.food_name}"
                ),
                payload=payload,
                totals=totals,
                evidence=(
                    {
                        "source_type": "nutrition_label_text",
                        "raw_text": normalized_text,
                        "warnings": list(parsed.warnings),
                        "attachment_id": primary_attachment_id,
                        "attachment_ids": list(attachment_id_list),
                        "text_source": text_source,
                        "ocr_results": ocr_results,
                        "ocr_source": ",".join(str(result["source"]) for result in ocr_results) or None,
                        "ocr_confidence": (
                            min(float(result["confidence"]) for result in ocr_results)
                            if ocr_results
                            else None
                        ),
                        "ocr_warnings": [
                            warning
                            for result in ocr_results
                            for warning in list(result.get("warnings", []))
                        ],
                        "logged_diary_entry": bool(entries),
                    },
                ),
            )
        )
        self._persist()
        return proposal

    def repeat_meal(
        self,
        *,
        person_id: str,
        source_day: date,
        meal_type: str,
        logged_at_local: str,
    ) -> CreateDiaryEntriesProposal:
        person = self._require_person(person_id)
        target_logged_at = self._parse_person_datetime(logged_at_local, person)
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=f"repeat {meal_type} from {source_day.isoformat()}",
            settings=self._agent_settings(None),
            status="started",
            **self._run_metadata(self._agent_settings(None)),
        )
        self.agent_runs[run.id] = run
        proposal = self._create_repeated_meal_proposal(
            person_id=person_id,
            text=run.input_text,
            run=run,
            target_logged_at=target_logged_at,
            source_day=source_day,
            meal_type=normalize_meal_type(meal_type),
        )
        self._persist()
        return proposal

    def propose_recipe(
        self,
        *,
        household_id: str,
        person_id: str,
        recipe_text: str,
        logged_at_local: str | None = None,
        quantity_g: float | None = None,
        meal_type: str | None = None,
    ) -> CreateDiaryEntriesProposal:
        self._require_household(household_id)
        person = self._require_person(person_id)
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
            food = self.catalog.foods[version.food_id]
            nutrients = version.nutrients_per_100g.scale(ingredient.quantity_g / 100)
            total += nutrients
            ingredient_payloads.append(
                {
                    "source_text": ingredient.source_text,
                    "phrase": ingredient.phrase,
                    "quantity_g": ingredient.quantity_g,
                    "food_id": food.id,
                    "food_name": food.name,
                    "food_version_id": version.id,
                    "resolution_reason": resolution.reason,
                    "confidence": resolution.confidence,
                    "nutrients": nutrients_to_snapshot(nutrients.rounded()),
                }
            )
        if parsed.yield_g is None:
            payload = {
                "household_id": household_id,
                "food_name": parsed.name,
                "brand": None,
                "version_label": "recipe draft",
                "yield_g": None,
                "nutrients_total": nutrients_to_snapshot(total.rounded()),
                "ingredients": ingredient_payloads,
                "source": "recipe",
                "precise_logging_enabled": False,
                "missing_fields": ["yield_g"],
            }
            proposal = self.proposals.create(
                CreateDiaryEntriesProposal(
                    id=self._next_id("proposal"),
                    person_id=person_id,
                    entries=(),
                    proposal_type="recipe_draft",
                    summary=f"Recipe draft saved without yield: {parsed.name}",
                    payload=payload,
                    evidence=(
                        {
                            "source_type": "recipe_text",
                            "raw_text": recipe_text,
                            "ingredient_count": len(parsed.ingredients),
                            "missing_fields": ["yield_g"],
                        },
                    ),
                )
            )
            self._persist()
            return proposal
        nutrients_per_100g = total.scale(100 / parsed.yield_g).rounded()
        entries: tuple[DiaryEntry, ...] = ()
        proposal_totals = Nutrients()
        pending_food_versions: list[dict[str, Any]] = []
        pending_food_id: str | None = None
        pending_version_id: str | None = None
        if logged_at_local is not None or quantity_g is not None:
            if logged_at_local is None or quantity_g is None:
                raise ValueError("logged_at_local and quantity_g must be provided together")
            if quantity_g <= 0:
                raise ValueError("quantity_g must be positive")
            logged_at = self._parse_person_datetime(logged_at_local, person)
            pending_food_id = self._next_id("food")
            pending_version_id = self._next_id("food_version")
            entry = DiaryEntry(
                id=self._next_id("diary_entry"),
                person_id=person_id,
                logged_at=logged_at,
                meal_type=meal_type or infer_meal_type(logged_at),
                food_version_id=pending_version_id,
                quantity_g=quantity_g,
                source="recipe",
            )
            entries = (entry,)
            proposal_totals = nutrients_per_100g.scale(quantity_g / 100)
            pending_food_versions.append(
                {
                    "food_id": pending_food_id,
                    "food_version_id": pending_version_id,
                    "household_id": household_id,
                    "food_name": parsed.name,
                    "brand": None,
                    "version_label": "recipe batch",
                    "nutrients_per_100g": nutrients_to_snapshot(nutrients_per_100g),
                    "source": "recipe",
                    "confidence": 1.0,
                }
            )
        payload = {
            "household_id": household_id,
            "food_name": parsed.name,
            "brand": None,
            "version_label": "recipe batch",
            "food_id": pending_food_id,
            "food_version_id": pending_version_id,
            "yield_g": parsed.yield_g,
            "nutrients_per_100g": nutrients_to_snapshot(nutrients_per_100g),
            "ingredients": ingredient_payloads,
            "source": "recipe",
            "logged_at_local": logged_at_local,
            "quantity_g": quantity_g,
            "meal_type": entries[0].meal_type if entries else None,
            "estimated_food_versions": pending_food_versions,
        }
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=person_id,
                entries=entries,
                proposal_type="recipe_food_version",
                summary=(
                    f"Recipe food version and diary entry drafted: {parsed.name}"
                    if entries
                    else f"Recipe food version drafted: {parsed.name}"
                ),
                payload=payload,
                totals=proposal_totals,
                evidence=(
                    {
                        "source_type": "recipe_text",
                        "raw_text": recipe_text,
                        "ingredient_count": len(parsed.ingredients),
                        "logged_diary_entry": bool(entries),
                    },
                ),
            )
        )
        self._persist()
        return proposal

    def get_proposal(self, proposal_id: str) -> CreateDiaryEntriesProposal:
        return self.proposals.proposals[proposal_id]

    def list_proposals(
        self,
        *,
        person_id: str | None = None,
        status: str | None = None,
    ) -> tuple[CreateDiaryEntriesProposal, ...]:
        proposals = list(self.proposals.proposals.values())
        if person_id is not None:
            proposals = [proposal for proposal in proposals if proposal.person_id == person_id]
        if status is not None:
            proposals = [proposal for proposal in proposals if proposal.status == status]
        proposals.sort(key=lambda proposal: (proposal.created_at, proposal.id), reverse=True)
        return tuple(proposals)

    def get_agent_run(self, agent_run_id: str) -> AgentRun:
        return self.agent_runs[agent_run_id]

    def agent_tool_calls_for_run(self, agent_run_id: str) -> tuple[AgentToolCall, ...]:
        calls = [
            call
            for call in self.agent_tool_calls.values()
            if call.agent_run_id == agent_run_id
        ]
        calls.sort(key=lambda call: (call.started_at, call.id))
        return tuple(calls)

    def chat_turns_for_person(self, person_id: str) -> tuple[AgentChatTurn, ...]:
        self._require_person(person_id)
        turns = [
            turn
            for turn in self.chat_turns.values()
            if turn.person_id == person_id
        ]
        turns.sort(key=lambda turn: (turn.created_at, turn.id))
        return tuple(turns)

    def chat_turn_for_agent_run(self, agent_run_id: str) -> AgentChatTurn:
        for turn in self.chat_turns.values():
            if turn.agent_run_id == agent_run_id:
                return turn
        raise KeyError(agent_run_id)

    def onboarding_turns_for_session(self, session_id: str) -> tuple[OnboardingTurn, ...]:
        turns = [
            turn
            for turn in self.onboarding_turns.values()
            if turn.session_id == session_id
        ]
        turns.sort(key=lambda turn: (turn.created_at, turn.id))
        return tuple(turns)

    def onboarding_chat(
        self,
        *,
        session_id: str,
        message: str,
        household_id: str | None = None,
        agent_settings: dict[str, Any] | None = None,
    ) -> OnboardingTurn:
        settings = self._agent_settings(agent_settings)
        self._ensure_model_available(settings, replay_message=message)
        if household_id is not None:
            self._require_household(household_id)
        assistant_message = (
            "Vou configurar o diário por conversa. Diga seu nome, fuso horário, "
            "objetivo e qualquer meta inicial que você já queira propor."
        )
        turn = OnboardingTurn(
            id=self._next_id("onboarding_turn"),
            session_id=session_id,
            household_id=household_id,
            user_message=message,
            assistant_message=assistant_message,
        )
        self.onboarding_turns[turn.id] = turn
        self._persist()
        return turn

    def draft_onboarding_proposal(
        self,
        *,
        session_id: str,
        household_name: str | None,
        household_id: str | None,
        person: dict[str, Any],
        targets: dict[str, Any],
        notes: str | None = None,
        source_text: str = "",
    ) -> CreateDiaryEntriesProposal:
        if household_id is not None:
            household = self._require_household(household_id)
            resolved_household_id = household.id
            resolved_household_name = household.name
        else:
            resolved_household_id = None
            resolved_household_name = str(household_name or "Casa").strip() or "Casa"
        person_name = str(person.get("name") or "").strip()
        if not person_name:
            raise ValueError("person name is required")
        timezone_name = str(person.get("timezone") or "America/Sao_Paulo").strip()
        ZoneInfo(timezone_name)
        target_nutrients = nutrients_from_mapping(targets)
        if target_nutrients.calories_kcal <= 0:
            raise ValueError("daily calorie target must be positive")
        payload = {
            "session_id": session_id,
            "household_id": resolved_household_id,
            "household_name": resolved_household_name,
            "person": {
                "name": person_name,
                "timezone": timezone_name,
                "birth_date": person.get("birth_date"),
                "sex": person.get("sex"),
                "height_cm": person.get("height_cm"),
                "activity_level": person.get("activity_level"),
            },
            "targets": nutrients_to_snapshot(target_nutrients),
            "notes": notes,
        }
        proposal = self.proposals.create(
            CreateDiaryEntriesProposal(
                id=self._next_id("proposal"),
                person_id=f"onboarding:{session_id}",
                entries=(),
                proposal_type="profile_setup",
                summary=f"Profile setup drafted for {person_name}",
                payload=payload,
                evidence=(
                    {
                        "source_type": "onboarding_chat",
                        "session_id": session_id,
                        "raw_text": source_text,
                    },
                ),
            )
        )
        self._persist()
        return proposal

    def enqueue_job(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        client_request_id: str | None = None,
    ) -> BackgroundJob:
        if job_type != "agent_chat":
            raise ValueError(f"unsupported job type: {job_type}")
        if client_request_id:
            for existing in self.jobs.values():
                if existing.client_request_id == client_request_id:
                    return existing
        job = BackgroundJob(
            id=self._next_id("job"),
            job_type=job_type,
            status="pending",
            payload=dict(payload),
            client_request_id=client_request_id,
        )
        self.jobs[job.id] = job
        self._persist()
        return job

    def get_job(self, job_id: str) -> BackgroundJob:
        return self.jobs[job_id]

    def list_jobs(
        self,
        *,
        person_id: str | None = None,
        status: str | None = None,
    ) -> tuple[BackgroundJob, ...]:
        jobs = list(self.jobs.values())
        if person_id is not None:
            jobs = [job for job in jobs if job.payload.get("person_id") == person_id]
        if status is not None:
            jobs = [job for job in jobs if job.status == status]
        jobs.sort(key=lambda job: (job.created_at, job.id))
        return tuple(jobs)

    def process_next_job(self) -> BackgroundJob | None:
        pending = self.list_jobs(status="pending")
        if not pending:
            return None
        return self.process_job(pending[0].id)

    def process_job(self, job_id: str) -> BackgroundJob:
        job = self.jobs[job_id]
        if job.status != "pending":
            return job
        now = datetime.now(timezone.utc)
        running = BackgroundJob(
            id=job.id,
            job_type=job.job_type,
            status="running",
            payload=job.payload,
            client_request_id=job.client_request_id,
            result=job.result,
            last_error=None,
            attempts=job.attempts + 1,
            created_at=job.created_at,
            updated_at=now,
            started_at=now,
            completed_at=None,
        )
        self.jobs[job.id] = running
        self._persist()
        try:
            result = self._execute_job(running)
        except Exception as exc:
            failed_at = datetime.now(timezone.utc)
            failed = BackgroundJob(
                id=running.id,
                job_type=running.job_type,
                status="failed",
                payload=running.payload,
                client_request_id=running.client_request_id,
                result=running.result,
                last_error=str(exc),
                attempts=running.attempts,
                created_at=running.created_at,
                updated_at=failed_at,
                started_at=running.started_at,
                completed_at=failed_at,
            )
            self.jobs[job.id] = failed
            self._persist()
            return failed
        completed_at = datetime.now(timezone.utc)
        succeeded = BackgroundJob(
            id=running.id,
            job_type=running.job_type,
            status="succeeded",
            payload=running.payload,
            client_request_id=running.client_request_id,
            result=result,
            last_error=None,
            attempts=running.attempts,
            created_at=running.created_at,
            updated_at=completed_at,
            started_at=running.started_at,
            completed_at=completed_at,
        )
        self.jobs[job.id] = succeeded
        self._persist()
        return succeeded

    def _execute_job(self, job: BackgroundJob) -> dict[str, Any]:
        payload = dict(job.payload)
        if job.job_type == "agent_chat":
            response = self.chat(
                person_id=str(payload["person_id"]),
                message=str(payload["message"]),
                today=date.fromisoformat(str(payload["today"])) if payload.get("today") else date.today(),
                agent_settings=payload.get("agent_settings"),
                attachment_ids=payload.get("attachment_ids"),
                intent=str(payload["intent"]) if payload.get("intent") is not None else None,
            )
            turn = self.chat_turn_for_agent_run(response.run_id)
            return {
                "run_id": response.run_id,
                "chat_turn_id": turn.id,
                "behavior_label": response.behavior_label,
                "proposal_id": response.proposal_id,
            }
        raise ValueError(f"unsupported job type: {job.job_type}")

    def confirm_proposal(self, proposal_id: str) -> CreateDiaryEntriesProposal:
        proposal = self.proposals.proposals[proposal_id]
        if proposal.status == "applied":
            raise ValueError("proposal is already applied")
        if proposal.status == "superseded":
            raise ValueError("proposal is superseded")
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        if proposal.status == "needs_clarification":
            raise ValueError("proposal needs clarification before it can be applied")
        if proposal.proposal_type in {"food_version_from_label", "food_version_from_lookup"}:
            applied = self._apply_food_version_proposal(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        if proposal.proposal_type == "recipe_food_version":
            applied = self._apply_recipe_food_version_proposal(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        if proposal.proposal_type == "recipe_draft":
            applied = self._apply_recipe_draft_proposal(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        if proposal.proposal_type == "diary_entry_update":
            applied = self._apply_diary_entry_update_proposal(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        if proposal.proposal_type == "diary_entries_with_estimates":
            applied = self._apply_diary_entries_with_estimates(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        if proposal.proposal_type == "review_note":
            applied = self._apply_review_note_proposal(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        if proposal.proposal_type == "profile_update":
            applied = self._apply_profile_update_proposal(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        if proposal.proposal_type == "goal_profile":
            applied = self._apply_goal_profile_proposal(proposal)
            self.proposals.proposals[proposal_id] = applied
            self._persist()
            return applied
        if proposal.proposal_type == "profile_setup":
            applied = self._apply_profile_setup_proposal(proposal)
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

    def _record_agent_tool_call(
        self,
        *,
        run: AgentRun,
        tool_name: str,
        input_summary: str,
        output_summary: str,
        status: str = "completed",
        source_record_ids: tuple[str, ...] = (),
        error: str | None = None,
    ) -> AgentToolCall:
        now = datetime.now(timezone.utc)
        call = AgentToolCall(
            id=self._next_id("agent_tool_call"),
            agent_run_id=run.id,
            person_id=run.person_id,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            source_record_ids=source_record_ids,
            error=error,
            started_at=now,
            completed_at=now,
        )
        self.agent_tool_calls[call.id] = call
        return call

    def _record_agent_chat_turn(
        self,
        *,
        run: AgentRun,
        user_message: str,
        response: AgentChatResponse,
    ) -> AgentChatTurn:
        turn = AgentChatTurn(
            id=self._next_id("agent_chat_turn"),
            person_id=run.person_id,
            agent_run_id=run.id,
            user_message=user_message,
            assistant_message=response.message,
            behavior_label=response.behavior_label,
            citations=response.citations,
            proposal_id=response.proposal_id,
            created_at=datetime.now(timezone.utc),
        )
        self.chat_turns[turn.id] = turn
        return turn

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
        household_id = str(payload["household_id"])
        food_name = str(payload["food_name"])
        brand = payload.get("brand") if payload.get("brand") is None else str(payload["brand"])
        existing_food = self._find_food_by_name(
            household_id=household_id,
            name=food_name,
            brand=brand,
        )
        requested_food_id = (
            existing_food.id
            if existing_food is not None
            else str(payload["food_id"])
            if payload.get("food_id") is not None
            else None
        )
        food, version = self._create_food_with_version(
            household_id=household_id,
            name=food_name,
            brand=brand,
            version_label=str(payload["version_label"]),
            nutrients_per_100g=nutrients_from_snapshot(
                dict(payload["nutrients_per_100g"])
            ),
            source=str(payload.get("source", "label_scan")),
            aliases=[food_name.casefold()],
            barcode=payload.get("barcode") if payload.get("barcode") is None else str(payload["barcode"]),
            serving_size_g=float(payload["serving_size_g"]),
            confidence=float(payload.get("confidence", 1.0)),
            food_id=requested_food_id,
            version_id=str(payload["food_version_id"]) if payload.get("food_version_id") is not None else None,
        )
        applied_ids = [food.id, version.id]
        barcode = payload.get("barcode")
        if barcode is not None:
            association = self.catalog.resolve_barcode(str(barcode))
            if association is not None:
                applied_ids.append(association.id)
        attachment_ids = tuple(
            str(item) for item in (payload.get("attachment_ids") or []) if str(item).strip()
        )
        attachment_id = payload.get("attachment_id")
        if attachment_id is not None and str(attachment_id) not in attachment_ids:
            attachment_ids = (str(attachment_id), *attachment_ids)
        for attachment_id in attachment_ids:
            self._link_attachment(
                attachment_id,
                linked_record_type="food_version",
                linked_record_id=version.id,
            )
            applied_ids.append(attachment_id)
        for entry in proposal.entries:
            if entry.food_version_id != version.id:
                entry = DiaryEntry(
                    id=entry.id,
                    person_id=entry.person_id,
                    logged_at=entry.logged_at,
                    meal_type=entry.meal_type,
                    food_version_id=version.id,
                    quantity_g=entry.quantity_g,
                    source=entry.source,
                    deleted_at=entry.deleted_at,
                )
            self.diary.add_entry(entry)
            applied_ids.append(entry.id)
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
            confirmed_at=proposal.confirmed_at or datetime.now(timezone.utc),
            rejected_at=proposal.rejected_at,
        )

    def _apply_recipe_food_version_proposal(
        self,
        proposal: CreateDiaryEntriesProposal,
    ) -> CreateDiaryEntriesProposal:
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        payload = proposal.payload
        household_id = str(payload["household_id"])
        food_name = str(payload["food_name"])
        brand = payload.get("brand") if payload.get("brand") is None else str(payload["brand"])
        existing_food = self._find_food_by_name(
            household_id=household_id,
            name=food_name,
            brand=brand,
        )
        food, version = self._create_food_with_version(
            household_id=household_id,
            name=food_name,
            brand=brand,
            version_label=str(payload["version_label"]),
            nutrients_per_100g=nutrients_from_snapshot(
                dict(payload["nutrients_per_100g"])
            ),
            source=str(payload.get("source", "recipe")),
            aliases=[food_name.casefold()],
            barcode=None,
            serving_size_g=None,
            confidence=float(payload.get("confidence", 1.0)),
            food_id=(
                existing_food.id
                if existing_food is not None
                else str(payload["food_id"]) if payload.get("food_id") is not None else None
            ),
            version_id=str(payload["food_version_id"]) if payload.get("food_version_id") is not None else None,
        )
        applied_ids = [food.id, version.id]
        self.recipe_versions[version.id] = recipe_version_from_proposal_payload(
            id=self._next_id("recipe_version"),
            household_id=household_id,
            food_id=food.id,
            food_version_id=version.id,
            payload=payload,
            source_proposal_id=proposal.id,
        )
        for entry in proposal.entries:
            if entry.food_version_id != version.id:
                entry = DiaryEntry(
                    id=entry.id,
                    person_id=entry.person_id,
                    logged_at=entry.logged_at,
                    meal_type=entry.meal_type,
                    food_version_id=version.id,
                    quantity_g=entry.quantity_g,
                    source=entry.source,
                    deleted_at=entry.deleted_at,
                )
            self.diary.add_entry(entry)
            applied_ids.append(entry.id)
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
            confirmed_at=proposal.confirmed_at or datetime.now(timezone.utc),
            rejected_at=proposal.rejected_at,
        )

    def _apply_recipe_draft_proposal(
        self,
        proposal: CreateDiaryEntriesProposal,
    ) -> CreateDiaryEntriesProposal:
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
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
            applied_record_ids=(),
            created_at=proposal.created_at,
            confirmed_at=proposal.confirmed_at or datetime.now(timezone.utc),
            rejected_at=proposal.rejected_at,
        )

    def _apply_diary_entry_update_proposal(
        self,
        proposal: CreateDiaryEntriesProposal,
    ) -> CreateDiaryEntriesProposal:
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        payload = proposal.payload
        updated = self.diary.update_entry(
            str(payload["entry_id"]),
            quantity_g=float(payload["quantity_g"]) if payload.get("quantity_g") is not None else None,
            meal_type=str(payload["meal_type"]) if payload.get("meal_type") is not None else None,
            food_version_id=str(payload["food_version_id"])
            if payload.get("food_version_id") is not None
            else None,
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
            applied_record_ids=(updated.id,),
            created_at=proposal.created_at,
            confirmed_at=proposal.confirmed_at or datetime.now(timezone.utc),
            rejected_at=proposal.rejected_at,
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
                brand=estimate_payload.get("brand")
                if estimate_payload.get("brand") is None
                else str(estimate_payload["brand"]),
                version_label=str(estimate_payload["version_label"]),
                nutrients_per_100g=nutrients_from_snapshot(
                    dict(estimate_payload["nutrients_per_100g"])
                ),
                source=str(estimate_payload["source"]),
                aliases=[str(estimate_payload["phrase"])],
                barcode=estimate_payload.get("barcode")
                if estimate_payload.get("barcode") is None
                else str(estimate_payload["barcode"]),
                serving_size_g=float(estimate_payload["serving_size_g"])
                if estimate_payload.get("serving_size_g") is not None
                else None,
                confidence=float(estimate_payload.get("confidence", 1.0)),
                food_id=str(estimate_payload["food_id"]),
                version_id=str(estimate_payload["food_version_id"]),
            )
            applied_record_ids.extend([food.id, version.id])
            barcode = estimate_payload.get("barcode")
            if barcode is not None:
                association = self.catalog.resolve_barcode(str(barcode))
                if association is not None:
                    applied_record_ids.append(association.id)
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
            confirmed_at=proposal.confirmed_at or datetime.now(timezone.utc),
            rejected_at=proposal.rejected_at,
        )

    def _apply_review_note_proposal(
        self,
        proposal: CreateDiaryEntriesProposal,
    ) -> CreateDiaryEntriesProposal:
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        payload = proposal.payload
        starts_on = date.fromisoformat(str(payload["starts_on"])) if payload.get("starts_on") else None
        ends_on = date.fromisoformat(str(payload["ends_on"])) if payload.get("ends_on") else None
        note = ReviewNote(
            id=self._next_id("review_note"),
            person_id=proposal.person_id,
            note_type=str(payload.get("note_type", "review")),
            title=str(payload.get("title", "Review note")),
            body=str(payload["body"]),
            starts_on=starts_on,
            ends_on=ends_on,
            source=str(payload.get("source", "agent_chat")),
            source_agent_run_id=proposal.source_agent_run_id,
            source_proposal_id=proposal.id,
            source_record_refs=(
                {"record_type": "proposal", "record_id": proposal.id},
            ),
        )
        self.review_notes[note.id] = note
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
            applied_record_ids=(note.id,),
            created_at=proposal.created_at,
            confirmed_at=proposal.confirmed_at or datetime.now(timezone.utc),
            rejected_at=proposal.rejected_at,
        )

    def _apply_profile_update_proposal(
        self,
        proposal: CreateDiaryEntriesProposal,
    ) -> CreateDiaryEntriesProposal:
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        payload = proposal.payload
        birth_date = date.fromisoformat(str(payload["birth_date"])) if payload.get("birth_date") else None
        person = self.update_person(
            person_id=proposal.person_id,
            name=str(payload["name"]) if payload.get("name") else None,
            timezone=str(payload["timezone"]) if payload.get("timezone") else None,
            birth_date=birth_date,
            sex=str(payload["sex"]) if payload.get("sex") else None,
            height_cm=float(payload["height_cm"]) if payload.get("height_cm") is not None else None,
            activity_level=str(payload["activity_level"]) if payload.get("activity_level") else None,
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
            applied_record_ids=(person.id,),
            created_at=proposal.created_at,
            confirmed_at=proposal.confirmed_at or datetime.now(timezone.utc),
            rejected_at=proposal.rejected_at,
        )

    def _apply_goal_profile_proposal(
        self,
        proposal: CreateDiaryEntriesProposal,
    ) -> CreateDiaryEntriesProposal:
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        payload = proposal.payload
        targets = nutrients_from_mapping(payload["targets"])
        starts_on = date.fromisoformat(str(payload["starts_on"]))
        goal = self.create_goal_profile(
            person_id=proposal.person_id,
            starts_on=starts_on,
            targets=targets,
            notes=str(payload["notes"]) if payload.get("notes") else "Agent-drafted target update",
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
            applied_record_ids=(goal.id,),
            created_at=proposal.created_at,
            confirmed_at=proposal.confirmed_at or datetime.now(timezone.utc),
            rejected_at=proposal.rejected_at,
        )

    def _apply_profile_setup_proposal(
        self,
        proposal: CreateDiaryEntriesProposal,
    ) -> CreateDiaryEntriesProposal:
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        payload = proposal.payload
        person_payload = dict(payload["person"])
        household_id = payload.get("household_id")
        if household_id:
            household = self._require_household(str(household_id))
        else:
            household = self.create_household(name=str(payload["household_name"]))
        birth_date = (
            date.fromisoformat(str(person_payload["birth_date"]))
            if person_payload.get("birth_date")
            else None
        )
        person = self.create_person(
            household_id=household.id,
            name=str(person_payload["name"]),
            timezone=str(person_payload["timezone"]),
            birth_date=birth_date,
            sex=str(person_payload["sex"]) if person_payload.get("sex") else None,
            height_cm=float(person_payload["height_cm"]) if person_payload.get("height_cm") is not None else None,
            activity_level=str(person_payload["activity_level"]) if person_payload.get("activity_level") else None,
        )
        goal = self.create_goal_profile(
            person_id=person.id,
            starts_on=date.today(),
            targets=nutrients_from_mapping(payload["targets"]),
            notes=str(payload["notes"]) if payload.get("notes") else "Created from conversational onboarding.",
        )
        applied_payload = dict(payload)
        applied_payload.update(
            {
                "created_household_id": household.id,
                "created_person_id": person.id,
                "created_goal_id": goal.id,
            }
        )
        return CreateDiaryEntriesProposal(
            id=proposal.id,
            person_id=person.id,
            entries=proposal.entries,
            proposal_type=proposal.proposal_type,
            status="applied",
            summary=proposal.summary,
            payload=applied_payload,
            totals=proposal.totals,
            evidence=proposal.evidence,
            source_agent_run_id=proposal.source_agent_run_id,
            applied_record_ids=(household.id, person.id, goal.id),
            created_at=proposal.created_at,
            confirmed_at=proposal.confirmed_at or datetime.now(timezone.utc),
            rejected_at=proposal.rejected_at,
        )

    def _persist(self) -> None:
        if self.repository is not None:
            self.repository.save(self._snapshot())

    def _is_empty(self) -> bool:
        return not any(
            (
                self.households,
                self.people,
                self.goal_profiles,
                self.catalog.foods,
                self.catalog.versions,
                self.catalog.aliases,
                self.catalog.barcode_associations,
                self.diary.entries,
                self.weights,
                self.proposals.proposals,
                self.agent_runs,
                self.agent_tool_calls,
                self.chat_turns,
                self.onboarding_turns,
                self.jobs,
                self.review_notes,
                self.attachments,
                self.recipe_versions,
            )
        )

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
            "recipe_versions": [
                recipe_version_to_snapshot(item) for item in self.recipe_versions.values()
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
            "agent_tool_calls": [
                agent_tool_call_to_snapshot(item) for item in self.agent_tool_calls.values()
            ],
            "agent_chat_turns": [
                agent_chat_turn_to_snapshot(item) for item in self.chat_turns.values()
            ],
            "onboarding_turns": [
                onboarding_turn_to_snapshot(item) for item in self.onboarding_turns.values()
            ],
            "jobs": [background_job_to_snapshot(item) for item in self.jobs.values()],
            "review_notes": [
                review_note_to_snapshot(item) for item in self.review_notes.values()
            ],
            "attachment_objects": [
                attachment_to_snapshot(item) for item in self.attachments.values()
            ],
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
        self.recipe_versions = {
            item["food_version_id"]: recipe_version_from_snapshot(item)
            for item in snapshot.get("recipe_versions", [])
        }
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
        self.agent_tool_calls = {
            item["id"]: agent_tool_call_from_snapshot(item)
            for item in snapshot.get("agent_tool_calls", [])
        }
        self.chat_turns = {
            item["id"]: agent_chat_turn_from_snapshot(item)
            for item in snapshot.get("agent_chat_turns", [])
        }
        self.onboarding_turns = {
            item["id"]: onboarding_turn_from_snapshot(item)
            for item in snapshot.get("onboarding_turns", [])
        }
        self.jobs = {
            item["id"]: background_job_from_snapshot(item)
            for item in snapshot.get("jobs", [])
        }
        self.review_notes = {
            item["id"]: review_note_from_snapshot(item)
            for item in snapshot.get("review_notes", [])
        }
        self.attachments = {
            item["id"]: attachment_from_snapshot(item)
            for item in snapshot.get("attachment_objects", [])
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
    fragments = [
        fragment.strip()
        for fragment in re.split(r"[,;\n]\s*|\s+/\s+", strip_meal_heading(text))
        if fragment.strip()
    ]
    if not fragments:
        raise ValueError("text meal is empty")

    logged_at = default_logged_at
    first_time = parse_time_prefix(fragments[0], default_logged_at=default_logged_at)
    if first_time is not None:
        logged_at = first_time
        fragments = fragments[1:]

    items: list[ParsedMealItem] = []
    for fragment in fragments:
        removal = parse_text_meal_removal(fragment)
        if removal is not None:
            # A "-33g ossos e pele" line discounts waste from the item just listed.
            if not items or items[-1].evidence.get("quantity_basis") != "grams":
                raise ValueError(f"quantity discount without a weighable preceding item: {fragment}")
            last = items[-1]
            remaining = last.quantity_g - removal.quantity_g
            if remaining <= 0:
                raise ValueError(f"quantity discount removes the whole preceding item: {fragment}")
            items[-1] = ParsedMealItem(
                phrase=last.phrase,
                quantity_g=remaining,
                source_text=f"{last.source_text} ({fragment})",
                evidence={
                    **last.evidence,
                    "quantity_discount_g": removal.quantity_g,
                    "quantity_discount_phrase": removal.phrase,
                    "quantity_discount_source_text": fragment,
                },
            )
            continue
        items.append(parse_text_meal_item(fragment))
    if not items:
        raise ValueError("text meal has no food items")
    return logged_at, items


_MEAL_HEADING = (
    r"\s*(?:café da manhã|cafe da manha|café|cafe|breakfast|almoço|almoco|lunch|jantar|janta|dinner|lanche|snack)\s*:"
)


def text_looks_like_meal_amendment(text: str) -> bool:
    normalized = text.casefold().strip()
    if not normalized:
        return False
    # An explicit meal heading always starts a new meal, never an amendment —
    # even when the body contains removal ("-33g ossos") or addition lines.
    if re.match(_MEAL_HEADING, normalized):
        return False
    if re.search(r"(^|\n)\s*-+\s*\d", normalized):
        return True
    if re.search(
        r"\b(?:adicione|adiciona|acrescenta|acrescente|add|esqueci|esquecido|esqueceu|faltou"
        r"|inclui|incluir|inclua|coloca|colocar|bota|botar|remove|remova|retira|subtrai)\b",
        normalized,
    ):
        return True
    return re.search(r"\d+(?:[,.]\d+)?\s*g(?:ramas?)?\s+", normalized) is not None


def text_looks_like_chat_meal_log(text: str) -> bool:
    normalized = text.casefold().strip()
    if not normalized:
        return False
    if text_looks_like_meal_amendment(text):
        return True
    if re.match(_MEAL_HEADING, normalized):
        return re.search(r"\d+(?:[,.]\d+)?\s*g(?:ramas?)?\s+", normalized) is not None
    try:
        _, items = parse_text_meal_items(text, default_logged_at=datetime(2026, 1, 1, 12, 0))
    except ValueError:
        return False
    return any(item.evidence.get("quantity_basis") == "grams" for item in items)


def parse_chat_kcal_range_estimate(text: str) -> ParsedRangeEstimate | None:
    source_text = text.strip()
    if not source_text:
        return None
    match = re.search(
        r"(?P<low>\d{2,5}(?:[,.]\d+)?)\s*(?:-|–|—|\ba\b|\bat[eé]\b|\be\b)\s*"
        r"(?P<high>\d{2,5}(?:[,.]\d+)?)\s*(?:kcal|calorias?)\b",
        source_text,
        re.I,
    )
    if match is None:
        return None
    low_kcal = float(match.group("low").replace(",", "."))
    high_kcal = float(match.group("high").replace(",", "."))
    if low_kcal > high_kcal:
        low_kcal, high_kcal = high_kcal, low_kcal
    if low_kcal < 50 or high_kcal > 10000 or (high_kcal - low_kcal) < 10:
        return None

    label = source_text[: match.start()].strip(" \t\n\r:-–—,.;~")
    label = re.sub(
        r"\b(?:entre|de|aprox(?:imadamente)?|cerca de|mais ou menos|talvez|acho que|estimo|estimado|registra(?:r)?|coloca(?:r)?|log(?:ar)?)\s*$",
        "",
        label,
        flags=re.I,
    ).strip(" \t\n\r:-–—,.;~")
    if not label:
        after = source_text[match.end() :].strip()
        after_match = re.search(r"\b(?:na|no|num|em|para|pra|de|do|da)\s+(.+)$", after, re.I)
        if after_match is not None:
            label = after_match.group(1).strip(" \t\n\r:-–—,.;~")
    if not label:
        normalized = source_text.casefold()
        if re.search(r"\b(?:festa|party|restaurante|social|evento|rodizio|rodízio)\b", normalized):
            label = "Refeição social"
    if not label:
        return None
    label = re.sub(r"\s+", " ", label).strip()
    if label.casefold() in {"café", "cafe", "café da manhã", "cafe da manha"}:
        label = "Café estimado"
    elif label.casefold() in {"almoço", "almoco", "lunch"}:
        label = "Almoço estimado"
    elif label.casefold() in {"jantar", "dinner"}:
        label = "Jantar estimado"
    elif label.casefold() in {"lanche", "snack"}:
        label = "Lanche estimado"
    return ParsedRangeEstimate(
        label=label,
        low_kcal=low_kcal,
        high_kcal=high_kcal,
        source_text=source_text,
    )


_WEIGHT_NUMBER = r"(?<![\d.,])(\d{2,3}(?:[,.]\d{1,2})?)"


def _with_weight_note(weight_note: str | None, message: str) -> str:
    return f"{weight_note} {message}" if weight_note else message


def parse_chat_weight_entry(text: str) -> float | None:
    normalized = text.casefold()
    # Questions about weight are never weigh-ins.
    if "?" in normalized:
        return None
    match = re.search(_WEIGHT_NUMBER + r"\s*(?:kg|kgs|quilos?)\b", normalized)
    if match is None:
        weigh_in_verb = (
            r"(?:pesei(?:\s+hoje)?|amanheci(?:\s+hoje)?\s+com|"
            r"novo\s+peso\s*:?|peso\s+de\s+hoje\s*:?|"
            r"meu\s+peso(?:\s+hoje)?\s*(?:é|eh|está|esta|:|=))"
        )
        match = re.search(weigh_in_verb + r"\s*" + _WEIGHT_NUMBER + r"\b", normalized)
    if match is None:
        return None
    weight = float(match.group(1).replace(",", "."))
    if not 25 <= weight <= 350:
        return None
    return weight


def remove_chat_weight_lines(text: str) -> str:
    kept = [line for line in text.splitlines() if parse_chat_weight_entry(line) is None]
    return "\n".join(kept).strip()


def chat_default_logged_at(text: str, *, today: date) -> datetime:
    normalized = text.casefold().strip()
    hour = 12
    if re.match(r"\s*(?:café da manhã|cafe da manha|café|cafe|breakfast)\s*:", normalized):
        hour = 8
    elif re.match(r"\s*(?:lanche|snack)\s*:", normalized):
        hour = 16
    elif re.match(r"\s*(?:jantar|janta|dinner)\s*:", normalized):
        hour = 20
    return datetime.combine(today, datetime.min.time()).replace(hour=hour)


def parse_text_meal_amendment(text: str) -> tuple[str, list[ParsedMealRemoval]]:
    additions: list[str] = []
    removals: list[ParsedMealRemoval] = []
    fragments = [
        fragment.strip()
        for fragment in re.split(r"[,;\n]\s*|\s+/\s+", strip_meal_heading(text))
        if fragment.strip()
    ]
    for fragment in fragments:
        cleaned = fragment.strip()
        if re.fullmatch(
            r"(?:ah|opa|oi|ok|blz|beleza|valeu|obrigad[oa]|obg|ent[aã]o|tamb[eé]m|foi mal|desculpa)[!.…]*",
            cleaned,
            re.I,
        ):
            continue
        removal = parse_text_meal_removal(cleaned)
        if removal is not None:
            removals.append(removal)
            continue
        addition = re.sub(
            r"^\s*(?:ah[,!]?\s+|opa[,!]?\s+|tamb[eé]m\s+)?"
            r"(?:\+|adicione|adiciona|acrescenta|acrescente|add|inclui|incluir|inclua"
            r"|coloca(?:r)?|bota(?:r)?|faltou|(?:tinha\s+|tava\s+)?esquec(?:i|ido|eu)(?:\s+de)?)"
            r"(?:\s+(?:incluir|adicionar|acrescentar|colocar|botar|por|pôr|registrar|anotar))?"
            r"(?:\s*:)?\s+",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        addition = re.sub(
            r"^(\d+(?:[,.]\d+)?\s*g(?:ramas?)?)\s+de\s+",
            r"\1 ",
            addition,
            flags=re.I,
        )
        if addition:
            additions.append(addition)
    return ", ".join(additions), removals


def parse_text_meal_removal(fragment: str) -> ParsedMealRemoval | None:
    patterns = (
        r"^\s*-\s*(\d+(?:[,.]\d+)?)\s*g(?:ramas?)?\s+(.+)$",
        r"^\s*(?:remove|remova|retira|retire|subtrai|subtraia)\s+(\d+(?:[,.]\d+)?)\s*g(?:ramas?)?\s+(?:de\s+)?(.+)$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, fragment, re.I)
        if match is None:
            continue
        return ParsedMealRemoval(
            phrase=normalize_food_phrase(match.group(2)),
            quantity_g=float(match.group(1).replace(",", ".")),
            source_text=fragment,
        )
    return None


def strip_meal_heading(text: str) -> str:
    return re.sub(f"^{_MEAL_HEADING}\\s*", "", text, flags=re.I)


def parse_repeated_meal_reference(
    text: str,
    *,
    default_logged_at: datetime,
) -> tuple[date, str] | None:
    match = re.fullmatch(
        r"\s*(?:same|mesm[ao])\s+(breakfast|lunch|dinner|snack|late|café da manhã|cafe da manha|café|cafe|almoço|almoco|jantar|lanche)\s+(?:as|de|do|da)\s+(yesterday|ontem|today|hoje|\d{4}-\d{2}-\d{2})\s*",
        text,
        re.I,
    )
    if match is None:
        return None
    meal_type = normalize_meal_type(match.group(1))
    day_text = match.group(2).casefold()
    if day_text in {"yesterday", "ontem"}:
        source_day = default_logged_at.date() - timedelta(days=1)
    elif day_text in {"today", "hoje"}:
        source_day = default_logged_at.date()
    else:
        source_day = date.fromisoformat(day_text)
    return source_day, meal_type


def normalize_meal_type(value: str) -> str:
    normalized = value.casefold().strip()
    aliases = {
        "café da manhã": "breakfast",
        "cafe da manha": "breakfast",
        "café": "breakfast",
        "cafe": "breakfast",
        "almoço": "lunch",
        "almoco": "lunch",
        "jantar": "dinner",
        "lanche": "snack",
    }
    return aliases.get(normalized, normalized)


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

    unsupported_unit = re.fullmatch(
        r"(\d+(?:[,.]\d+)?)\s+(fatia|fatias|slice|slices)\s+(.+)",
        fragment,
        re.I,
    )
    if unsupported_unit is not None:
        quantity = float(unsupported_unit.group(1).replace(",", "."))
        unit = unsupported_unit.group(2).casefold()
        phrase = normalize_food_phrase(unsupported_unit.group(3))
        return ParsedMealItem(
            phrase=phrase,
            quantity_g=0,
            source_text=fragment,
            evidence={
                "quantity_basis": "unsupported_unit",
                "unit": unit,
                "unit_quantity": quantity,
            },
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
    normalized = value.strip().casefold()
    # "139g de feijão" and "139g feijão" must resolve to the same food.
    return re.sub(r"^(?:de|do|da|dos|das)\s+", "", normalized)


def parse_chat_day_reference(message: str, *, today: date) -> date | None:
    dated = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", message)
    if dated is not None:
        return date.fromisoformat(dated.group(1))
    lowered = message.casefold()
    if "yesterday" in lowered or "ontem" in lowered:
        return today - timedelta(days=1)
    if "today" in lowered or "hoje" in lowered:
        return today
    return None


def parse_chat_week_reference(message: str, *, today: date) -> tuple[date, date] | None:
    lowered = message.casefold()
    if "week" not in lowered and "semana" not in lowered:
        return None
    dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", message)
    if len(dates) >= 2:
        start = date.fromisoformat(dates[0])
        end = date.fromisoformat(dates[1])
        if end < start:
            raise ValueError("week end date must be on or after start date")
        return start, end
    start = today - timedelta(days=today.weekday())
    if "last week" in lowered or "semana passada" in lowered:
        start -= timedelta(days=7)
    return start, start + timedelta(days=6)


def parse_chat_micronutrient_question(message: str) -> bool:
    lowered = message.casefold()
    return any(
        marker in lowered
        for marker in (
            "micronutrient",
            "vitamin",
            "mineral",
            "nutrient gap",
            "nutritional gap",
            "nutrientes",
            "vitamina",
            "mineral",
        )
    )


def parse_chat_food_version_use_question(message: str) -> str | None:
    lowered = message.casefold()
    if not any(
        marker in lowered
        for marker in (
            "new label",
            "new version",
            "using the new",
            "novo rótulo",
            "novo rotulo",
            "nova versão",
            "nova versao",
            "nova embalagem",
        )
    ):
        return None

    patterns = (
        r"\bnew\s+(.+?)\s+(?:label|version)\b",
        r"\b(?:novo|nova)\s+(.+?)\s+(?:r[oó]tulo|rotulo|vers[aã]o|versao|embalagem)\b",
        r"\b(?:bought|comprei)\s+(?:a|an|o|a|um|uma)?\s*(?:new|novo|nova)\s+(.+?)(?:[.?]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, message, re.I)
        if match is None:
            continue
        phrase = normalize_food_phrase(match.group(1))
        phrase = re.sub(r"\b(?:the|o|a|um|uma)\b", " ", phrase, flags=re.I)
        phrase = re.sub(r"\s+", " ", phrase).strip(" .?")
        if phrase:
            return phrase
    return None


def parse_chat_quantity_correction(message: str) -> dict[str, object] | None:
    match = re.search(
        r"\b(?:change|correct|update|alterar|corrigir|mudar)\s+(.+?)\s+"
        r"(?:on|em)\s+(\d{4}-\d{2}-\d{2})\s+"
        r"(?:to|para)\s+(\d+(?:[,.]\d+)?)\s*g\b",
        message,
        re.I,
    )
    if match is None:
        return None
    return {
        "phrase": normalize_food_phrase(match.group(1)),
        "day": date.fromisoformat(match.group(2)),
        "quantity_g": float(match.group(3).replace(",", ".")),
    }


def parse_chat_review_note(message: str) -> dict[str, object] | None:
    match = re.search(
        r"^\s*(?:save|salvar|record|registrar)\s+"
        r"(?:(?:a|uma)\s+)?(?:review\s+)?(?:note|nota)"
        r"(?:\s+(?:for|de|para)\s+(\d{4}-\d{2}-\d{2})"
        r"(?:\s+(?:to|ate|até|-)\s+(\d{4}-\d{2}-\d{2}))?)?"
        r"\s*:\s*(.+?)\s*$",
        message,
        re.I | re.S,
    )
    if match is None:
        return None
    body = match.group(3).strip()
    if not body:
        return None
    starts_on = date.fromisoformat(match.group(1)) if match.group(1) else None
    ends_on = date.fromisoformat(match.group(2)) if match.group(2) else starts_on
    return {
        "starts_on": starts_on,
        "ends_on": ends_on,
        "body": body,
    }


def parse_chat_profile_goal_update(message: str, *, today: date) -> dict[str, object] | None:
    lowered = message.casefold()
    if not any(marker in lowered for marker in ("goal", "target", "meta", "perfil", "profile", "altura", "height")):
        return None

    target_patterns = {
        "calories_kcal": r"(?:calories|calorias|kcal)\s*(?:to|para|=|:)?\s*(\d+(?:[,.]\d+)?)",
        "protein_g": r"(?:protein|proteina|proteína)\s*(?:to|para|=|:)?\s*(\d+(?:[,.]\d+)?)\s*g?",
        "carbs_g": r"(?:carbs|carboidratos?)\s*(?:to|para|=|:)?\s*(\d+(?:[,.]\d+)?)\s*g?",
        "fat_g": r"(?:fat|gordura)\s*(?:to|para|=|:)?\s*(\d+(?:[,.]\d+)?)\s*g?",
        "fiber_g": r"(?:fiber|fibra)\s*(?:to|para|=|:)?\s*(\d+(?:[,.]\d+)?)\s*g?",
        "sodium_mg": r"(?:sodium|sodio|sódio)\s*(?:to|para|=|:)?\s*(\d+(?:[,.]\d+)?)\s*mg?",
    }
    targets: dict[str, float] = {}
    for key, pattern in target_patterns.items():
        match = re.search(pattern, message, re.I)
        if match is not None:
            targets[key] = float(match.group(1).replace(",", "."))
    if targets:
        defaults = {
            "calories_kcal": 2000.0,
            "protein_g": 150.0,
            "carbs_g": 180.0,
            "fat_g": 70.0,
            "fiber_g": 30.0,
            "sodium_mg": 2300.0,
        }
        defaults.update(targets)
        starts_on_match = re.search(r"\b(?:starting|from|a partir de|desde)\s+(\d{4}-\d{2}-\d{2})\b", message, re.I)
        starts_on = date.fromisoformat(starts_on_match.group(1)) if starts_on_match else today
        return {
            "proposal_type": "goal_profile",
            "summary": f"Create goal profile starting {starts_on.isoformat()}",
            "payload": {
                "starts_on": starts_on.isoformat(),
                "targets": defaults,
                "notes": "Agent-drafted target update",
            },
        }

    changes: dict[str, object] = {}
    height_match = re.search(r"(?:height|altura)\s*(?:to|para|=|:)?\s*(\d+(?:[,.]\d+)?)\s*cm?", message, re.I)
    if height_match is not None:
        changes["height_cm"] = float(height_match.group(1).replace(",", "."))
    activity_match = re.search(r"(?:activity|atividade)\s*(?:to|para|=|:)\s*([a-zA-ZÀ-ÿ _-]+)", message, re.I)
    if activity_match is not None:
        changes["activity_level"] = activity_match.group(1).strip(" .")
    timezone_match = re.search(r"(?:timezone|fuso)\s*(?:to|para|=|:)\s*([A-Za-z_/-]+)", message, re.I)
    if timezone_match is not None:
        changes["timezone"] = timezone_match.group(1).strip()
    if changes:
        return {
            "proposal_type": "profile_update",
            "summary": "Update profile fields",
            "payload": changes,
        }
    return None


def parse_chat_profile_goal_capability_question(message: str) -> bool:
    lowered = message.casefold()
    has_profile_or_goal = any(
        marker in lowered
        for marker in (
            "profile",
            "perfil",
            "goal",
            "goals",
            "target",
            "targets",
            "meta",
            "metas",
        )
    )
    has_change_intent = any(
        marker in lowered
        for marker in (
            "can you",
            "could you",
            "are you able",
            "alter",
            "change",
            "update",
            "adjust",
            "consegue",
            "pode",
            "alterar",
            "mudar",
            "ajustar",
            "atualizar",
        )
    )
    return has_profile_or_goal and has_change_intent and "?" in message


def parse_nutrition_label_text(text: str) -> ParsedNutritionLabel:
    fields = parse_label_fields(text)
    food_name = (
        fields.get("produto")
        or fields.get("product")
        or fields.get("nome")
        or infer_ocr_product_name(text)
    )
    if not food_name:
        raise ValueError("label text is missing product name")
    brand = fields.get("marca") or fields.get("brand")
    serving_text = (
        fields.get("porcao")
        or fields.get("porção")
        or fields.get("serving")
        or infer_ocr_serving_text(text)
    )
    if serving_text is None:
        raise ValueError("label text is missing serving size")
    serving_size_g = parse_grams(serving_text)
    if serving_size_g <= 0:
        raise ValueError("serving size must be positive")

    calories = parse_number_from_field(fields, ("valor energetico", "valor energético", "calorias", "calories", "energy"))
    protein = parse_number_from_field(fields, ("proteinas", "proteínas", "protein"))
    carbs = parse_number_from_field(fields, ("carboidratos", "carbs", "carbohydrate"))
    fat = parse_number_from_field(
        fields,
        ("gorduras totais", "gordura totais", "gordura total", "fat", "total fat"),
    )
    fiber = parse_number_from_field(fields, ("fibra alimentar", "fibras alimentares", "fibras", "fiber"), default=0)
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
    if yield_g is not None and yield_g <= 0:
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
    for key, value in parse_markdown_nutrition_table_fields(text).items():
        fields.setdefault(key, value)
    return fields


def normalize_label_key(value: str) -> str:
    without_units = re.sub(r"\s*\([^)]*\)", "", value.strip().casefold())
    return re.sub(r"\s+", " ", without_units).strip()


def infer_ocr_product_name(text: str) -> str | None:
    skipped_prefixes = (
        "lote",
        "data ",
        "tara ",
        "ingrediente",
        "nao contem",
        "não contém",
        "conserva",
        "informacao nutricional",
        "informação nutricional",
        "porcao",
        "porção",
    )
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("|").strip()
        if not line or ":" in line:
            continue
        normalized = normalize_label_key(line)
        if normalized.startswith(skipped_prefixes):
            continue
        if normalized.startswith(":---") or normalized in {"100g", "80g", "%vd"}:
            continue
        return line
    return None


def infer_ocr_serving_text(text: str) -> str | None:
    match = re.search(r"\bpor[cç][aã]o\s*:\s*([^\n|]+?\d+(?:[,.]\d+)?\s*g)\b", text, re.I)
    if match is not None:
        return match.group(1).strip()
    match = re.search(r"\bserving(?: size)?\s*:\s*([^\n|]+?\d+(?:[,.]\d+)?\s*g)\b", text, re.I)
    if match is not None:
        return match.group(1).strip()
    return None


def parse_markdown_nutrition_table_fields(text: str) -> dict[str, str]:
    nutrient_keys = {
        normalize_label_key("Valor energetico"),
        normalize_label_key("Valor energético"),
        normalize_label_key("Calorias"),
        normalize_label_key("Proteinas"),
        normalize_label_key("Proteínas"),
        normalize_label_key("Carboidratos"),
        normalize_label_key("Gorduras totais"),
        normalize_label_key("Gordura totais"),
        normalize_label_key("Gordura total"),
        normalize_label_key("Fibra alimentar"),
        normalize_label_key("Fibras alimentares"),
        normalize_label_key("Sodio"),
        normalize_label_key("Sódio"),
    }
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        for index, cell in enumerate(cells):
            key = normalize_label_key(cell)
            if key not in nutrient_keys:
                continue
            values: list[str] = []
            for following in cells[index + 1 :]:
                following_key = normalize_label_key(following)
                if following_key in nutrient_keys:
                    break
                if re.search(r"\d", following):
                    values.append(following)
            if values:
                fields.setdefault(key, values[1] if len(values) > 1 else values[0])
    return fields


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


def nutrients_from_mapping(value: Any) -> Nutrients:
    if not isinstance(value, dict):
        raise ValueError("nutrient targets must be an object")
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


def day_summary_evidence_status(entry_source: str, version_source: str) -> str:
    entry_source = entry_source.casefold()
    version_source = version_source.casefold()
    if "range" in entry_source or "range" in version_source:
        return "range_estimate"
    if "model_estimate" in version_source or "estimate" in version_source:
        return "estimated"
    if "external_lookup" in version_source or "lookup" in entry_source:
        return "looked_up"
    if entry_source.startswith("agent"):
        return "inferred"
    return "exact"


def day_summary_confidence(*, evidence_status: str, version_confidence: float) -> float:
    if evidence_status == "exact":
        return 1.0
    return version_confidence


def food_version_to_snapshot(version: FoodVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "food_id": version.food_id,
        "label": version.label,
        "nutrients_per_100g": nutrients_to_snapshot(version.nutrients_per_100g),
        "source": version.source,
        "serving_size_g": version.serving_size_g,
        "confidence": version.confidence,
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
        confidence=float(value.get("confidence", 1.0)),
        created_at=datetime.fromisoformat(value["created_at"]),
        archived=bool(value.get("archived", False)),
    )


def recipe_version_from_proposal_payload(
    *,
    id: str,
    household_id: str,
    food_id: str,
    food_version_id: str,
    payload: dict[str, Any],
    source_proposal_id: str,
) -> RecipeVersion:
    return RecipeVersion(
        id=id,
        household_id=household_id,
        food_id=food_id,
        food_version_id=food_version_id,
        name=str(payload["food_name"]),
        yield_g=float(payload["yield_g"]),
        ingredients=tuple(
            RecipeIngredient(
                food_id=str(item["food_id"]),
                food_version_id=str(item["food_version_id"]),
                food_name=str(item["food_name"]),
                quantity_g=float(item["quantity_g"]),
                nutrients=nutrients_from_snapshot(dict(item["nutrients"])),
            )
            for item in payload.get("ingredients", [])
        ),
        source_proposal_id=source_proposal_id,
    )


def recipe_version_to_snapshot(recipe: RecipeVersion) -> dict[str, Any]:
    return {
        "id": recipe.id,
        "household_id": recipe.household_id,
        "food_id": recipe.food_id,
        "food_version_id": recipe.food_version_id,
        "name": recipe.name,
        "yield_g": recipe.yield_g,
        "ingredients": [
            {
                "food_id": ingredient.food_id,
                "food_version_id": ingredient.food_version_id,
                "food_name": ingredient.food_name,
                "quantity_g": ingredient.quantity_g,
                "nutrients": nutrients_to_snapshot(ingredient.nutrients),
            }
            for ingredient in recipe.ingredients
        ],
        "source_proposal_id": recipe.source_proposal_id,
        "created_at": recipe.created_at.isoformat(),
    }


def recipe_version_from_snapshot(value: dict[str, Any]) -> RecipeVersion:
    return RecipeVersion(
        id=value["id"],
        household_id=value["household_id"],
        food_id=value["food_id"],
        food_version_id=value["food_version_id"],
        name=value["name"],
        yield_g=float(value["yield_g"]),
        ingredients=tuple(
            RecipeIngredient(
                food_id=item["food_id"],
                food_version_id=item["food_version_id"],
                food_name=item["food_name"],
                quantity_g=float(item["quantity_g"]),
                nutrients=nutrients_from_snapshot(item["nutrients"]),
            )
            for item in value.get("ingredients", [])
        ),
        source_proposal_id=value.get("source_proposal_id"),
        created_at=datetime.fromisoformat(value["created_at"]),
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
        "confirmed_at": proposal.confirmed_at.isoformat()
        if proposal.confirmed_at is not None
        else None,
        "rejected_at": proposal.rejected_at.isoformat()
        if proposal.rejected_at is not None
        else None,
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
        confirmed_at=datetime.fromisoformat(value["confirmed_at"])
        if value.get("confirmed_at")
        else None,
        rejected_at=datetime.fromisoformat(value["rejected_at"])
        if value.get("rejected_at")
        else None,
    )


def agent_run_to_snapshot(run: AgentRun) -> dict[str, Any]:
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
    }


def agent_run_from_snapshot(value: dict[str, Any]) -> AgentRun:
    return AgentRun(
        id=value["id"],
        person_id=value["person_id"],
        input_text=value["input_text"],
        settings=dict(value.get("settings", {})),
        status=value["status"],
        proposal_id=value.get("proposal_id"),
        runtime=value.get("runtime"),
        model_name=value.get("model_name"),
        tool_loop_count=int(value.get("tool_loop_count") or 0),
        fallback_reason=value.get("fallback_reason"),
        created_at=datetime.fromisoformat(value["created_at"]),
    )


def agent_tool_call_to_snapshot(call: AgentToolCall) -> dict[str, Any]:
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


def agent_tool_call_from_snapshot(value: dict[str, Any]) -> AgentToolCall:
    return AgentToolCall(
        id=value["id"],
        agent_run_id=value["agent_run_id"],
        person_id=value["person_id"],
        tool_name=value["tool_name"],
        input_summary=value["input_summary"],
        output_summary=value["output_summary"],
        status=value["status"],
        source_record_ids=tuple(value.get("source_record_ids", [])),
        error=value.get("error"),
        started_at=datetime.fromisoformat(value["started_at"]),
        completed_at=datetime.fromisoformat(value["completed_at"])
        if value.get("completed_at")
        else None,
    )


def agent_chat_turn_to_snapshot(turn: AgentChatTurn) -> dict[str, Any]:
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
    }


def agent_chat_turn_from_snapshot(value: dict[str, Any]) -> AgentChatTurn:
    return AgentChatTurn(
        id=value["id"],
        person_id=value["person_id"],
        agent_run_id=value["agent_run_id"],
        user_message=value["user_message"],
        assistant_message=value["assistant_message"],
        behavior_label=value["behavior_label"],
        citations=tuple(dict(item) for item in value.get("citations", [])),
        proposal_id=value.get("proposal_id"),
        created_at=datetime.fromisoformat(value["created_at"]),
    )


def onboarding_turn_to_snapshot(turn: OnboardingTurn) -> dict[str, Any]:
    return {
        "id": turn.id,
        "session_id": turn.session_id,
        "household_id": turn.household_id,
        "user_message": turn.user_message,
        "assistant_message": turn.assistant_message,
        "proposal_id": turn.proposal_id,
        "created_at": turn.created_at.isoformat(),
    }


def onboarding_turn_from_snapshot(value: dict[str, Any]) -> OnboardingTurn:
    return OnboardingTurn(
        id=value["id"],
        session_id=value["session_id"],
        household_id=value.get("household_id"),
        user_message=value["user_message"],
        assistant_message=value["assistant_message"],
        proposal_id=value.get("proposal_id"),
        created_at=datetime.fromisoformat(value["created_at"]),
    )


def background_job_to_snapshot(job: BackgroundJob) -> dict[str, Any]:
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


def background_job_from_snapshot(value: dict[str, Any]) -> BackgroundJob:
    return BackgroundJob(
        id=value["id"],
        job_type=value["job_type"],
        status=value["status"],
        payload=dict(value.get("payload", {})),
        client_request_id=value.get("client_request_id"),
        result=dict(value.get("result", {})),
        last_error=value.get("last_error"),
        attempts=int(value.get("attempts", 0)),
        created_at=datetime.fromisoformat(value["created_at"]),
        updated_at=datetime.fromisoformat(value.get("updated_at", value["created_at"])),
        started_at=datetime.fromisoformat(value["started_at"]) if value.get("started_at") else None,
        completed_at=datetime.fromisoformat(value["completed_at"]) if value.get("completed_at") else None,
    )


def review_note_to_snapshot(note: ReviewNote) -> dict[str, Any]:
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


def review_note_from_snapshot(value: dict[str, Any]) -> ReviewNote:
    return ReviewNote(
        id=value["id"],
        person_id=value["person_id"],
        note_type=value.get("note_type", "review"),
        title=value.get("title", "Review note"),
        body=value["body"],
        starts_on=date.fromisoformat(value["starts_on"]) if value.get("starts_on") else None,
        ends_on=date.fromisoformat(value["ends_on"]) if value.get("ends_on") else None,
        source=value.get("source", "manual"),
        source_agent_run_id=value.get("source_agent_run_id"),
        source_proposal_id=value.get("source_proposal_id"),
        source_record_refs=tuple(value.get("source_record_refs", [])),
        created_at=datetime.fromisoformat(value["created_at"]),
    )


def attachment_to_snapshot(attachment: AttachmentObject) -> dict[str, Any]:
    return {
        "id": attachment.id,
        "household_id": attachment.household_id,
        "created_by_person_id": attachment.created_by_person_id,
        "object_type": attachment.object_type,
        "mime_type": attachment.mime_type,
        "byte_size": attachment.byte_size,
        "sha256": attachment.sha256,
        "content_base64": base64.b64encode(attachment.content).decode("ascii"),
        "filename": attachment.filename,
        "storage_status": attachment.storage_status,
        "retention_policy": attachment.retention_policy,
        "linked_record_type": attachment.linked_record_type,
        "linked_record_id": attachment.linked_record_id,
        "created_at": attachment.created_at.isoformat(),
    }


def attachment_from_snapshot(value: dict[str, Any]) -> AttachmentObject:
    content = base64.b64decode(value["content_base64"])
    return AttachmentObject(
        id=value["id"],
        household_id=value["household_id"],
        created_by_person_id=value["created_by_person_id"],
        object_type=value["object_type"],
        mime_type=value["mime_type"],
        byte_size=int(value["byte_size"]),
        sha256=value["sha256"],
        content=content,
        filename=value.get("filename"),
        storage_status=value.get("storage_status", "stored"),
        retention_policy=value.get("retention_policy", "keep"),
        linked_record_type=value.get("linked_record_type"),
        linked_record_id=value.get("linked_record_id"),
        created_at=datetime.fromisoformat(value["created_at"]),
    )
