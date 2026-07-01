from __future__ import annotations

import unittest

from health_monitor.api.http_api import HttpApi
from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.lookup.estimates import NutritionEstimate, StaticFoodEstimator
from health_monitor.lookup.foods import FoodLookupCandidate, StaticFoodLookupProvider
from health_monitor.lookup.labels import LabelTextExtraction, StaticLabelTextExtractor


class HttpApiContractTest(unittest.TestCase):
    def test_daily_driver_flow_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())

        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        food_response = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Iogurte Batavo",
                "brand": "Batavo",
                "version_label": "Protein label",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 80,
                    "protein_g": 10,
                    "carbs_g": 7,
                    "fat_g": 1,
                },
                "aliases": ["iogurte batavo"],
                "barcode": "7891000000000",
            },
        ).body
        version = food_response["version"]

        created = api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": version["id"],
                "quantity_g": 150,
                "source": "manual",
            },
        )
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.body["meal_type"], "breakfast")
        self.assertEqual(summary["totals"]["calories_kcal"], 120)
        self.assertEqual(summary["totals"]["protein_g"], 15)
        self.assertEqual(summary["meals"]["breakfast"][0]["food_name"], "Iogurte Batavo")

    def test_food_resolve_prefers_recently_logged_alias_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        natural = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Iogurte Natural",
                "brand": "Batavo",
                "version_label": "natural label",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 80,
                    "protein_g": 5,
                    "carbs_g": 9,
                    "fat_g": 2,
                },
                "aliases": ["iogurte"],
            },
        ).body
        protein = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Iogurte Protein",
                "brand": "Batavo",
                "version_label": "protein label",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 70,
                    "protein_g": 10,
                    "carbs_g": 6,
                    "fat_g": 1,
                },
                "aliases": ["iogurte"],
            },
        ).body
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": natural["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        )
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-03T10:00:00",
                "food_version_id": protein["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        )

        resolved = api.handle(
            "GET",
            (
                f"/api/foods/resolve?household_id={household['id']}"
                f"&person_id={person['id']}&phrase=iogurte"
            ),
            None,
        ).body

        self.assertEqual(resolved["food_version_id"], protein["version"]["id"])
        self.assertEqual(resolved["reason"], "alias_recently_logged_version")

    def test_people_and_goal_targets_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        gabriel = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
                "birth_date": "1990-05-04",
                "sex": "male",
                "height_cm": 180,
                "activity_level": "moderate",
            },
        ).body
        partner = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Partner",
                "timezone": "America/Sao_Paulo",
                "birth_date": "1992-08-10",
                "sex": "female",
                "height_cm": 165,
                "activity_level": "light",
            },
        ).body
        target = api.handle(
            "POST",
            "/api/goals",
            {
                "person_id": gabriel["id"],
                "starts_on": "2026-07-01",
                "targets": {
                    "calories_kcal": 2000,
                    "protein_g": 150,
                    "carbs_g": 180,
                    "fat_g": 70,
                },
                "notes": "initial plan",
            },
        ).body

        people = api.handle("GET", f"/api/people?household_id={household['id']}", None).body
        active_target = api.handle(
            "GET",
            f"/api/goals/active?person_id={gabriel['id']}&day=2026-07-01",
            None,
        ).body
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={gabriel['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual([person["name"] for person in people], ["Gabriel", "Partner"])
        self.assertEqual(partner["height_cm"], 165)
        self.assertEqual(target["targets"]["protein_g"], 150)
        self.assertEqual(active_target["id"], target["id"])
        self.assertEqual(summary["target"]["calories_kcal"], 2000)
        self.assertEqual(summary["target_delta"]["calories_kcal"], -2000)

    def test_text_meal_proposal_round_trip_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Queijo Minas",
                "brand": None,
                "version_label": "current",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
        )

        proposal = api.handle(
            "POST",
            "/api/agent/text-meal",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "text": "100g queijo",
                "agent_settings": {
                    "model_profile": "ollama-local",
                    "effort": "medium",
                    "max_tool_loops": 4,
                },
            },
        ).body
        before = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body
        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        after = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(proposal["status"], "draft")
        self.assertEqual(proposal["summary"], "1 diary entries drafted from text meal")
        self.assertEqual(proposal["totals"]["calories_kcal"], 315)
        self.assertEqual(proposal["agent_run"]["settings"]["model_profile"], "ollama-local")
        self.assertEqual(proposal["evidence"][0]["resolution_reason"], "alias_default_version")
        self.assertEqual(proposal["entries"][0]["food_name"], "Queijo Minas")
        self.assertEqual(before["totals"]["calories_kcal"], 0)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(after["totals"]["calories_kcal"], 315)

    def test_text_meal_unsupported_unit_returns_clarification_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Queijo Minas",
                "brand": None,
                "version_label": "current",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
        )

        proposal = api.handle(
            "POST",
            "/api/agent/text-meal",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "text": "10am, 1 fatia queijo",
                "agent_settings": {"external_lookup": False},
            },
        ).body
        rejected_apply = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None)
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(proposal["status"], "needs_clarification")
        self.assertEqual(proposal["entries"], [])
        self.assertEqual(proposal["payload"]["missing_fields"], ["quantity_g"])
        self.assertEqual(proposal["payload"]["unresolved_items"][0]["unit"], "fatia")
        self.assertEqual(rejected_apply.status_code, 400)
        self.assertIn("needs clarification", rejected_apply.body["error"]["message"])
        self.assertEqual(summary["totals"]["calories_kcal"], 0)

    def test_diary_entry_correction_round_trip_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        food_response = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Queijo Minas",
                "brand": None,
                "version_label": "current",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
        ).body
        entry = api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": food_response["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        ).body

        updated = api.handle(
            "PATCH",
            f"/api/diary/{entry['id']}",
            {"quantity_g": 50, "meal_type": "snack"},
        ).body
        deleted = api.handle("DELETE", f"/api/diary/{entry['id']}", None).body
        after_delete = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body
        restored = api.handle("POST", f"/api/diary/{entry['id']}/restore", None).body
        after_restore = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(updated["quantity_g"], 50)
        self.assertEqual(updated["meal_type"], "snack")
        self.assertIsNotNone(deleted["deleted_at"])
        self.assertEqual(after_delete["totals"]["calories_kcal"], 0)
        self.assertIsNone(restored["deleted_at"])
        self.assertEqual(after_restore["totals"]["calories_kcal"], 157.5)

    def test_errors_are_json_contracts(self) -> None:
        api = HttpApi(HealthMonitorService())

        response = api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": "missing",
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": "missing",
                "quantity_g": 100,
                "source": "manual",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.body["error"]["type"], "ValueError")

    def test_label_scan_proposal_round_trip_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        proposal = api.handle(
            "POST",
            "/api/agent/label-scan",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "table_text": "\n".join(
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
                ),
                "set_as_default": True,
            },
        ).body

        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        resolved = api.handle(
            "GET",
            (
                f"/api/foods/resolve?household_id={household['id']}"
                f"&person_id={person['id']}&barcode=7891000000000"
            ),
            None,
        ).body

        self.assertEqual(proposal["proposal_type"], "food_version_from_label")
        self.assertEqual(proposal["payload"]["food_name"], "Iogurte Batavo Protein")
        self.assertEqual(proposal["payload"]["nutrients_per_100g"]["protein_g"], 8.82)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(resolved["reason"], "confirmed_barcode_association")

    def test_label_scan_accepts_separate_barcode_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        proposal = api.handle(
            "POST",
            "/api/agent/label-scan",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "table_text": "\n".join(
                    [
                        "Produto: Iogurte Batavo Protein",
                        "Marca: Batavo",
                        "Porcao: 170 g",
                        "Valor energetico: 120 kcal",
                        "Proteinas: 15 g",
                        "Carboidratos: 10 g",
                        "Gorduras totais: 2 g",
                    ]
                ),
                "barcode": "7891000000000",
                "set_as_default": True,
            },
        ).body

        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        resolved = api.handle(
            "GET",
            (
                f"/api/foods/resolve?household_id={household['id']}"
                f"&person_id={person['id']}&barcode=7891000000000"
            ),
            None,
        ).body

        self.assertEqual(proposal["payload"]["barcode"], "7891000000000")
        self.assertEqual(applied["applied_record_ids"][1], resolved["food_version_id"])

    def test_label_scan_can_log_portion_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        proposal = api.handle(
            "POST",
            "/api/agent/label-scan",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "table_text": "\n".join(
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
                ),
                "logged_at_local": "2026-07-01T10:00:00",
                "quantity_g": 170,
                "set_as_default": True,
            },
        ).body
        before = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body
        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        after = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(proposal["entries"][0]["quantity_g"], 170)
        self.assertEqual(proposal["entries"][0]["food_name"], "Iogurte Batavo Protein")
        self.assertEqual(before["totals"]["calories_kcal"], 0)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(after["totals"]["calories_kcal"], 120)
        self.assertEqual(after["meals"]["breakfast"][0]["food_version_id"], applied["applied_record_ids"][1])

    def test_attachment_label_scan_round_trip_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        attachment = api.handle(
            "POST",
            "/api/attachments",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "object_type": "nutrition_label_image",
                "mime_type": "image/png",
                "filename": "label.png",
                "content_base64": "ZmFrZS1sYWJlbC1pbWFnZQ==",
                "retention_policy": "keep",
            },
        ).body
        proposal = api.handle(
            "POST",
            "/api/agent/label-scan",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "table_text": "\n".join(
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
                ),
                "attachment_id": attachment["id"],
            },
        ).body

        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        restored_attachment = api.handle("GET", f"/api/attachments/{attachment['id']}", None).body

        self.assertEqual(attachment["byte_size"], 16)
        self.assertEqual(proposal["evidence"][0]["attachment_id"], attachment["id"])
        self.assertEqual(restored_attachment["linked_record_type"], "food_version")
        self.assertEqual(restored_attachment["linked_record_id"], applied["applied_record_ids"][1])

    def test_image_only_label_scan_uses_extractor_through_http_contract(self) -> None:
        api = HttpApi(
            HealthMonitorService(
                label_text_extractor=StaticLabelTextExtractor(
                    LabelTextExtraction(
                        text="\n".join(
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
                        ),
                        source="static_ocr",
                        confidence=0.9,
                    )
                )
            )
        )
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        attachment = api.handle(
            "POST",
            "/api/attachments",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "object_type": "nutrition_label_image",
                "mime_type": "image/png",
                "filename": "label.png",
                "content_base64": "ZmFrZS1sYWJlbC1pbWFnZQ==",
            },
        ).body

        proposal = api.handle(
            "POST",
            "/api/agent/label-scan",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "table_text": "",
                "attachment_id": attachment["id"],
            },
        ).body

        self.assertEqual(proposal["proposal_type"], "food_version_from_label")
        self.assertEqual(proposal["payload"]["ocr_source"], "static_ocr")
        self.assertEqual(proposal["payload"]["food_name"], "Iogurte Batavo Protein")

    def test_food_lookup_candidate_proposal_through_http_contract(self) -> None:
        api = HttpApi(
            HealthMonitorService(
                food_lookup_provider=StaticFoodLookupProvider(
                    [
                        FoodLookupCandidate(
                            source_type="external_database",
                            source_name="Open Food Facts",
                            source_id="7891000000000",
                            product_name="Iogurte Batavo Protein",
                            brand="Batavo",
                            barcode="7891000000000",
                            nutrients_per_100g=Nutrients(70.59, 8.82, 5.88, 1.18),
                            serving_size_g=170,
                            confidence=0.82,
                            warnings=("user-contributed data",),
                        )
                    ]
                )
            )
        )
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        candidates = api.handle(
            "GET",
            (
                f"/api/lookups/foods?household_id={household['id']}"
                f"&person_id={person['id']}&barcode=7891000000000"
            ),
            None,
        ).body
        proposal = api.handle(
            "POST",
            "/api/lookups/foods/propose",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "candidate_id": candidates[0]["id"],
            },
        ).body
        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        resolved = api.handle(
            "GET",
            (
                f"/api/foods/resolve?household_id={household['id']}"
                f"&person_id={person['id']}&barcode=7891000000000"
            ),
            None,
        ).body

        self.assertEqual(candidates[0]["source_name"], "Open Food Facts")
        self.assertEqual(candidates[0]["warnings"], ["user-contributed data"])
        self.assertEqual(proposal["proposal_type"], "food_version_from_lookup")
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(resolved["reason"], "confirmed_barcode_association")

    def test_recipe_proposal_round_trip_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        for food in (
            {
                "name": "Queijo Minas",
                "version_label": "current",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
            {
                "name": "Banana",
                "version_label": "generic",
                "nutrients_per_100g": {
                    "calories_kcal": 89,
                    "protein_g": 1.1,
                    "carbs_g": 22.8,
                    "fat_g": 0.3,
                },
                "aliases": ["banana"],
            },
        ):
            api.handle(
                "POST",
                "/api/foods",
                {
                    "household_id": household["id"],
                    "brand": None,
                    "source": "reference",
                    **food,
                },
            )

        proposal = api.handle(
            "POST",
            "/api/agent/recipe",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "recipe_text": "\n".join(
                    [
                        "Recipe: Batch breakfast mix",
                        "Yield: 1000 g",
                        "Ingredients:",
                        "500g queijo",
                        "500g banana",
                    ]
                ),
            },
        ).body

        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        resolved = api.handle(
            "GET",
            (
                f"/api/foods/resolve?household_id={household['id']}"
                f"&person_id={person['id']}&phrase=batch+breakfast+mix"
            ),
            None,
        ).body

        self.assertEqual(proposal["proposal_type"], "recipe_food_version")
        self.assertEqual(proposal["payload"]["nutrients_per_100g"]["protein_g"], 12.05)
        self.assertEqual(len(proposal["payload"]["ingredients"]), 2)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(resolved["food_version_id"], applied["applied_record_ids"][1])

    def test_recipe_can_log_portion_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Queijo Minas",
                "brand": None,
                "version_label": "current",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
        )
        api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Banana",
                "brand": None,
                "version_label": "generic",
                "source": "reference",
                "nutrients_per_100g": {
                    "calories_kcal": 89,
                    "protein_g": 1.1,
                    "carbs_g": 22.8,
                    "fat_g": 0.3,
                },
                "aliases": ["banana"],
            },
        )
        proposal = api.handle(
            "POST",
            "/api/agent/recipe",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "recipe_text": "\n".join(
                    [
                        "Recipe: Batch breakfast mix",
                        "Yield: 1000 g",
                        "Ingredients:",
                        "500g queijo",
                        "500g banana",
                    ]
                ),
                "logged_at_local": "2026-07-01T12:30:00",
                "quantity_g": 100,
            },
        ).body
        before = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body
        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        after = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(proposal["entries"][0]["food_name"], "Batch breakfast mix")
        self.assertEqual(proposal["entries"][0]["meal_type"], "lunch")
        self.assertEqual(before["totals"]["calories_kcal"], 0)
        self.assertEqual(after["totals"]["calories_kcal"], 202)
        self.assertEqual(after["meals"]["lunch"][0]["food_version_id"], applied["applied_record_ids"][1])

    def test_recipe_missing_yield_draft_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "brand": None,
                "source": "reference",
                "name": "Queijo Minas",
                "version_label": "current",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
        )

        proposal = api.handle(
            "POST",
            "/api/agent/recipe",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "recipe_text": "Recipe: No yield\nIngredients:\n500g queijo",
            },
        ).body
        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body

        self.assertEqual(proposal["proposal_type"], "recipe_draft")
        self.assertEqual(proposal["payload"]["precise_logging_enabled"], False)
        self.assertEqual(proposal["payload"]["missing_fields"], ["yield_g"])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["applied_record_ids"], [])

    def test_unknown_food_estimate_round_trip_through_http_contract(self) -> None:
        api = HttpApi(
            HealthMonitorService(
                estimator=StaticFoodEstimator(
                    {
                        "kfc double crunch combo": NutritionEstimate(
                            phrase="kfc double crunch combo",
                            food_name="KFC Double Crunch combo",
                            nutrients_per_100g=Nutrients(260, 11, 24, 13),
                            source="fixture_model_estimate",
                            confidence=0.42,
                            notes="Fixture estimate for a regional restaurant meal.",
                        )
                    }
                )
            )
        )
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        proposal = api.handle(
            "POST",
            "/api/agent/text-meal",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T20:00:00",
                "text": "300g KFC Double Crunch combo",
                "agent_settings": {"external_lookup": True},
            },
        ).body

        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        resolved = api.handle(
            "GET",
            (
                f"/api/foods/resolve?household_id={household['id']}"
                f"&person_id={person['id']}&phrase=kfc+double+crunch+combo"
            ),
            None,
        ).body

        self.assertEqual(proposal["proposal_type"], "diary_entries_with_estimates")
        self.assertEqual(proposal["totals"]["calories_kcal"], 780)
        self.assertEqual(proposal["evidence"][0]["source_type"], "model_estimate")
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(len(applied["applied_record_ids"]), 3)
        self.assertEqual(resolved["food_version_id"], proposal["entries"][0]["food_version_id"])

    def test_agent_chat_answer_and_correction_proposal_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        food = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Queijo Minas",
                "brand": None,
                "version_label": "current",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
        ).body
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": food["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        )

        answer = api.handle(
            "POST",
            "/api/agent/chat",
            {
                "person_id": person["id"],
                "message": "Why was 2026-07-01 high in calories?",
                "today": "2026-07-02",
                "agent_settings": {"model_profile": "deterministic-test"},
            },
        ).body
        correction = api.handle(
            "POST",
            "/api/agent/chat",
            {
                "person_id": person["id"],
                "message": "Change queijo on 2026-07-01 to 50g",
                "today": "2026-07-02",
            },
        ).body
        applied = api.handle(
            "POST",
            f"/api/proposals/{correction['proposal']['id']}/confirm",
            None,
        ).body
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(answer["behavior_label"], "explain_day")
        self.assertIn("Queijo Minas", answer["message"])
        self.assertEqual(correction["behavior_label"], "draft_diary_correction")
        self.assertEqual(correction["proposal"]["proposal_type"], "diary_entry_update")
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(summary["totals"]["calories_kcal"], 157.5)

    def test_agent_chat_review_note_proposal_and_read_model_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body

        response = api.handle(
            "POST",
            "/api/agent/chat",
            {
                "person_id": person["id"],
                "message": (
                    "Save review note for 2026-07-01 to 2026-07-07: "
                    "Social dinners made adherence harder."
                ),
                "today": "2026-07-08",
            },
        ).body
        empty_notes = api.handle(
            "GET",
            f"/api/review-notes?person_id={person['id']}",
            None,
        ).body
        applied = api.handle(
            "POST",
            f"/api/proposals/{response['proposal']['id']}/confirm",
            None,
        ).body
        notes = api.handle(
            "GET",
            f"/api/review-notes?person_id={person['id']}",
            None,
        ).body

        self.assertEqual(response["behavior_label"], "draft_review_note")
        self.assertEqual(response["proposal"]["proposal_type"], "review_note")
        self.assertEqual(empty_notes, [])
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["starts_on"], "2026-07-01")
        self.assertIn("Social dinners", notes[0]["body"])

    def test_agent_chat_week_explanation_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        food = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Queijo Minas",
                "brand": None,
                "version_label": "current",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
        ).body
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": food["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        )
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-02T10:00:00",
                "food_version_id": food["version"]["id"],
                "quantity_g": 50,
                "source": "manual",
            },
        )

        response = api.handle(
            "POST",
            "/api/agent/chat",
            {
                "person_id": person["id"],
                "message": "Explain the week 2026-07-01 to 2026-07-07",
                "today": "2026-07-08",
            },
        ).body

        self.assertEqual(response["behavior_label"], "explain_week")
        self.assertIn("472.5 kcal", response["message"])
        self.assertGreaterEqual(len(response["citations"]), 2)

    def test_agent_chat_micronutrient_side_quest_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        food = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Queijo Minas",
                "brand": None,
                "version_label": "current",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                    "fiber_g": 0,
                    "sodium_mg": 0,
                },
                "aliases": ["queijo"],
            },
        ).body
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": food["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        )

        response = api.handle(
            "POST",
            "/api/agent/chat",
            {
                "person_id": person["id"],
                "message": "What micronutrients look consistently low this week?",
                "today": "2026-07-02",
            },
        ).body

        self.assertEqual(response["behavior_label"], "micronutrient_analysis")
        self.assertIn("vitamins and minerals are not stored", response["message"].casefold())
        self.assertGreaterEqual(len(response["citations"]), 1)

    def test_weight_trend_and_week_summary_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        food_response = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Queijo Minas",
                "brand": None,
                "version_label": "current",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
        ).body
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": food_response["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        )
        api.handle(
            "POST",
            "/api/weights",
            {
                "person_id": person["id"],
                "measured_at_local": "2026-07-01T08:00:00",
                "weight_kg": 91.2,
                "note": "start",
                "source": "manual",
            },
        )
        api.handle(
            "POST",
            "/api/weights",
            {
                "person_id": person["id"],
                "measured_at_local": "2026-07-07T08:00:00",
                "weight_kg": 90.4,
                "note": "week end",
                "source": "manual",
            },
        )

        trend = api.handle("GET", f"/api/weights/trend?person_id={person['id']}", None).body
        week = api.handle(
            "GET",
            f"/api/summaries/week?person_id={person['id']}&start=2026-07-01&end=2026-07-07",
            None,
        ).body

        self.assertEqual(trend["delta_kg"], -0.8)
        self.assertEqual(len(trend["entries"]), 2)
        self.assertEqual(week["totals"]["calories_kcal"], 315)
        self.assertEqual(week["averages"]["calories_kcal"], 45)
        self.assertEqual(week["weight_delta_kg"], -0.8)

    def test_weight_entry_edit_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        person = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        first = api.handle(
            "POST",
            "/api/weights",
            {
                "person_id": person["id"],
                "measured_at_local": "2026-07-01T08:00:00",
                "weight_kg": 91.2,
                "note": "start",
                "source": "manual",
            },
        ).body
        api.handle(
            "POST",
            "/api/weights",
            {
                "person_id": person["id"],
                "measured_at_local": "2026-07-07T08:00:00",
                "weight_kg": 90.4,
                "note": "week end",
                "source": "manual",
            },
        )

        updated = api.handle(
            "PATCH",
            f"/api/weights/{first['id']}",
            {
                "measured_at_local": "2026-07-01T07:30:00",
                "weight_kg": 91.0,
                "note": "corrected start",
            },
        ).body
        trend = api.handle("GET", f"/api/weights/trend?person_id={person['id']}", None).body

        self.assertEqual(updated["weight_kg"], 91.0)
        self.assertEqual(updated["note"], "corrected start")
        self.assertEqual(trend["delta_kg"], -0.6)

    def test_export_and_import_round_trip_through_http_contract(self) -> None:
        source = HttpApi(HealthMonitorService())
        household = source.handle("POST", "/api/households", {"name": "Casa"}).body
        person = source.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        food = source.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Queijo Minas",
                "brand": None,
                "version_label": "current",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 315,
                    "protein_g": 23,
                    "carbs_g": 2.6,
                    "fat_g": 23.5,
                },
                "aliases": ["queijo"],
            },
        ).body
        source.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": food["version"]["id"],
                "quantity_g": 50,
                "source": "manual",
            },
        )

        exported = source.handle("GET", "/api/exports/full", None).body
        target = HttpApi(HealthMonitorService())
        imported = target.handle("POST", "/api/imports/full", exported).body
        summary = target.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(exported["format"], "health-monitor.snapshot")
        self.assertEqual(imported["imported"]["diary_entries"], 1)
        self.assertEqual(summary["totals"]["calories_kcal"], 157.5)


if __name__ == "__main__":
    unittest.main()
