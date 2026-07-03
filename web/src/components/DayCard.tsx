import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { loadActiveGoal, loadDaySummary, loadWeightTrend } from "../api";
import { queryKeys } from "../queryKeys";
import type { DaySummary, DaySummaryEntry, Nutrients, WeightTrend } from "../types";

type Props = {
  personId: string;
  day: string;
};

const MEAL_LABELS: Record<string, string> = {
  breakfast: "Café",
  lunch: "Almoço",
  snack: "Lanche",
  dinner: "Janta",
  unknown: "Sem refeição",
};

const MEAL_ORDER = ["breakfast", "lunch", "snack", "dinner", "unknown"];

export function DayCard({ personId, day }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  const dayQuery = useQuery({
    queryKey: queryKeys.daySummary(personId, day),
    queryFn: () => loadDaySummary(personId, day),
  });
  const goalQuery = useQuery({
    queryKey: queryKeys.activeGoal(personId, day),
    queryFn: () => loadActiveGoal(personId, day),
  });
  const weightQuery = useQuery({
    queryKey: queryKeys.weightTrend(personId),
    queryFn: () => loadWeightTrend(personId),
  });

  const summary = dayQuery.data;
  const target = summary?.target ?? goalQuery.data?.targets ?? null;
  const remaining = summary?.target_delta ? invertNutrients(summary.target_delta) : null;

  return (
    <section className="day-card" aria-label="Resumo do dia">
      <header className="day-card-header">
        <div>
          <p className="eyebrow">Hoje</p>
          <h2>{formatDay(day)}</h2>
        </div>
        <button
          type="button"
          className="compact-button"
          onClick={() => setCollapsed((value) => !value)}
          aria-expanded={!collapsed}
        >
          {collapsed ? "Abrir" : "Recolher"}
        </button>
      </header>

      {dayQuery.isLoading ? (
        <div className="day-card-skeleton">Carregando diário...</div>
      ) : dayQuery.isError ? (
        <p className="form-error">Não foi possível carregar o dia.</p>
      ) : summary ? (
        <>
          <SummaryStrip summary={summary} target={target} remaining={remaining} />
          {!collapsed ? (
            <>
              <MealGroups summary={summary} />
              <WeightStrip trend={weightQuery.data} loading={weightQuery.isLoading} />
            </>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function SummaryStrip({
  summary,
  target,
  remaining,
}: {
  summary: DaySummary;
  target: Nutrients | null;
  remaining: Nutrients | null;
}) {
  return (
    <div className="summary-strip">
      <div className="summary-primary">
        <strong>{number(summary.totals.calories_kcal)} kcal</strong>
        <span>de {target?.calories_kcal != null ? `${number(target.calories_kcal)} kcal` : "meta aberta"}</span>
      </div>
      <div className="macro-grid" aria-label="Macronutrientes do dia">
        <Macro label="Prot" value={summary.totals.protein_g} target={target?.protein_g} />
        <Macro label="Carb" value={summary.totals.carbs_g} target={target?.carbs_g} />
        <Macro label="Gord" value={summary.totals.fat_g} target={target?.fat_g} />
        <Macro label="Fibra" value={summary.totals.fiber_g} target={target?.fiber_g} />
      </div>
      <p className="remaining-line">
        Restante: {remaining ? remainingText(remaining) : "sem meta ativa para este dia"}
      </p>
    </div>
  );
}

function Macro({ label, value, target }: { label: string; value?: number; target?: number }) {
  return (
    <span>
      <strong>{number(value)}g</strong>
      <small>
        {label}
        {target != null ? ` / ${number(target)}g` : ""}
      </small>
    </span>
  );
}

function MealGroups({ summary }: { summary: DaySummary }) {
  const groups = orderedMealEntries(summary.meals);
  if (groups.length === 0) {
    return <p className="empty-copy">Nada registrado ainda. Mande uma mensagem para começar.</p>;
  }
  return (
    <div className="meal-groups">
      {groups.map(([mealType, entries]) => (
        <section key={mealType} className="meal-group">
          <div className="meal-heading">
            <h3>{MEAL_LABELS[mealType] ?? mealType}</h3>
            <span>{number(sumCalories(entries))} kcal</span>
          </div>
          <div className="meal-entry-list">
            {entries.map((entry) => (
              <article key={entry.id} className="meal-entry">
                <div>
                  <strong>{entry.food_name}</strong>
                  <span>
                    {number(entry.quantity_g)}g · {[entry.brand, entry.food_version_label].filter(Boolean).join(" · ")}
                  </span>
                </div>
                <div className="entry-meta">
                  <strong>{number(entry.nutrients.calories_kcal)} kcal</strong>
                  <span className={`confidence-badge confidence-${confidenceKind(entry)}`}>
                    {confidenceLabel(entry)}
                  </span>
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function WeightStrip({ trend, loading }: { trend?: WeightTrend; loading: boolean }) {
  if (loading) {
    return <p className="weight-strip">Peso: carregando...</p>;
  }
  if (!trend?.latest_kg) {
    return <p className="weight-strip">Peso: nenhum registro recente.</p>;
  }
  const delta = trend.delta_kg;
  return (
    <p className="weight-strip">
      Peso: <strong>{formatKg(trend.latest_kg)}</strong>
      {delta != null ? <span>{delta >= 0 ? "+" : ""}{formatKg(delta)} desde o início</span> : null}
    </p>
  );
}

function orderedMealEntries(meals: Record<string, DaySummaryEntry[]>): Array<[string, DaySummaryEntry[]]> {
  const known = MEAL_ORDER.filter((meal) => meals[meal]?.length).map((meal) => [meal, meals[meal]] as [string, DaySummaryEntry[]]);
  const rest = Object.entries(meals)
    .filter(([meal, entries]) => entries.length && !MEAL_ORDER.includes(meal))
    .sort(([a], [b]) => a.localeCompare(b));
  return [...known, ...rest];
}

function sumCalories(entries: DaySummaryEntry[]): number {
  return entries.reduce((total, entry) => total + (entry.nutrients.calories_kcal ?? 0), 0);
}

function remainingText(remaining: Nutrients): string {
  return [
    `${number(remaining.calories_kcal)} kcal`,
    `${number(remaining.protein_g)}g prot`,
    `${number(remaining.carbs_g)}g carb`,
    `${number(remaining.fat_g)}g gord`,
    remaining.fiber_g != null ? `${number(remaining.fiber_g)}g fibra` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

function invertNutrients(nutrients: Nutrients): Nutrients {
  return {
    calories_kcal: invert(nutrients.calories_kcal),
    protein_g: invert(nutrients.protein_g),
    carbs_g: invert(nutrients.carbs_g),
    fat_g: invert(nutrients.fat_g),
    fiber_g: invert(nutrients.fiber_g),
    sodium_mg: invert(nutrients.sodium_mg),
  };
}

function invert(value?: number | null): number | undefined {
  return value == null ? undefined : -value;
}

function confidenceKind(entry: DaySummaryEntry): "exact" | "estimate" | "range" {
  if (entry.evidence_status.includes("range")) {
    return "range";
  }
  if (entry.confidence >= 0.9 || entry.evidence_status.includes("exact")) {
    return "exact";
  }
  return "estimate";
}

function confidenceLabel(entry: DaySummaryEntry): string {
  const kind = confidenceKind(entry);
  if (kind === "exact") {
    return "exato";
  }
  if (kind === "range") {
    return "faixa";
  }
  return "estimado";
}

function number(value?: number | null): string {
  return Math.round(value ?? 0).toLocaleString("pt-BR");
}

function formatKg(value: number): string {
  return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} kg`;
}

function formatDay(day: string): string {
  const [year, month, date] = day.split("-").map(Number);
  return new Intl.DateTimeFormat("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
  }).format(new Date(year, month - 1, date));
}
