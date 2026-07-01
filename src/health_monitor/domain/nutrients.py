from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Nutrients:
    calories_kcal: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fiber_g: float = 0
    sodium_mg: float = 0

    def scale(self, factor: float) -> "Nutrients":
        return Nutrients(
            calories_kcal=self.calories_kcal * factor,
            protein_g=self.protein_g * factor,
            carbs_g=self.carbs_g * factor,
            fat_g=self.fat_g * factor,
            fiber_g=self.fiber_g * factor,
            sodium_mg=self.sodium_mg * factor,
        )

    def __add__(self, other: "Nutrients") -> "Nutrients":
        return Nutrients(
            calories_kcal=self.calories_kcal + other.calories_kcal,
            protein_g=self.protein_g + other.protein_g,
            carbs_g=self.carbs_g + other.carbs_g,
            fat_g=self.fat_g + other.fat_g,
            fiber_g=self.fiber_g + other.fiber_g,
            sodium_mg=self.sodium_mg + other.sodium_mg,
        )

    def rounded(self, digits: int = 2) -> "Nutrients":
        return Nutrients(
            calories_kcal=round(self.calories_kcal, digits),
            protein_g=round(self.protein_g, digits),
            carbs_g=round(self.carbs_g, digits),
            fat_g=round(self.fat_g, digits),
            fiber_g=round(self.fiber_g, digits),
            sodium_mg=round(self.sodium_mg, digits),
        )


ZERO_NUTRIENTS = Nutrients()

