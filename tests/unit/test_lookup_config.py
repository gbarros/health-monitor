from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from health_monitor.config import AppConfig
from health_monitor.lookup.foods import (
    CompositeFoodLookupProvider,
    OpenFoodFactsLookupProvider,
    USDAFoodDataCentralLookupProvider,
)
from health_monitor.server import build_service


class LookupConfigTest(unittest.TestCase):
    def test_openfoodfacts_and_usda_are_composed_in_source_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = build_service(
                AppConfig(
                    persistence_backend="sqlite",
                    sqlite_path=Path(tmpdir) / "state.sqlite3",
                    food_estimator="none",
                    label_text_extractor="none",
                    openfoodfacts_enabled=True,
                    usda_enabled=True,
                    usda_api_key="fixture-key",
                )
            )

        provider = service.food_lookup_provider
        self.assertIsInstance(provider, CompositeFoodLookupProvider)
        assert isinstance(provider, CompositeFoodLookupProvider)
        self.assertIsInstance(provider.providers[0], OpenFoodFactsLookupProvider)
        self.assertIsInstance(provider.providers[1], USDAFoodDataCentralLookupProvider)

    def test_usda_lookup_can_be_disabled_independently(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = build_service(
                AppConfig(
                    persistence_backend="sqlite",
                    sqlite_path=Path(tmpdir) / "state.sqlite3",
                    food_estimator="none",
                    label_text_extractor="none",
                    openfoodfacts_enabled=False,
                    usda_enabled=False,
                    usda_api_key="fixture-key",
                )
            )

        self.assertIsNone(service.food_lookup_provider)


if __name__ == "__main__":
    unittest.main()
