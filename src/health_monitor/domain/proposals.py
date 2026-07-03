from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from health_monitor.domain.diary import Diary, DiaryEntry
from health_monitor.domain.nutrients import Nutrients


ProposalStatus = Literal[
    "draft",
    "needs_clarification",
    "confirmed",
    "applied",
    "rejected",
    "superseded",
]
ProposalType = Literal[
    "diary_entries",
    "diary_entries_with_estimates",
    "food_version_from_label",
    "recipe_food_version",
    "recipe_draft",
    "diary_entry_update",
    "food_version_from_lookup",
    "review_note",
    "profile_update",
    "goal_profile",
    "profile_setup",
]


@dataclass(frozen=True)
class CreateDiaryEntriesProposal:
    id: str
    person_id: str
    entries: tuple[DiaryEntry, ...]
    proposal_type: ProposalType = "diary_entries"
    status: ProposalStatus = "draft"
    summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    totals: Nutrients = field(default_factory=Nutrients)
    evidence: tuple[dict[str, object], ...] = ()
    source_agent_run_id: str | None = None
    applied_record_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: datetime | None = None
    rejected_at: datetime | None = None


class ProposalService:
    def __init__(self, diary: Diary) -> None:
        self.diary = diary
        self.proposals: dict[str, CreateDiaryEntriesProposal] = {}

    def create(self, proposal: CreateDiaryEntriesProposal) -> CreateDiaryEntriesProposal:
        self.proposals[proposal.id] = proposal
        return proposal

    def reject(self, proposal_id: str) -> CreateDiaryEntriesProposal:
        proposal = self.proposals[proposal_id]
        if proposal.status == "applied":
            raise ValueError("cannot reject applied proposal")
        if proposal.status == "superseded":
            raise ValueError("cannot reject superseded proposal")
        if proposal.status == "rejected":
            raise ValueError("proposal is already rejected")
        now = datetime.now(timezone.utc)
        rejected = CreateDiaryEntriesProposal(
            id=proposal.id,
            person_id=proposal.person_id,
            entries=proposal.entries,
            proposal_type=proposal.proposal_type,
            status="rejected",
            summary=proposal.summary,
            payload=proposal.payload,
            totals=proposal.totals,
            evidence=proposal.evidence,
            source_agent_run_id=proposal.source_agent_run_id,
            applied_record_ids=proposal.applied_record_ids,
            created_at=proposal.created_at,
            confirmed_at=proposal.confirmed_at,
            rejected_at=now,
        )
        self.proposals[proposal_id] = rejected
        return rejected

    def confirm_and_apply(self, proposal_id: str) -> CreateDiaryEntriesProposal:
        proposal = self.proposals[proposal_id]
        if proposal.status == "applied":
            raise ValueError("proposal is already applied")
        if proposal.status == "superseded":
            raise ValueError("proposal is superseded")
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        if proposal.status == "needs_clarification":
            raise ValueError("proposal needs clarification before it can be applied")
        if proposal.proposal_type != "diary_entries":
            raise ValueError(f"proposal type cannot be applied by diary service: {proposal.proposal_type}")
        now = datetime.now(timezone.utc)
        for entry in proposal.entries:
            self.diary.add_entry(entry)
        applied = CreateDiaryEntriesProposal(
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
            applied_record_ids=tuple(entry.id for entry in proposal.entries),
            created_at=proposal.created_at,
            confirmed_at=proposal.confirmed_at or now,
            rejected_at=proposal.rejected_at,
        )
        self.proposals[proposal_id] = applied
        return applied

    def supersede(
        self,
        proposal_id: str,
        *,
        superseded_by_proposal_id: str,
    ) -> CreateDiaryEntriesProposal:
        proposal = self.proposals[proposal_id]
        if proposal.status == "applied":
            raise ValueError("cannot supersede applied proposal")
        if proposal.status == "rejected":
            raise ValueError("cannot supersede rejected proposal")
        if proposal.status == "superseded":
            raise ValueError("proposal is already superseded")
        superseded = CreateDiaryEntriesProposal(
            id=proposal.id,
            person_id=proposal.person_id,
            entries=proposal.entries,
            proposal_type=proposal.proposal_type,
            status="superseded",
            summary=proposal.summary,
            payload={
                **proposal.payload,
                "superseded_by_proposal_id": superseded_by_proposal_id,
            },
            totals=proposal.totals,
            evidence=proposal.evidence,
            source_agent_run_id=proposal.source_agent_run_id,
            applied_record_ids=proposal.applied_record_ids,
            created_at=proposal.created_at,
            confirmed_at=proposal.confirmed_at,
            rejected_at=proposal.rejected_at,
        )
        self.proposals[proposal_id] = superseded
        return superseded
