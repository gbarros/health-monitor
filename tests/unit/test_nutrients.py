from __future__ import annotations

import unittest

from health_monitor.domain.nutrients import Nutrients


class NutrientMathTest(unittest.TestCase):
    def test_scales_and_adds_nutrients_deterministically(self) -> None:
        cheese = Nutrients(calories_kcal=320, protein_g=20, carbs_g=3, fat_g=25)
        eggs = Nutrients(calories_kcal=155, protein_g=13, carbs_g=1.1, fat_g=11)

        total = cheese.scale(0.5) + eggs.scale(1.0)

        self.assertEqual(total.rounded(1), Nutrients(315, 23, 2.6, 23.5))


if __name__ == "__main__":
    unittest.main()

