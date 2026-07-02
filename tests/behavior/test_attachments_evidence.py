from __future__ import annotations

import unittest

from health_monitor.application.service import HealthMonitorService
from health_monitor.lookup.labels import LabelTextExtraction, StaticLabelTextExtractor


LABEL_TEXT = "\n".join(
    [
        "Produto: Iogurte Batavo Protein",
        "Marca: Batavo",
        "Porcao: 170 g",
        "Valor energetico: 120 kcal",
        "Proteinas: 15 g",
        "Carboidratos: 10 g",
        "Gorduras totais: 2 g",
        "Codigo de barras: 7891000000000",
    ]
)


class AttachmentsEvidenceTest(unittest.TestCase):
    def service_with_ocr(self) -> HealthMonitorService:
        return HealthMonitorService(
            label_text_extractor=StaticLabelTextExtractor(
                LabelTextExtraction(text=LABEL_TEXT, source="static_ocr", confidence=0.91)
            )
        )

    def test_uploaded_attachment_preserves_blob_metadata_and_hash(self) -> None:
        service = self.service_with_ocr()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )

        attachment = service.create_attachment(
            household_id=household.id,
            person_id=person.id,
            object_type="nutrition_label_image",
            mime_type="image/png",
            content=b"fake-label-image",
            filename="label.png",
            retention_policy="keep",
        )

        self.assertEqual(attachment.byte_size, 16)
        self.assertEqual(
            attachment.sha256,
            "1e0b1758b5cb3d72ea79712192876e51ca5b103f1c55b8b77592f18d89c6782f",
        )
        self.assertEqual(attachment.storage_status, "stored")
        self.assertEqual(attachment.linked_record_type, None)

    def test_label_scan_can_link_attachment_to_confirmed_food_version(self) -> None:
        service = self.service_with_ocr()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        attachment = service.create_attachment(
            household_id=household.id,
            person_id=person.id,
            object_type="nutrition_label_image",
            mime_type="image/png",
            content=b"fake-label-image",
            filename="label.png",
            retention_policy="keep",
        )

        proposal = service.propose_label_scan(
            household_id=household.id,
            person_id=person.id,
            table_text=LABEL_TEXT,
            attachment_id=attachment.id,
        )
        applied = service.confirm_proposal(proposal.id)
        linked = service.get_attachment(attachment.id)

        self.assertEqual(proposal.evidence[0]["attachment_id"], attachment.id)
        self.assertEqual(linked.linked_record_type, "food_version")
        self.assertEqual(linked.linked_record_id, applied.applied_record_ids[1])

    def test_food_version_attachment_can_be_listed_after_label_confirmation(self) -> None:
        service = self.service_with_ocr()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        attachment = service.create_attachment(
            household_id=household.id,
            person_id=person.id,
            object_type="nutrition_label_image",
            mime_type="image/png",
            content=b"fake-label-image",
            filename="label.png",
            retention_policy="keep",
        )

        proposal = service.propose_label_scan(
            household_id=household.id,
            person_id=person.id,
            table_text=LABEL_TEXT,
            attachment_id=attachment.id,
        )
        applied = service.confirm_proposal(proposal.id)
        food_version_id = applied.applied_record_ids[1]

        evidence = service.attachments_for_record(
            linked_record_type="food_version",
            linked_record_id=food_version_id,
        )
        restored = service.get_attachment(attachment.id)

        self.assertEqual([item.id for item in evidence], [attachment.id])
        self.assertEqual(evidence[0].linked_record_type, "food_version")
        self.assertEqual(evidence[0].linked_record_id, food_version_id)
        self.assertEqual(restored.content, b"fake-label-image")

    def test_rejected_proposal_keeps_attachment_for_audit_without_linking(self) -> None:
        service = self.service_with_ocr()
        household = service.create_household(name="Casa")
        person = service.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        attachment = service.create_attachment(
            household_id=household.id,
            person_id=person.id,
            object_type="nutrition_label_image",
            mime_type="image/png",
            content=b"fake-label-image",
            filename="label.png",
            retention_policy="keep",
        )
        proposal = service.propose_label_scan(
            household_id=household.id,
            person_id=person.id,
            table_text=LABEL_TEXT,
            attachment_id=attachment.id,
        )

        service.reject_proposal(proposal.id)
        restored = service.get_attachment(attachment.id)

        self.assertEqual(restored.linked_record_type, None)
        self.assertEqual(restored.storage_status, "stored")

    def test_export_import_preserves_attachment_objects(self) -> None:
        first = HealthMonitorService()
        household = first.create_household(name="Casa")
        person = first.create_person(
            household_id=household.id,
            name="Gabriel",
            timezone="America/Sao_Paulo",
        )
        attachment = first.create_attachment(
            household_id=household.id,
            person_id=person.id,
            object_type="nutrition_label_image",
            mime_type="image/png",
            content=b"fake-label-image",
            filename="label.png",
            retention_policy="keep",
        )

        second = HealthMonitorService()
        second.import_data(first.export_data())
        restored = second.get_attachment(attachment.id)

        self.assertEqual(restored.content, b"fake-label-image")
        self.assertEqual(restored.mime_type, "image/png")


if __name__ == "__main__":
    unittest.main()
