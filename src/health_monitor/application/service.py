from __future__ import annotations

import base64
import hashlib
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
from health_monitor.lookup.foods import FoodLookupCandidate, FoodLookupProvider
from health_monitor.lookup.labels import LabelTextExtraction, LabelTextExtractor
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
        label_text_extractor: LabelTextExtractor | None = None,
    ) -> None:
        self.repository = repository
        self.estimator = estimator
        self.food_lookup_provider = food_lookup_provider
        self.label_text_extractor = label_text_extractor
        self.households: dict[str, Household] = {}
        self.people: dict[str, Person] = {}
        self.goal_profiles: dict[str, GoalProfile] = {}
        self.catalog = FoodCatalog()
        self.diary = Diary(self.catalog)
        self.weights: dict[str, WeightEntry] = {}
        self.resolver = FoodResolver(self.catalog)
        self.proposals = ProposalService(self.diary)
        self.agent_runs: dict[str, AgentRun] = {}
        self.review_notes: dict[str, ReviewNote] = {}
        self.lookup_candidates: dict[str, FoodLookupCandidate] = {}
        self.attachments: dict[str, AttachmentObject] = {}
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

    def update_proposal_entry(
        self,
        *,
        proposal_id: str,
        entry_id: str,
        quantity_g: float | None = None,
        meal_type: str | None = None,
    ) -> CreateDiaryEntriesProposal:
        proposal = self.proposals.proposals[proposal_id]
        if proposal.status != "draft":
            raise ValueError("only draft proposals can be edited")
        if not proposal.entries:
            raise ValueError("proposal has no editable diary entries")
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
                    food_version_id=entry.food_version_id,
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
            self._updated_proposal_evidence_item(item, tuple(updated_entries))
            for item in proposal.evidence
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
        )
        self.proposals.proposals[proposal_id] = updated
        self._persist()
        return updated

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
        entries: tuple[DiaryEntry, ...],
    ) -> dict[str, object]:
        updated = dict(item)
        food_version_id = item.get("food_version_id")
        if food_version_id is None:
            return updated
        for entry in entries:
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
            "review_notes": len(self.review_notes),
            "attachment_objects": len(self.attachments),
        }

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

    def chat(
        self,
        *,
        person_id: str,
        message: str,
        today: date,
        agent_settings: dict[str, Any] | None = None,
    ) -> AgentChatResponse:
        settings = dict(agent_settings or {})
        self._require_person(person_id)
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=message,
            settings=settings,
            status="started",
        )
        self.agent_runs[run.id] = run

        correction = parse_chat_quantity_correction(message)
        if correction is not None:
            response = self._chat_draft_diary_correction(
                person_id=person_id,
                message=message,
                today=today,
                run=run,
                correction=correction,
            )
            self._persist()
            return response

        review_note = parse_chat_review_note(message)
        if review_note is not None:
            response = self._chat_draft_review_note(
                person_id=person_id,
                message=message,
                run=run,
                review_note=review_note,
            )
            self._persist()
            return response

        if parse_chat_micronutrient_question(message):
            response = self._chat_analyze_micronutrients(
                person_id=person_id,
                message=message,
                today=today,
                run=run,
            )
            self._persist()
            return response

        requested_week = parse_chat_week_reference(message, today=today)
        if requested_week is not None:
            start, end = requested_week
            response = self._chat_explain_week(
                person_id=person_id,
                message=message,
                run=run,
                start=start,
                end=end,
            )
            self._persist()
            return response

        requested_day = parse_chat_day_reference(message, today=today)
        if requested_day is not None:
            response = self._chat_explain_day(
                person_id=person_id,
                message=message,
                run=run,
                day=requested_day,
            )
            self._persist()
            return response

        response = AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=(
                "I can answer diary day/week summary questions and draft diary quantity "
                "corrections from structured app data. I do not have enough context for "
                "that request yet."
            ),
            behavior_label="answer_question",
        )
        self.agent_runs[run.id] = AgentRun(
            id=run.id,
            person_id=run.person_id,
            input_text=run.input_text,
            settings=run.settings,
            status="answered",
            created_at=run.created_at,
        )
        self._persist()
        return response

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
        repeated_meal = parse_repeated_meal_reference(text, default_logged_at=logged_at)
        run = AgentRun(
            id=self._next_id("agent_run"),
            person_id=person_id,
            input_text=text,
            settings=settings,
            status="started",
        )
        self.agent_runs[run.id] = run
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
        parsed_logged_at, items = parse_text_meal_items(text, default_logged_at=logged_at)
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
            resolution: FoodResolution | None = None
            estimate: NutritionEstimate | None = None
            evidence_source_type = "local_food"
            evidence_source_details: dict[str, object] = {}
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
                if not settings.get("external_lookup", True):
                    raise
                lookup_candidate = self._lookup_first_external_food_candidate(item.phrase)
                if lookup_candidate is not None:
                    food_id = self._next_id("food")
                    food_version_id = self._next_id("food_version")
                    version_label = f"{lookup_candidate.source_name} lookup"
                    version = FoodVersion(
                        id=food_version_id,
                        food_id=food_id,
                        label=version_label,
                        nutrients_per_100g=lookup_candidate.nutrients_per_100g,
                        source="external_lookup",
                        serving_size_g=lookup_candidate.serving_size_g,
                    )
                    estimated_food_versions.append(
                        {
                            "food_id": food_id,
                            "food_version_id": food_version_id,
                            "household_id": person.household_id,
                            "food_name": lookup_candidate.product_name,
                            "brand": lookup_candidate.brand,
                            "phrase": item.phrase,
                            "version_label": version_label,
                            "nutrients_per_100g": nutrients_to_snapshot(
                                lookup_candidate.nutrients_per_100g.rounded()
                            ),
                            "source": "external_lookup",
                            "source_type": lookup_candidate.source_type,
                            "source_name": lookup_candidate.source_name,
                            "source_id": lookup_candidate.source_id,
                            "source_url": lookup_candidate.source_url,
                            "barcode": lookup_candidate.barcode,
                            "serving_size_g": lookup_candidate.serving_size_g,
                            "confidence": lookup_candidate.confidence,
                            "warnings": list(lookup_candidate.warnings),
                        }
                    )
                    source = "agent_lookup_proposal"
                    resolution_reason = "external_lookup"
                    confidence = lookup_candidate.confidence
                    evidence_source_type = lookup_candidate.source_type
                    evidence_source_details = {
                        "source_name": lookup_candidate.source_name,
                        "source_id": lookup_candidate.source_id,
                        "source_url": lookup_candidate.source_url,
                        "warnings": list(lookup_candidate.warnings),
                    }
                else:
                    if self.estimator is None:
                        raise ValueError(f"food reference could not be resolved or estimated: {item.phrase}")
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
                            "brand": None,
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
                    evidence_source_type = "model_estimate"
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

    def _create_text_meal_clarification_proposal(
        self,
        *,
        person_id: str,
        text: str,
        run: AgentRun,
        logged_at: datetime,
        unresolved_items: tuple[ParsedMealItem, ...] | list[ParsedMealItem],
    ) -> CreateDiaryEntriesProposal:
        unresolved_payload = [
            {
                "source_text": item.source_text,
                "phrase": item.phrase,
                "unit": item.evidence.get("unit"),
                "quantity": item.evidence.get("unit_quantity", item.quantity_g),
                "quantity_basis": item.evidence.get("quantity_basis"),
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
                summary="Need grams or serving size before logging this meal.",
                payload={
                    "logged_at_local": logged_at.isoformat(),
                    "raw_text": text,
                    "missing_fields": ["quantity_g"],
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
        self.agent_runs[run.id] = AgentRun(
            id=run.id,
            person_id=run.person_id,
            input_text=run.input_text,
            settings=run.settings,
            status="needs_clarification",
            proposal_id=proposal.id,
            created_at=run.created_at,
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
        self.agent_runs[run.id] = AgentRun(
            id=run.id,
            person_id=run.person_id,
            input_text=run.input_text,
            settings=run.settings,
            status="proposal_created",
            proposal_id=proposal.id,
            created_at=run.created_at,
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
        self.agent_runs[run.id] = AgentRun(
            id=run.id,
            person_id=run.person_id,
            input_text=run.input_text,
            settings=run.settings,
            status="answered",
            created_at=run.created_at,
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
        self.agent_runs[run.id] = AgentRun(
            id=run.id,
            person_id=run.person_id,
            input_text=run.input_text,
            settings=run.settings,
            status="answered",
            created_at=run.created_at,
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message=answer,
            behavior_label=behavior_label,
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
        self.agent_runs[run.id] = AgentRun(
            id=run.id,
            person_id=run.person_id,
            input_text=run.input_text,
            settings=run.settings,
            status="answered",
            created_at=run.created_at,
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
        self.agent_runs[run.id] = AgentRun(
            id=run.id,
            person_id=run.person_id,
            input_text=run.input_text,
            settings=run.settings,
            status="proposal_created",
            proposal_id=proposal.id,
            created_at=run.created_at,
        )
        return AgentChatResponse(
            run_id=run.id,
            person_id=person_id,
            message="I drafted a review note. Confirm the proposal to save it.",
            behavior_label="draft_review_note",
            proposal_id=proposal.id,
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
        if not matches:
            self.agent_runs[run.id] = AgentRun(
                id=run.id,
                person_id=run.person_id,
                input_text=run.input_text,
                settings=run.settings,
                status="answered",
                created_at=run.created_at,
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
        self.agent_runs[run.id] = AgentRun(
            id=run.id,
            person_id=run.person_id,
            input_text=run.input_text,
            settings=run.settings,
            status="proposal_created",
            proposal_id=proposal.id,
            created_at=run.created_at,
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

    def propose_label_scan(
        self,
        *,
        household_id: str,
        person_id: str,
        table_text: str | None,
        set_as_default: bool = True,
        attachment_id: str | None = None,
        barcode: str | None = None,
        logged_at_local: str | None = None,
        quantity_g: float | None = None,
        meal_type: str | None = None,
    ) -> CreateDiaryEntriesProposal:
        self._require_household(household_id)
        person = self._require_person(person_id)
        attachment = None
        if attachment_id is not None:
            attachment = self.get_attachment(attachment_id)
            if attachment.household_id != household_id:
                raise ValueError("attachment belongs to a different household")
        text_source = "user_text"
        extraction: LabelTextExtraction | None = None
        normalized_text = (table_text or "").strip()
        if not normalized_text:
            if attachment is None or self.label_text_extractor is None:
                raise ValueError("label scan requires table text or an attachment text extractor")
            extraction = self.label_text_extractor.extract(
                image_bytes=attachment.content,
                mime_type=attachment.mime_type,
                filename=attachment.filename,
            )
            if extraction is None or not extraction.text.strip():
                raise ValueError("could not extract nutrition label text from attachment")
            normalized_text = extraction.text.strip()
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
            "attachment_id": attachment_id,
            "text_source": text_source,
            "ocr_text": extraction.text if extraction is not None else None,
            "ocr_source": extraction.source if extraction is not None else None,
            "ocr_confidence": extraction.confidence if extraction is not None else None,
            "ocr_warnings": list(extraction.warnings) if extraction is not None else [],
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
                        "attachment_id": attachment_id,
                        "text_source": text_source,
                        "ocr_source": extraction.source if extraction is not None else None,
                        "ocr_confidence": extraction.confidence if extraction is not None else None,
                        "ocr_warnings": list(extraction.warnings) if extraction is not None else [],
                        "logged_diary_entry": bool(entries),
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

    def get_agent_run(self, agent_run_id: str) -> AgentRun:
        return self.agent_runs[agent_run_id]

    def confirm_proposal(self, proposal_id: str) -> CreateDiaryEntriesProposal:
        proposal = self.proposals.proposals[proposal_id]
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
        food, version = self._create_food_with_version(
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
            food_id=str(payload["food_id"]) if payload.get("food_id") is not None else None,
            version_id=str(payload["food_version_id"]) if payload.get("food_version_id") is not None else None,
        )
        applied_ids = [food.id, version.id]
        barcode = payload.get("barcode")
        if barcode is not None:
            association = self.catalog.resolve_barcode(str(barcode))
            if association is not None:
                applied_ids.append(association.id)
        attachment_id = payload.get("attachment_id")
        if attachment_id is not None:
            self._link_attachment(
                str(attachment_id),
                linked_record_type="food_version",
                linked_record_id=version.id,
            )
            applied_ids.append(str(attachment_id))
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
            food_id=(
                existing_food.id
                if existing_food is not None
                else str(payload["food_id"]) if payload.get("food_id") is not None else None
            ),
            version_id=str(payload["food_version_id"]) if payload.get("food_version_id") is not None else None,
        )
        applied_ids = [food.id, version.id]
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
                self.review_notes,
                self.attachments,
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


def parse_repeated_meal_reference(
    text: str,
    *,
    default_logged_at: datetime,
) -> tuple[date, str] | None:
    match = re.fullmatch(
        r"\s*(?:same|mesm[ao])\s+(breakfast|lunch|dinner|snack|late|café da manhã|cafe da manha|almoço|almoco|jantar|lanche)\s+(?:as|de|do|da)\s+(yesterday|ontem|today|hoje|\d{4}-\d{2}-\d{2})\s*",
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
    return value.strip().casefold()


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
