from __future__ import annotations

import unittest

from health_monitor.lookup.foods import OpenFoodFactsLookupProvider


class FixtureOpenFoodFactsProvider(OpenFoodFactsLookupProvider):
    def __init__(self) -> None:
        super().__init__(base_url="https://world.openfoodfacts.test")
        self.last_url = ""

    def _get_json(self, url: str) -> dict[str, object] | None:
        self.last_url = url
        if "/api/v2/product/7891000000000.json" in url:
            return {
                "status": 1,
                "product": {
                    "code": "7891000000000",
                    "product_name": "Iogurte Batavo Protein",
                    "brands": "Batavo",
                    "serving_size": "170 g",
                    "nutriments": {
                        "energy-kcal_100g": 70.59,
                        "proteins_100g": 8.82,
                        "carbohydrates_100g": 5.88,
                        "fat_100g": 1.18,
                        "fiber_100g": 0.4,
                        "sodium_100g": 0.08,
                    },
                },
            }
        return {
            "products": [
                {
                    "code": "7892000000000",
                    "product_name": "Queijo Minas Frescal",
                    "brands": "Marca Brasil",
                    "serving_size": "30 g",
                    "nutriments": {
                        "energy-kcal_100g": 264,
                        "proteins_100g": 17,
                        "carbohydrates_100g": 3,
                        "fat_100g": 20,
                        "sodium_100g": 0.42,
                    },
                }
            ]
        }


class OpenFoodFactsLookupProviderTest(unittest.TestCase):
    def test_barcode_fixture_maps_source_metadata_and_nutrients(self) -> None:
        provider = FixtureOpenFoodFactsProvider()

        candidates = provider.lookup(barcode="7891000000000")

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.source_name, "Open Food Facts")
        self.assertEqual(candidate.source_id, "7891000000000")
        self.assertEqual(candidate.source_url, "https://world.openfoodfacts.test/product/7891000000000")
        self.assertEqual(candidate.product_name, "Iogurte Batavo Protein")
        self.assertEqual(candidate.brand, "Batavo")
        self.assertEqual(candidate.serving_size_g, 170)
        self.assertEqual(candidate.nutrients_per_100g.calories_kcal, 70.59)
        self.assertEqual(candidate.nutrients_per_100g.fiber_g, 0.4)
        self.assertEqual(candidate.nutrients_per_100g.sodium_mg, 80)

    def test_phrase_fixture_uses_brazil_biased_search(self) -> None:
        provider = FixtureOpenFoodFactsProvider()

        candidates = provider.lookup(phrase="queijo minas")

        self.assertEqual(candidates[0].product_name, "Queijo Minas Frescal")
        self.assertIn("search_terms=queijo+minas", provider.last_url)
        self.assertIn("countries_tags_en=Brazil", provider.last_url)
        self.assertIn("page_size=5", provider.last_url)


if __name__ == "__main__":
    unittest.main()
