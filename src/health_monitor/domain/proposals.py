from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from health_monitor.domain.diary import Diary, DiaryEntry
from health_monitor.domain.nutrients import Nutrients


ProposalStatus = Literal["draft", "confirmed", "applied", "rejected"]
ProposalType = Literal[
    "diary_entries",
    "diary_entries_with_estimates",
    "food_version_from_label",
    "recipe_food_version",
    "recipe_draft",
    "diary_entry_update",
    "food_version_from_lookup",
    "review_note",
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


class ProposalService:
    def __init__(self, diary: Diary) -> None:
        self.diary = diary
        self.proposals: dict[str, CreateDiaryEntriesProposal] = {}

    def create(self, proposal: CreateDiaryEntriesProposal) -> CreateDiaryEntriesProposal:
        self.proposals[proposal.id] = proposal
        return proposal

    def reject(self, proposal_id: str) -> CreateDiaryEntriesProposal:
        proposal = self.proposals[proposal_id]
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
        )
        self.proposals[proposal_id] = rejected
        return rejected

    def confirm_and_apply(self, proposal_id: str) -> CreateDiaryEntriesProposal:
        proposal = self.proposals[proposal_id]
        if proposal.status == "rejected":
            raise ValueError("cannot apply rejected proposal")
        if proposal.proposal_type != "diary_entries":
            raise ValueError(f"proposal type cannot be applied by diary service: {proposal.proposal_type}")
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
        )
        self.proposals[proposal_id] = applied
        return applied
