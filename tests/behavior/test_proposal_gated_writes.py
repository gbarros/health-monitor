from __future__ import annotations

import unittest
from datetime import datetime, timezone

from health_monitor.domain.diary import Diary, DiaryEntry
from health_monitor.domain.foods import Food, FoodCatalog, FoodVersion
from health_monitor.domain.nutrients import Nutrients
from health_monitor.domain.proposals import CreateDiaryEntriesProposal, ProposalService


class ProposalGatedWritesBehaviorTest(unittest.TestCase):
    def make_services(self) -> tuple[Diary, ProposalService]:
        catalog = FoodCatalog()
        catalog.add_food(Food(id="food_egg", household_id="household_1", name="Ovo"))
        catalog.add_version(
            FoodVersion(
                id="egg_large",
                food_id="food_egg",
                label="Large egg",
                source="reference",
                nutrients_per_100g=Nutrients(calories_kcal=155, protein_g=13),
            ),
            make_default=True,
        )
        diary = Diary(catalog)
        return diary, ProposalService(diary)

    def test_rejected_proposal_does_not_create_diary_entries(self) -> None:
        diary, proposals = self.make_services()
        entry = DiaryEntry(
            id="entry_proposed",
            person_id="person_1",
            logged_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
            meal_type="breakfast",
            food_version_id="egg_large",
            quantity_g=100,
            source="agent_proposal",
        )
        proposals.create(
            CreateDiaryEntriesProposal(id="proposal_1", person_id="person_1", entries=(entry,))
        )

        proposals.reject("proposal_1")
        rejected = proposals.proposals["proposal_1"]

        self.assertEqual(diary.entries_for_day("person_1", datetime(2026, 7, 1).date()), [])
        self.assertEqual(rejected.status, "rejected")
        self.assertIsNotNone(rejected.rejected_at)
        self.assertIsNone(rejected.confirmed_at)

    def test_confirmed_proposal_creates_diary_entries(self) -> None:
        diary, proposals = self.make_services()
        entry = DiaryEntry(
            id="entry_proposed",
            person_id="person_1",
            logged_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
            meal_type="breakfast",
            food_version_id="egg_large",
            quantity_g=100,
            source="agent_proposal",
        )
        proposals.create(
            CreateDiaryEntriesProposal(id="proposal_1", person_id="person_1", entries=(entry,))
        )

        applied = proposals.confirm_and_apply("proposal_1")

        self.assertEqual(applied.status, "applied")
        self.assertIsNotNone(applied.confirmed_at)
        self.assertIsNone(applied.rejected_at)
        self.assertEqual(len(diary.entries_for_day("person_1", datetime(2026, 7, 1).date())), 1)

    def test_applied_proposal_cannot_be_confirmed_or_rejected_again(self) -> None:
        diary, proposals = self.make_services()
        entry = DiaryEntry(
            id="entry_proposed",
            person_id="person_1",
            logged_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
            meal_type="breakfast",
            food_version_id="egg_large",
            quantity_g=100,
            source="agent_proposal",
        )
        proposals.create(
            CreateDiaryEntriesProposal(id="proposal_1", person_id="person_1", entries=(entry,))
        )

        applied = proposals.confirm_and_apply("proposal_1")

        with self.assertRaisesRegex(ValueError, "already applied"):
            proposals.confirm_and_apply("proposal_1")
        with self.assertRaisesRegex(ValueError, "cannot reject applied proposal"):
            proposals.reject("proposal_1")
        self.assertEqual(proposals.proposals["proposal_1"], applied)
        self.assertEqual(len(diary.entries_for_day("person_1", datetime(2026, 7, 1).date())), 1)


if __name__ == "__main__":
    unittest.main()
