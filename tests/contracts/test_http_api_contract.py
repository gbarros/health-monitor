from __future__ import annotations

import unittest
from datetime import date

from health_monitor.api.http_api import HttpApi as BaseHttpApi
from health_monitor.application.service import HealthMonitorService
from health_monitor.domain.nutrients import Nutrients
from health_monitor.lookup.estimates import NutritionEstimate, StaticFoodEstimator
from health_monitor.lookup.foods import FoodLookupCandidate, StaticFoodLookupProvider
from health_monitor.lookup.labels import LabelTextExtraction, StaticLabelTextExtractor


class HttpApi(BaseHttpApi):
    def _handle(self, method: str, target: str, body: dict[str, object]):
        # These test-only shims keep service-level proposal mechanics covered
        # without making internal tool paths look like public HTTP routes.
        if method == "POST" and target == "/_test/service/structured-meal":
            proposal = self.service.draft_structured_meal_proposal(
                person_id=str(body["person_id"]),
                day=date.fromisoformat(str(body["day"])),
                time_text=str(body["time_text"]) if body.get("time_text") is not None else None,
                meal_type=str(body["meal_type"]) if body.get("meal_type") is not None else None,
                items=body.get("items") if isinstance(body.get("items"), list) else [],
                agent_settings=body.get("agent_settings") if isinstance(body.get("agent_settings"), dict) else None,
                source_text=str(body["source_text"]) if body.get("source_text") is not None else "structured meal draft",
            )
            return BaseHttpApi.handle(self, "GET", f"/api/proposals/{proposal.id}", None)
        if method == "POST" and target == "/_test/service/structured-meal/amend":
            proposal = self.service.amend_structured_meal_proposal(
                proposal_id=str(body["proposal_id"]),
                person_id=str(body["person_id"]),
                add=body.get("add") if isinstance(body.get("add"), list) else (),
                remove=body.get("remove") if isinstance(body.get("remove"), list) else (),
                set_quantity=body.get("set_quantity") if isinstance(body.get("set_quantity"), list) else (),
                agent_settings=body.get("agent_settings") if isinstance(body.get("agent_settings"), dict) else None,
                source_text=str(body["source_text"]) if body.get("source_text") is not None else "structured meal amendment",
            )
            return BaseHttpApi.handle(self, "GET", f"/api/proposals/{proposal.id}", None)
        if method == "POST" and target == "/_test/service/repeat-meal":
            proposal = self.service.repeat_meal(
                person_id=str(body["person_id"]),
                source_day=date.fromisoformat(str(body["source_day"])),
                meal_type=str(body["meal_type"]),
                logged_at_local=str(body["logged_at_local"]),
            )
            return BaseHttpApi.handle(self, "GET", f"/api/proposals/{proposal.id}", None)
        if method == "POST" and target == "/_test/service/label-scan":
            proposal = self.service.propose_label_scan(
                household_id=str(body["household_id"]),
                person_id=str(body["person_id"]),
                table_text=str(body["table_text"]) if body.get("table_text") is not None else None,
                set_as_default=bool(body.get("set_as_default", True)),
                attachment_id=str(body["attachment_id"]) if body.get("attachment_id") is not None else None,
                attachment_ids=body.get("attachment_ids") if isinstance(body.get("attachment_ids"), list) else None,
                barcode=str(body["barcode"]) if body.get("barcode") is not None else None,
                logged_at_local=str(body["logged_at_local"]) if body.get("logged_at_local") is not None else None,
                quantity_g=float(body["quantity_g"]) if body.get("quantity_g") is not None else None,
                meal_type=str(body["meal_type"]) if body.get("meal_type") is not None else None,
            )
            return BaseHttpApi.handle(self, "GET", f"/api/proposals/{proposal.id}", None)
        if method == "POST" and target == "/_test/service/recipe":
            proposal = self.service.propose_recipe(
                household_id=str(body["household_id"]),
                person_id=str(body["person_id"]),
                recipe_text=str(body["recipe_text"]),
                logged_at_local=str(body["logged_at_local"]) if body.get("logged_at_local") is not None else None,
                quantity_g=float(body["quantity_g"]) if body.get("quantity_g") is not None else None,
                meal_type=str(body["meal_type"]) if body.get("meal_type") is not None else None,
            )
            return BaseHttpApi.handle(self, "GET", f"/api/proposals/{proposal.id}", None)
        return super()._handle(method, target, body)


