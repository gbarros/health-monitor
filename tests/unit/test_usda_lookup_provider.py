from __future__ import annotations

import unittest

from health_monitor.lookup.foods import USDAFoodDataCentralLookupProvider


class FixtureUSDAProvider(USDAFoodDataCentralLookupProvider):
    def _get_json(self, url: str) -> dict[str, object] | None:
        self.last_url = url
        return {
            "foods": [
                {
                    "fdcId": 12345,
                    "description": "BANANA, RAW",
                    "brandOwner": None,
                    "dataType": "Foundation",
                    "servingSize": 100,
                    "servingSizeUnit": "g",
                    "foodNutrients": [
                        {"nutrientName": "Energy", "unitName": "KCAL", "value": 89},
                        {"nutrientName": "Protein", "unitName": "G", "value": 1.1},
                        {"nutrientName": "Carbohydrate, by difference", "unitName": "G", "value": 22.8},
                        {"nutrientName": "Total lipid (fat)", "unitName": "G", "value": 0.3},
                        {"nutrientName": "Fiber, total dietary", "unitName": "G", "value": 2.6},
                        {"nutrientName": "Sodium, Na", "unitName": "MG", "value": 1},
                    ],
                }
            ]
        }


class USDAFoodDataCentralLookupProviderTest(unittest.TestCase):
    def test_usda_phrase_lookup_maps_nutrients_and_source_metadata(self) -> None:
        provider = FixtureUSDAProvider(api_key="fixture-key")

        candidates = provider.lookup(phrase="banana")

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.source_name, "USDA FoodData Central")
        self.assertEqual(candidate.source_id, "12345")
        self.assertEqual(candidate.product_name, "BANANA, RAW")
        self.assertEqual(candidate.nutrients_per_100g.calories_kcal, 89)
        self.assertEqual(candidate.nutrients_per_100g.fiber_g, 2.6)
        self.assertEqual(candidate.nutrients_per_100g.sodium_mg, 1)
        self.assertIn("api_key=fixture-key", provider.last_url)

    def test_usda_lookup_is_disabled_without_api_key(self) -> None:
        provider = USDAFoodDataCentralLookupProvider(api_key=None)

        self.assertEqual(provider.lookup(phrase="banana"), [])


if __name__ == "__main__":
    unittest.main()
