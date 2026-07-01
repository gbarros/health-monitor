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


class LabelImageExtractionTest(unittest.TestCase):
    def test_image_only_label_scan_uses_extractor_and_preserves_output(self) -> None:
        service = HealthMonitorService(
            label_text_extractor=StaticLabelTextExtractor(
                LabelTextExtraction(
                    text=LABEL_TEXT,
                    source="static_ocr",
                    confidence=0.91,
                    warnings=("review sodium manually",),
                )
            )
        )
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
        )

        proposal = service.propose_label_scan(
            household_id=household.id,
            person_id=person.id,
            table_text=None,
            attachment_id=attachment.id,
        )

        self.assertEqual(proposal.proposal_type, "food_version_from_label")
        self.assertEqual(proposal.payload["food_name"], "Iogurte Batavo Protein")
        self.assertEqual(proposal.payload["ocr_text"], LABEL_TEXT)
        self.assertEqual(proposal.payload["ocr_source"], "static_ocr")
        self.assertEqual(proposal.payload["ocr_confidence"], 0.91)
        self.assertEqual(proposal.evidence[0]["raw_text"], LABEL_TEXT)
        self.assertEqual(proposal.evidence[0]["ocr_warnings"], ["review sodium manually"])

    def test_image_only_label_scan_requires_extractor_result(self) -> None:
        service = HealthMonitorService(label_text_extractor=StaticLabelTextExtractor(None))
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
        )

        with self.assertRaisesRegex(ValueError, "could not extract nutrition label text"):
            service.propose_label_scan(
                household_id=household.id,
                person_id=person.id,
                table_text="",
                attachment_id=attachment.id,
            )


if __name__ == "__main__":
    unittest.main()