class HttpApiContractTest(unittest.TestCase):
    def ocr_api(self) -> HttpApi:
        return HttpApi(
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

    def test_health_endpoint_reports_api_readiness(self) -> None:
        api = HttpApi(HealthMonitorService())

        response = api.handle("GET", "/api/health", None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.body,
            {
                "status": "ok",
                "service": "health-monitor-api",
            },
        )

    def test_legacy_prompt_builder_endpoints_are_removed_from_http_surface(self) -> None:
        api = BaseHttpApi(HealthMonitorService())

        for path in ("/api/agent/text-meal", "/api/agent/label-scan", "/api/agent/recipe", "/api/diary/repeat"):
            response = api.handle("POST", path, {})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.body["error"]["type"], "NotFound")

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
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-02T12:00:00",
                "food_version_id": version["id"],
                "quantity_g": 100,
                "meal_type": "lunch",
                "source": "manual",
            },
        )
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body
        range_entries = api.handle(
            "GET",
            f"/api/diary/range?person_id={person['id']}&start=2026-07-01&end=2026-07-02",
            None,
        ).body

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.body["meal_type"], "breakfast")
        self.assertEqual(summary["totals"]["calories_kcal"], 120)
        self.assertEqual(summary["totals"]["protein_g"], 15)
        self.assertEqual(summary["meals"]["breakfast"][0]["food_name"], "Iogurte Batavo")
        self.assertEqual(summary["meals"]["breakfast"][0]["evidence_status"], "exact")
        self.assertEqual(summary["meals"]["breakfast"][0]["confidence"], 1.0)
        self.assertEqual([entry["meal_type"] for entry in range_entries], ["breakfast", "lunch"])
        self.assertEqual([entry["quantity_g"] for entry in range_entries], [150, 100])

    def test_manual_diary_log_can_use_serving_count_through_http_contract(self) -> None:
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
                "name": "Ovo",
                "brand": None,
                "version_label": "large egg",
                "source": "reference",
                "nutrients_per_100g": {
                    "calories_kcal": 155,
                    "protein_g": 13,
                    "carbs_g": 1.1,
                    "fat_g": 11,
                },
                "aliases": ["ovo"],
                "serving_size_g": 50,
            },
        ).body

        created = api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T09:00:00",
                "food_version_id": food_response["version"]["id"],
                "serving_count": 2,
                "source": "manual",
            },
        )
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.body["quantity_g"], 100)
        self.assertEqual(summary["totals"]["calories_kcal"], 155)
        self.assertEqual(summary["totals"]["protein_g"], 13)

    def test_manual_diary_serving_count_requires_serving_size_through_http_contract(self) -> None:
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

        created = api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T09:00:00",
                "food_version_id": food_response["version"]["id"],
                "serving_count": 1,
                "source": "manual",
            },
        )

        self.assertEqual(created.status_code, 400)
        self.assertIn("serving_size_g is required", created.body["error"]["message"])

    def test_quick_custom_food_log_through_http_contract(self) -> None:
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

        created = api.handle(
            "POST",
            "/api/diary/custom-food",
            {
                "household_id": household["id"],
                "person_id": person["id"],
                "name": "Pao de queijo caseiro",
                "brand": None,
                "version_label": "quick custom",
                "nutrients_per_100g": {
                    "calories_kcal": 280,
                    "protein_g": 7,
                    "carbs_g": 35,
                    "fat_g": 12,
                    "fiber_g": 3,
                    "sodium_mg": 400,
                },
                "logged_at_local": "2026-07-01T16:00:00",
                "quantity_g": 80,
                "aliases": ["pao de queijo"],
            },
        )
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body
        resolved = api.handle(
            "GET",
            (
                f"/api/foods/resolve?household_id={household['id']}"
                f"&person_id={person['id']}&phrase=pao+de+queijo"
            ),
            None,
        ).body

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.body["food"]["default_version_id"], created.body["version"]["id"])
        self.assertEqual(created.body["entry"]["food_version_id"], created.body["version"]["id"])
        self.assertEqual(created.body["entry"]["meal_type"], "snack")
        self.assertEqual(created.body["entry"]["source"], "manual_quick_custom")
        self.assertEqual(summary["totals"]["calories_kcal"], 224)
        self.assertEqual(summary["totals"]["protein_g"], 5.6)
        self.assertEqual(summary["totals"]["fiber_g"], 2.4)
        self.assertEqual(summary["totals"]["sodium_mg"], 320)
        self.assertEqual(summary["meals"]["snack"][0]["food_name"], "Pao de queijo caseiro")
        self.assertEqual(summary["meals"]["snack"][0]["nutrients"]["fiber_g"], 2.4)
        self.assertEqual(summary["meals"]["snack"][0]["nutrients"]["sodium_mg"], 320)
        self.assertEqual(resolved["food_version_id"], created.body["version"]["id"])

    def test_food_library_list_returns_loggable_default_versions_through_http_contract(self) -> None:
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
        cheese = api.handle(
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
        yogurt = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Iogurte Batavo",
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
                "food_version_id": cheese["version"]["id"],
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
                "food_version_id": yogurt["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        )

        all_foods = api.handle(
            "GET",
            f"/api/foods?household_id={household['id']}&person_id={person['id']}",
            None,
        ).body
        filtered = api.handle(
            "GET",
            f"/api/foods?household_id={household['id']}&person_id={person['id']}&q=iogurte",
            None,
        ).body

        self.assertEqual(all_foods[0]["food"]["name"], "Iogurte Batavo")
        self.assertEqual(all_foods[0]["version"]["id"], yogurt["food"]["default_version_id"])
        self.assertEqual(all_foods[0]["is_default"], True)
        self.assertEqual(all_foods[0]["last_used_at"], "2026-07-02T10:00:00-03:00")
        self.assertEqual(all_foods[1]["version"]["id"], cheese["food"]["default_version_id"])
        self.assertEqual(all_foods[1]["last_used_at"], "2026-07-01T10:00:00-03:00")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["food"]["name"], "Iogurte Batavo")
        self.assertEqual(filtered[0]["version"]["nutrients_per_100g"]["protein_g"], 10)

    def test_food_listing_exposes_aliases_and_active_barcodes_for_client_search(self) -> None:
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
                "name": "Leite Protein",
                "brand": "Piracanjuba",
                "version_label": "zero lactose",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 51,
                    "protein_g": 10,
                    "carbs_g": 4.8,
                    "fat_g": 0,
                },
                "aliases": ["o leite mais proteico"],
                "barcode": "7891000011111",
            },
        ).body

        listed = api.handle(
            "GET",
            f"/api/foods?household_id={household['id']}&person_id={person['id']}",
            None,
        ).body

        self.assertEqual(listed[0]["food"]["id"], food["food"]["id"])
        self.assertEqual(listed[0]["aliases"], ["o leite mais proteico"])
        self.assertEqual(listed[0]["barcodes"], ["7891000011111"])

    def test_food_archive_hides_library_entry_but_keeps_diary_history_through_http_contract(self) -> None:
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
                "name": "Iogurte antigo",
                "brand": "Batavo",
                "version_label": "old label",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 80,
                    "protein_g": 5,
                    "carbs_g": 9,
                    "fat_g": 2,
                },
                "aliases": ["iogurte antigo"],
                "barcode": "7891000000000",
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

        archived = api.handle("POST", f"/api/foods/{food['food']['id']}/archive", None)
        listed = api.handle(
            "GET",
            f"/api/foods?household_id={household['id']}&person_id={person['id']}",
            None,
        ).body
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body
        resolved = api.handle(
            "GET",
            (
                f"/api/foods/resolve?household_id={household['id']}"
                f"&person_id={person['id']}&phrase=iogurte+antigo"
            ),
            None,
        )

        self.assertEqual(archived.status_code, 200)
        self.assertTrue(archived.body["archived"])
        self.assertEqual(listed, [])
        self.assertEqual(summary["meals"]["breakfast"][0]["food_name"], "Iogurte antigo")
        self.assertEqual(summary["totals"]["calories_kcal"], 80)
        self.assertEqual(resolved.status_code, 400)

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
            "/_test/service/structured-meal",
            {
                "person_id": person["id"],
                "day": "2026-07-01",
                "time_text": "10:00",
                "items": [{"phrase": "queijo", "quantity_g": 100}],
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
        self.assertEqual(proposal["summary"], "1 diary entries drafted from structured meal items")
        self.assertEqual(proposal["totals"]["calories_kcal"], 315)
        self.assertEqual(proposal["agent_run"]["settings"]["model_profile"], "ollama-local")
        self.assertEqual(proposal["evidence"][0]["resolution_reason"], "alias_default_version")
        self.assertEqual(proposal["entries"][0]["food_name"], "Queijo Minas")
        self.assertEqual(before["totals"]["calories_kcal"], 0)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(after["totals"]["calories_kcal"], 315)

    def test_legacy_text_meal_job_is_rejected_through_http_contract(self) -> None:
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

        rejected = api.handle(
            "POST",
            "/api/jobs",
            {
                "job_type": "agent_text_meal",
                "payload": {
                    "person_id": person["id"],
                    "logged_at_local": "2026-07-01T10:00:00",
                    "text": "100g queijo",
                    "agent_settings": {"model_profile": "ollama-local"},
                },
            },
        )
        listed = api.handle(
            "GET",
            f"/api/jobs?person_id={person['id']}&status=pending",
            None,
        ).body

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.body["error"]["type"], "ValueError")
        self.assertEqual(listed, [])

    def test_chat_job_points_to_saved_chat_turn_through_http_contract(self) -> None:
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

        queued = api.handle(
            "POST",
            "/api/jobs",
            {
                "job_type": "agent_chat",
                "payload": {
                    "person_id": person["id"],
                    "message": "Why was 2026-07-01 high in calories?",
                    "today": "2026-07-01",
                },
            },
        ).body
        processed = api.handle("POST", f"/api/jobs/{queued['id']}/process", None).body
        history = api.handle(
            "GET",
            f"/api/agent/chat-history?person_id={person['id']}",
            None,
        ).body

        self.assertEqual(processed["status"], "succeeded")
        self.assertEqual(processed["result"]["behavior_label"], "answer_question")
        self.assertEqual(processed["result"]["chat_turn_id"], history[0]["id"])
        self.assertEqual(processed["result"]["run_id"], history[0]["agent_run_id"])
        self.assertEqual(history[0]["user_message"], "Why was 2026-07-01 high in calories?")

    def test_text_meal_can_copy_same_breakfast_as_yesterday_through_http_contract(self) -> None:
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
        cheese = api.handle(
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
        egg = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Ovo",
                "brand": None,
                "version_label": "large egg",
                "source": "reference",
                "nutrients_per_100g": {
                    "calories_kcal": 155,
                    "protein_g": 13,
                    "carbs_g": 1.1,
                    "fat_g": 11,
                },
                "aliases": ["ovo"],
                "serving_size_g": 50,
            },
        ).body
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T09:00:00",
                "food_version_id": cheese["version"]["id"],
                "quantity_g": 50,
                "source": "manual",
                "meal_type": "breakfast",
            },
        )
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T09:05:00",
                "food_version_id": egg["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
                "meal_type": "breakfast",
            },
        )

        proposal = api.handle(
            "POST",
            "/_test/service/repeat-meal",
            {
                "person_id": person["id"],
                "source_day": "2026-07-01",
                "meal_type": "breakfast",
                "logged_at_local": "2026-07-02T09:00:00",
            },
        ).body
        before = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-02",
            None,
        ).body
        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        after = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-02",
            None,
        ).body

        self.assertEqual(proposal["summary"], "2 diary entries copied from breakfast on 2026-07-01")
        self.assertEqual([entry["quantity_g"] for entry in proposal["entries"]], [50, 100])
        self.assertIsNone(proposal["confirmed_at"])
        self.assertIsNone(proposal["rejected_at"])
        self.assertEqual(before["totals"]["calories_kcal"], 0)
        self.assertEqual(applied["status"], "applied")
        self.assertIsNotNone(applied["confirmed_at"])
        self.assertIsNone(applied["rejected_at"])
        self.assertEqual(after["totals"]["calories_kcal"], 312.5)
        self.assertEqual(len(after["meals"]["breakfast"]), 2)

    def test_text_meal_proposal_entry_can_be_edited_through_http_contract(self) -> None:
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
            "/_test/service/structured-meal",
            {
                "person_id": person["id"],
                "day": "2026-07-01",
                "time_text": "10:00",
                "items": [{"phrase": "queijo", "quantity_g": 100}],
                "agent_settings": {"external_lookup": False},
            },
        ).body
        edited = api.handle(
            "PATCH",
            f"/api/proposals/{proposal['id']}/entries/{proposal['entries'][0]['id']}",
            {"quantity_g": 50, "meal_type": "snack"},
        ).body
        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(edited["entries"][0]["quantity_g"], 50)
        self.assertEqual(edited["entries"][0]["meal_type"], "snack")
        self.assertEqual(edited["totals"]["calories_kcal"], 157.5)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(summary["meals"]["snack"][0]["quantity_g"], 50)
        self.assertEqual(summary["totals"]["calories_kcal"], 157.5)

    def test_text_meal_proposal_entry_food_match_can_be_changed_through_http_contract(self) -> None:
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
        regular_food = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Leite integral",
                "brand": None,
                "version_label": "regular",
                "source": "reference",
                "nutrients_per_100g": {
                    "calories_kcal": 61,
                    "protein_g": 3.2,
                    "carbs_g": 4.8,
                    "fat_g": 3.3,
                },
                "aliases": ["leite"],
            },
        ).body
        protein_food = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Leite mais proteico",
                "brand": None,
                "version_label": "extra protein",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 50,
                    "protein_g": 10,
                    "carbs_g": 4,
                    "fat_g": 0.5,
                },
                "aliases": ["leite proteico"],
            },
        ).body
        proposal = api.handle(
            "POST",
            "/_test/service/structured-meal",
            {
                "person_id": person["id"],
                "day": "2026-07-01",
                "time_text": "10:00",
                "items": [{"phrase": "leite", "quantity_g": 100}],
                "agent_settings": {"external_lookup": False},
            },
        ).body

        edited = api.handle(
            "PATCH",
            f"/api/proposals/{proposal['id']}/entries/{proposal['entries'][0]['id']}",
            {"food_version_id": protein_food["version"]["id"]},
        ).body
        api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None)
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(proposal["entries"][0]["food_version_id"], regular_food["version"]["id"])
        self.assertEqual(edited["entries"][0]["food_version_id"], protein_food["version"]["id"])
        self.assertEqual(edited["entries"][0]["food_name"], "Leite mais proteico")
        self.assertEqual(edited["totals"]["protein_g"], 10)
        self.assertEqual(summary["meals"]["breakfast"][0]["food_version_id"], protein_food["version"]["id"])

    def test_proposals_can_be_listed_by_person_and_status_through_http_contract(self) -> None:
        api = HttpApi(HealthMonitorService())
        household = api.handle("POST", "/api/households", {"name": "Casa"}).body
        gabriel = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
            },
        ).body
        partner = api.handle(
            "POST",
            "/api/people",
            {
                "household_id": household["id"],
                "name": "Partner",
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
        first = api.handle(
            "POST",
            "/_test/service/structured-meal",
            {
                "person_id": gabriel["id"],
                "day": "2026-07-01",
                "time_text": "10:00",
                "items": [{"phrase": "queijo", "quantity_g": 100}],
                "agent_settings": {"external_lookup": False},
            },
        ).body
        second = api.handle(
            "POST",
            "/_test/service/structured-meal",
            {
                "person_id": gabriel["id"],
                "day": "2026-07-02",
                "time_text": "10:00",
                "items": [{"phrase": "queijo", "quantity_g": 50}],
                "agent_settings": {"external_lookup": False},
            },
        ).body
        partner_proposal = api.handle(
            "POST",
            "/_test/service/structured-meal",
            {
                "person_id": partner["id"],
                "day": "2026-07-02",
                "time_text": "10:00",
                "items": [{"phrase": "queijo", "quantity_g": 80}],
                "agent_settings": {"external_lookup": False},
            },
        ).body
        api.handle("POST", f"/api/proposals/{first['id']}/confirm", None)

        gabriel_all = api.handle("GET", f"/api/proposals?person_id={gabriel['id']}", None).body
        gabriel_drafts = api.handle(
            "GET",
            f"/api/proposals?person_id={gabriel['id']}&status=draft",
            None,
        ).body
        partner_all = api.handle("GET", f"/api/proposals?person_id={partner['id']}", None).body

        self.assertEqual({proposal["id"] for proposal in gabriel_all}, {first["id"], second["id"]})
        self.assertEqual([proposal["id"] for proposal in gabriel_drafts], [second["id"]])
        self.assertEqual([proposal["id"] for proposal in partner_all], [partner_proposal["id"]])
        self.assertEqual(gabriel_drafts[0]["status"], "draft")
        self.assertIn("created_at", gabriel_drafts[0])

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
            "/_test/service/label-scan",
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
            "/_test/service/label-scan",
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
            "/_test/service/label-scan",
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

    def test_label_scan_updates_existing_food_with_new_default_version_through_http_contract(self) -> None:
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
        old_food = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Iogurte Batavo Protein",
                "brand": "Batavo",
                "version_label": "old label",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 80,
                    "protein_g": 8,
                    "carbs_g": 7,
                    "fat_g": 2,
                },
                "aliases": ["iogurte batavo"],
            },
        ).body
        api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": old_food["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        )
        proposal = api.handle(
            "POST",
            "/_test/service/label-scan",
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
                "set_as_default": True,
            },
        ).body

        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        foods = api.handle(
            "GET",
            f"/api/foods?household_id={household['id']}&person_id={person['id']}",
            None,
        ).body
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(applied["applied_record_ids"][0], old_food["food"]["id"])
        self.assertNotEqual(applied["applied_record_ids"][1], old_food["version"]["id"])
        self.assertEqual(len(foods), 1)
        self.assertEqual(foods[0]["food"]["id"], old_food["food"]["id"])
        self.assertEqual(foods[0]["version"]["id"], applied["applied_record_ids"][1])
        self.assertEqual(foods[0]["version"]["nutrients_per_100g"]["protein_g"], 8.82)
        self.assertEqual(summary["meals"]["breakfast"][0]["food_version_id"], old_food["version"]["id"])
        self.assertEqual(summary["totals"]["calories_kcal"], 80)

    def test_attachment_label_scan_round_trip_through_http_contract(self) -> None:
        api = self.ocr_api()
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
            "/_test/service/label-scan",
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

    def test_label_scan_can_link_multiple_photo_attachments_through_http_contract(self) -> None:
        api = self.ocr_api()
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
        attachments = [
            api.handle(
                "POST",
                "/api/attachments",
                {
                    "household_id": household["id"],
                    "person_id": person["id"],
                    "object_type": "nutrition_label_image",
                    "mime_type": "image/png",
                    "filename": filename,
                    "content_base64": "ZmFrZS1sYWJlbC1pbWFnZQ==",
                    "retention_policy": "keep",
                },
            ).body
            for filename in ("front-label.png", "macro-table.png")
        ]
        proposal = api.handle(
            "POST",
            "/_test/service/label-scan",
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
                "attachment_ids": [attachment["id"] for attachment in attachments],
            },
        ).body

        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body
        food_version_id = applied["applied_record_ids"][1]
        restored = [
            api.handle("GET", f"/api/attachments/{attachment['id']}", None).body
            for attachment in attachments
        ]

        self.assertEqual(proposal["payload"]["attachment_id"], attachments[0]["id"])
        self.assertEqual(proposal["payload"]["attachment_ids"], [item["id"] for item in attachments])
        self.assertEqual(proposal["evidence"][0]["attachment_ids"], [item["id"] for item in attachments])
        self.assertEqual([item["linked_record_id"] for item in restored], [food_version_id, food_version_id])
        self.assertTrue(all(item["linked_record_type"] == "food_version" for item in restored))

    def test_food_version_evidence_attachments_can_be_listed_through_http_contract(self) -> None:
        api = self.ocr_api()
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
            "/_test/service/label-scan",
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
        food_version_id = applied["applied_record_ids"][1]

        listed = api.handle(
            "GET",
            f"/api/attachments?linked_record_type=food_version&linked_record_id={food_version_id}",
            None,
        ).body
        foods = api.handle(
            "GET",
            f"/api/foods?household_id={household['id']}&person_id={person['id']}",
            None,
        ).body
        restored_attachment = api.handle("GET", f"/api/attachments/{attachment['id']}", None).body

        self.assertEqual([item["id"] for item in listed], [attachment["id"]])
        self.assertEqual(listed[0]["linked_record_type"], "food_version")
        self.assertEqual(listed[0]["linked_record_id"], food_version_id)
        self.assertEqual(listed[0]["filename"], "label.png")
        self.assertNotIn("content_base64", listed[0])
        self.assertEqual(foods[0]["attachments"][0]["id"], attachment["id"])
        self.assertEqual(foods[0]["attachments"][0]["filename"], "label.png")
        self.assertNotIn("content_base64", foods[0]["attachments"][0])
        self.assertEqual(restored_attachment["content_base64"], "ZmFrZS1sYWJlbC1pbWFnZQ==")

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
            "/_test/service/label-scan",
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
        self.assertEqual(proposal["payload"]["confidence"], 0.82)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(resolved["reason"], "confirmed_barcode_association")
        foods = api.handle(
            "GET",
            f"/api/foods?household_id={household['id']}&person_id={person['id']}",
            None,
        ).body
        self.assertEqual(foods[0]["version"]["confidence"], 0.82)

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
            "/_test/service/recipe",
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
            "/_test/service/recipe",
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
            "/_test/service/recipe",
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
            "/_test/service/structured-meal",
            {
                "person_id": person["id"],
                "day": "2026-07-01",
                "time_text": "20:00",
                "items": [{"phrase": "kfc double crunch combo", "quantity_g": 300}],
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

    def test_text_meal_uses_external_lookup_before_model_estimate_through_http_contract(self) -> None:
        api = HttpApi(
            HealthMonitorService(
                food_lookup_provider=StaticFoodLookupProvider(
                    [
                        FoodLookupCandidate(
                            source_type="external_database",
                            source_name="Open Food Facts",
                            source_id="kfc-double-crunch-br",
                            product_name="KFC Double Crunch combo",
                            brand="KFC Brasil",
                            barcode=None,
                            nutrients_per_100g=Nutrients(240, 12, 25, 10),
                            serving_size_g=None,
                            confidence=0.76,
                            warnings=("third-party nutrition data",),
                        )
                    ]
                ),
                estimator=StaticFoodEstimator(
                    {
                        "kfc double crunch combo": NutritionEstimate(
                            phrase="kfc double crunch combo",
                            food_name="Model KFC estimate",
                            nutrients_per_100g=Nutrients(300, 9, 30, 16),
                            source="fixture_model_estimate",
                            confidence=0.42,
                            notes="Model fallback should not be used when lookup returns a candidate.",
                        )
                    }
                ),
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
            "/_test/service/structured-meal",
            {
                "person_id": person["id"],
                "day": "2026-07-01",
                "time_text": "20:00",
                "items": [{"phrase": "kfc double crunch combo", "quantity_g": 300}],
                "agent_settings": {"external_lookup": True},
            },
        ).body
        applied = api.handle("POST", f"/api/proposals/{proposal['id']}/confirm", None).body

        self.assertEqual(proposal["totals"]["calories_kcal"], 720)
        self.assertEqual(proposal["payload"]["estimated_food_versions"][0]["source"], "external_lookup")
        self.assertEqual(proposal["payload"]["estimated_food_versions"][0]["source_name"], "Open Food Facts")
        self.assertEqual(proposal["evidence"][0]["source_type"], "external_database")
        self.assertEqual(proposal["evidence"][0]["resolution_reason"], "external_lookup")
        self.assertEqual(
            [
                (call["tool_name"], call["status"])
                for call in proposal["agent_run"]["tool_calls"]
            ],
            [
                ("resolve_food_reference", "failed"),
                ("lookup_external_food", "completed"),
            ],
        )
        self.assertEqual(applied["status"], "applied")

    def test_text_meal_uses_controlled_research_lookup_before_model_estimate_through_http_contract(self) -> None:
        api = HttpApi(
            HealthMonitorService(
                food_lookup_provider=StaticFoodLookupProvider([]),
                research_lookup_provider=StaticFoodLookupProvider(
                    [
                        FoodLookupCandidate(
                            source_type="research_agent",
                            source_name="Controlled research agent",
                            source_id="research-kfc-double-crunch-br",
                            product_name="KFC Double Crunch combo Brazil",
                            brand="KFC Brasil",
                            barcode=None,
                            nutrients_per_100g=Nutrients(245, 12, 26, 10),
                            serving_size_g=None,
                            confidence=0.64,
                            warnings=("restaurant nutrition reference is approximate",),
                            source_url="https://example.test/kfc-double-crunch",
                            research_prompt="Research nutritional references for KFC Double Crunch combo in Brazil.",
                            source_claims=(
                                {
                                    "source": "third-party menu reference",
                                    "claim": "combo is treated as sandwich plus side and drink",
                                },
                            ),
                        )
                    ]
                ),
                estimator=StaticFoodEstimator(
                    {
                        "kfc double crunch combo": NutritionEstimate(
                            phrase="kfc double crunch combo",
                            food_name="Model KFC estimate",
                            nutrients_per_100g=Nutrients(300, 9, 30, 16),
                            source="fixture_model_estimate",
                            confidence=0.42,
                            notes="Model fallback should not be used when research returns a candidate.",
                        )
                    }
                ),
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
            "/_test/service/structured-meal",
            {
                "person_id": person["id"],
                "day": "2026-07-01",
                "time_text": "20:00",
                "items": [{"phrase": "kfc double crunch combo", "quantity_g": 300}],
                "agent_settings": {"external_lookup": True, "research_lookup": True},
            },
        ).body

        self.assertEqual(proposal["totals"]["calories_kcal"], 735)
        self.assertEqual(proposal["payload"]["estimated_food_versions"][0]["source"], "research_lookup")
        self.assertEqual(proposal["payload"]["estimated_food_versions"][0]["source_type"], "research_agent")
        self.assertEqual(
            proposal["payload"]["estimated_food_versions"][0]["research_prompt"],
            "Research nutritional references for KFC Double Crunch combo in Brazil.",
        )
        self.assertEqual(
            proposal["payload"]["estimated_food_versions"][0]["source_claims"][0]["claim"],
            "combo is treated as sandwich plus side and drink",
        )
        self.assertEqual(proposal["evidence"][0]["resolution_reason"], "research_lookup")
        self.assertEqual(
            [
                (call["tool_name"], call["status"])
                for call in proposal["agent_run"]["tool_calls"]
            ],
            [
                ("resolve_food_reference", "failed"),
                ("lookup_external_food", "completed"),
                ("lookup_research_food", "completed"),
            ],
        )

    def test_agent_chat_no_longer_drafts_correction_deterministically_through_http_contract(self) -> None:
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

        response = api.handle(
            "POST",
            "/api/agent/chat",
            {
                "person_id": person["id"],
                "message": "Change queijo on 2026-07-01 to 50g",
                "today": "2026-07-02",
                "agent_settings": {"model_profile": "deterministic-test"},
            },
        )
        summary = api.handle(
            "GET",
            f"/api/diary/day?person_id={person['id']}&day=2026-07-01",
            None,
        ).body

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.body["behavior_label"], "answer_question")
        self.assertIsNone(response.body["proposal_id"])
        self.assertEqual(response.body["proposal"], None)
        self.assertEqual(summary["totals"]["calories_kcal"], 315)

    def test_agent_chat_history_can_be_read_through_http_contract(self) -> None:
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
        entry = api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": food["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        ).body
        response = api.handle(
            "POST",
            "/api/agent/chat",
            {
                "person_id": person["id"],
                "message": "Why was 2026-07-01 high in calories?",
                "today": "2026-07-02",
            },
        ).body

        history = api.handle(
            "GET",
            f"/api/agent/chat-history?person_id={person['id']}",
            None,
        ).body

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["agent_run_id"], response["run_id"])
        self.assertEqual(history[0]["user_message"], "Why was 2026-07-01 high in calories?")
        self.assertEqual(history[0]["assistant_message"], response["message"])
        self.assertEqual(history[0]["behavior_label"], "answer_question")
        self.assertEqual(history[0]["citations"], [])

    def test_agent_chat_stream_returns_sse_events_through_http_contract(self) -> None:
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
            "/api/agent/chat/stream",
            {
                "person_id": person["id"],
                "message": "Pode resumir meu dia?",
                "today": "2026-07-02",
                "agent_settings": {"model_profile": "deterministic-test"},
            },
        )

        self.assertEqual(response.status_code, 200)
        event_iter = iter(response.iter_events())
        first = next(event_iter)
        self.assertEqual(first, {"event": "run_started", "data": {"status": "started"}})
        self.assertEqual(api.service.chat_turns_for_person(person["id"]), ())
        events = (first, *tuple(event_iter))
        self.assertEqual([event["event"] for event in events], ["run_started", "text_delta", "final"])
        self.assertEqual(events[1]["data"]["text"], events[-1]["data"]["message"])
        self.assertEqual(len(api.service.chat_turns_for_person(person["id"])), 1)

    def test_agent_chat_stream_supports_get_sse_route_for_eventsource_clients(self) -> None:
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
            "GET",
            (
                "/api/agent/chat/stream"
                f"?person_id={person['id']}"
                "&message=Pode%20resumir%20meu%20dia%3F"
                "&today=2026-07-02"
                "&model_profile=deterministic-test"
            ),
            None,
        )

        self.assertEqual(response.status_code, 200)
        events = tuple(response.iter_events())
        self.assertEqual([event["event"] for event in events], ["run_started", "text_delta", "final"])
        self.assertEqual(events[0]["data"]["status"], "started")
        self.assertEqual(api.service.chat_turns_for_person(person["id"])[0].user_message, "Pode resumir meu dia?")

    def test_agent_chat_stream_get_requires_person_id(self) -> None:
        api = HttpApi(HealthMonitorService())

        response = api.handle(
            "GET",
            "/api/agent/chat/stream?message=Oi&today=2026-07-02&model_profile=deterministic-test",
            None,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.body["error"]["message"], "stream requires person_id")

    def test_agent_chat_stream_get_requires_message(self) -> None:
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
            "GET",
            f"/api/agent/chat/stream?person_id={person['id']}&today=2026-07-02&model_profile=deterministic-test",
            None,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.body["error"]["message"], "stream requires message")

    def test_onboarding_chat_turns_are_persisted_by_session(self) -> None:
        api = HttpApi(HealthMonitorService(require_model=False))

        response = api.handle(
            "POST",
            "/api/agent/onboarding-chat",
            {
                "session_id": "session-1",
                "message": "Oi, sou Gabriel.",
                "agent_settings": {"agent_runtime": "pydantic-ai", "model_profile": "test"},
            },
        )
        history = api.handle("GET", "/api/agent/onboarding-history?session_id=session-1", None).body

        self.assertEqual(response.status_code, 201)
        self.assertEqual(history[0]["user_message"], "Oi, sou Gabriel.")
        self.assertEqual(history[0]["assistant_message"], response.body["assistant_message"])

    def test_onboarding_refuses_when_required_model_is_unavailable(self) -> None:
        api = HttpApi(
            HealthMonitorService(
                require_model=True,
                model_health_checker=lambda: False,
            )
        )

        response = api.handle(
            "POST",
            "/api/agent/onboarding-chat",
            {
                "session_id": "session-1",
                "message": "Oi, sou Gabriel.",
                "agent_settings": {"agent_runtime": "pydantic-ai", "model_profile": "test"},
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.body["error"]["type"], "model_unavailable")

    def test_onboarding_profile_setup_proposal_applies_household_person_and_goal(self) -> None:
        api = HttpApi(HealthMonitorService())

        api.handle(
            "POST",
            "/api/agent/onboarding-chat",
            {
                "session_id": "session-1",
                "message": "Oi, sou Gabriel.",
            },
        )
        api.handle(
            "POST",
            "/api/agent/onboarding-chat",
            {
                "session_id": "session-1",
                "message": "Quero começar com 2000 kcal e 150g de proteína.",
            },
        )
        proposal = api.service.draft_onboarding_proposal(
            session_id="session-1",
            household_name="Casa",
            household_id=None,
            person={
                "name": "Gabriel",
                "timezone": "America/Sao_Paulo",
                "activity_level": "moderate",
            },
            targets={
                "calories_kcal": 2000,
                "protein_g": 150,
                "carbs_g": 180,
                "fat_g": 70,
                "fiber_g": 30,
                "sodium_mg": 2300,
            },
            notes="Setup inicial",
            source_text="conversa livre",
        )
        applied = api.handle("POST", f"/api/proposals/{proposal.id}/confirm", None).body
        people = api.handle(
            "GET",
            f"/api/people?household_id={applied['payload']['created_household_id']}",
            None,
        ).body
        goal = api.handle(
            "GET",
            (
                f"/api/goals/active?person_id={applied['payload']['created_person_id']}"
                f"&day={proposal.payload['starts_on']}"
            ),
            None,
        ).body

        self.assertEqual(proposal.proposal_type, "profile_setup")
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["person_id"], applied["payload"]["created_person_id"])
        self.assertEqual(people[0]["name"], "Gabriel")
        self.assertEqual(proposal.payload["starts_on"], goal["starts_on"])
        self.assertEqual(goal["targets"]["calories_kcal"], 2000)
        self.assertEqual(len(applied["payload"]["migrated_onboarding_turn_ids"]), 2)
        migrated_turns = api.service.chat_turns_for_person(applied["payload"]["created_person_id"])
        self.assertEqual([turn.user_message for turn in migrated_turns], [
            "Oi, sou Gabriel.",
            "Quero começar com 2000 kcal e 150g de proteína.",
        ])
        self.assertEqual([turn.behavior_label for turn in migrated_turns], ["onboarding", "onboarding"])

    def test_agent_chat_review_note_text_does_not_create_proposal_without_model_tool_call(self) -> None:
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
        )
        empty_notes = api.handle(
            "GET",
            f"/api/review-notes?person_id={person['id']}",
            None,
        ).body

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.body["behavior_label"], "answer_question")
        self.assertIsNone(response.body["proposal_id"])
        self.assertEqual(empty_notes, [])

    def test_agent_chat_food_version_usage_answer_through_http_contract(self) -> None:
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
        old_food = api.handle(
            "POST",
            "/api/foods",
            {
                "household_id": household["id"],
                "name": "Iogurte Batavo Protein",
                "brand": "Batavo",
                "version_label": "old label",
                "source": "label_scan",
                "nutrients_per_100g": {
                    "calories_kcal": 80,
                    "protein_g": 8,
                    "carbs_g": 7,
                    "fat_g": 2,
                },
                "aliases": ["iogurte batavo"],
            },
        ).body
        old_entry = api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-01T10:00:00",
                "food_version_id": old_food["version"]["id"],
                "quantity_g": 100,
                "source": "manual",
            },
        ).body
        label = api.handle(
            "POST",
            "/_test/service/label-scan",
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
                "set_as_default": True,
            },
        ).body
        applied = api.handle("POST", f"/api/proposals/{label['id']}/confirm", None).body
        new_entry = api.handle(
            "POST",
            "/api/diary",
            {
                "person_id": person["id"],
                "logged_at_local": "2026-07-02T10:00:00",
                "food_version_id": applied["applied_record_ids"][1],
                "quantity_g": 170,
                "source": "manual",
            },
        ).body

        response = api.handle(
            "POST",
            "/api/agent/chat",
            {
                "person_id": person["id"],
                "message": "Did we start using the new Iogurte Batavo label?",
                "today": "2026-07-03",
            },
        ).body

        self.assertEqual(response["behavior_label"], "answer_question")
        self.assertIsNone(response["proposal_id"])
        self.assertEqual(response["citations"], [])

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

        self.assertEqual(response["behavior_label"], "answer_question")
        self.assertIsNone(response["proposal_id"])
        self.assertEqual(response["citations"], [])

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

        self.assertEqual(response["behavior_label"], "answer_question")
        self.assertIsNone(response["proposal_id"])
        self.assertEqual(response["citations"], [])

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
