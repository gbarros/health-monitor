import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { loadActiveGoal, loadDaySummary, loadWeightTrend } from "../api";
import { queryKeys } from "../queryKeys";
import type { DaySummary, DaySummaryEntry, Nutrients, WeightTrend } from "../types";
import { EntrySheet, WeightSheet } from "./DayEntrySheet";

type Props = {
  personId: string;
  day: string;
  today: string;
  onDayChange: (day: string) => void;
  onToast: (message: string) => void;
  onEntryDeleted: (entryId: string) => void;
};

const MEAL_LABELS: Record<string, string> = {
  breakfast: "Café",
  lunch: "Almoço",
  snack: "Lanche",
  dinner: "Janta",
  unknown: "Sem refeição",
};

const MEAL_ORDER = ["breakfast", "lunch", "snack", "dinner", "unknown"];

export function DayCard({ personId, day, today, onDayChange, onToast, onEntryDeleted }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [weightSheetOpen, setWeightSheetOpen] = useState(false);

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
  const selectedEntry = selectedEntryId ? findEntry(summary, selectedEntryId) : null;

  return (
    <section className="day-card" aria-label="Resumo do dia">
      <header className="day-card-header">
        <div className="day-nav">
          <button type="button" aria-label="Dia anterior" onClick={() => onDayChange(addDays(day, -1))}>
            ‹
          </button>
          <label className="day-date-button">
            <p className="eyebrow">{isToday(day, today) ? "Hoje" : "Dia"}</p>
            <h2>{formatDay(day)}</h2>
            <input
              type="date"
              value={day}
              max={today}
              aria-label="Escolher outro dia"
              onChange={(event) => event.target.value && onDayChange(event.target.value)}
            />
          </label>
          <button
            type="button"
            aria-label="Próximo dia"
            onClick={() => onDayChange(addDays(day, 1))}
            disabled={day >= today}
          >
            ›
          </button>
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
              <MealGroups
                summary={summary}
                proteinTarget={target?.protein_g ?? null}
                onEntryClick={(entry) => setSelectedEntryId(entry.id)}
              />
              <WeightStrip
                trend={weightQuery.data}
                loading={weightQuery.isLoading}
                onClick={() => setWeightSheetOpen(true)}
              />
            </>
          ) : null}
        </>
      ) : null}

      {selectedEntry ? (
        <EntrySheet
          entry={selectedEntry}
          personId={personId}
          day={day}
          onClose={() => setSelectedEntryId(null)}
          onToast={onToast}
          onDeleted={onEntryDeleted}
        />
      ) : null}

      {weightSheetOpen ? (
        <WeightSheet
          entries={weightQuery.data?.entries ?? []}
          onClose={() => setWeightSheetOpen(false)}
          onToast={onToast}
        />
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
  const entryCount = Object.values(summary.meals).reduce((total, entries) => total + entries.length, 0);
  const withinCalorieTarget =
    target?.calories_kcal != null && (summary.totals.calories_kcal ?? 0) <= target.calories_kcal;
  return (
    <div className="summary-strip">
      <div className="summary-primary">
        <strong>{number(summary.totals.calories_kcal)} kcal</strong>
        <span>de {target?.calories_kcal != null ? `${number(target.calories_kcal)} kcal` : "meta aberta"}</span>
      </div>
      <GoalBar
        label="kcal"
        value={summary.totals.calories_kcal ?? 0}
        target={target?.calories_kcal ?? null}
        fillClass="goal-bar__fill--kcal"
        overClass="goal-bar__fill--over"
        format={(value) => `${number(value)} kcal`}
      />
      <GoalBar
        label="proteína"
        value={summary.totals.protein_g ?? 0}
        target={target?.protein_g ?? null}
        fillClass="goal-bar__fill--protein"
        overClass="goal-bar__fill--met"
        format={(value) => `${number(value)} g`}
      />
      <div className="macro-grid" aria-label="Macronutrientes do dia">
        <Macro label="Prot" value={summary.totals.protein_g} target={target?.protein_g} />
        <Macro label="Carb" value={summary.totals.carbs_g} target={target?.carbs_g} />
        <Macro label="Gord" value={summary.totals.fat_g} target={target?.fat_g} />
        <Macro label="Fibra" value={summary.totals.fiber_g} target={target?.fiber_g} />
      </div>
      <p className="remaining-line">
        {entryCount} {entryCount === 1 ? "item" : "itens"} · Restante:{" "}
        {remaining ? remainingText(remaining) : "sem meta ativa para este dia"}
        {withinCalorieTarget ? " ✓" : ""}
      </p>
    </div>
  );
}

function GoalBar({
  label,
  value,
  target,
  fillClass,
  overClass,
  format,
}: {
  label: string;
  value: number;
  target: number | null;
  fillClass: string;
  overClass: string;
  format: (value: number) => string;
}) {
  if (target == null || target <= 0) {
    return null;
  }
  const scale = Math.max(value, target);
  const fillPct = value > 0 ? Math.max(1.5, (value / scale) * 100) : 0;
  const targetPct = Math.min(100, (target / scale) * 100);
  return (
    <div className="goal-bar" aria-label={`Progresso de ${label}: ${format(value)} de ${format(target)}`}>
      <div className="goal-bar__track">
        <div
          className={`goal-bar__fill ${fillClass}${value > target ? ` ${overClass}` : ""}`}
          style={{ width: `${fillPct}%` }}
        />
        <div className="goal-bar__tick" style={{ left: `${targetPct}%` }} />
      </div>
      <div className="goal-bar__labels">
        <span>{format(value)}</span>
        <span>meta {format(target)}</span>
      </div>
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

function MealGroups({
  summary,
  proteinTarget,
  onEntryClick,
}: {
  summary: DaySummary;
  proteinTarget: number | null;
  onEntryClick: (entry: DaySummaryEntry) => void;
}) {
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
              <button
                key={entry.id}
                type="button"
                className="entry-row-button"
                onClick={() => onEntryClick(entry)}
              >
                <article className="meal-entry">
                  <div>
                    <strong>{entry.food_name}</strong>
                    <span>
                      {[
                        `${number(entry.quantity_g)}g`,
                        formatTime(entry.logged_at),
                        entry.brand,
                        entry.food_version_label,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </div>
                  <EntryProteinShare protein={entry.nutrients.protein_g} proteinTarget={proteinTarget} />
                  <div className="entry-meta">
                    <strong>
                      {entry.nutrients.protein_g != null && entry.nutrients.protein_g >= 1
                        ? `${number(entry.nutrients.protein_g)}g P · `
                        : ""}
                      {number(entry.nutrients.calories_kcal)} kcal
                    </strong>
                    <span className={`confidence-badge confidence-${confidenceKind(entry)}`}>
                      {confidenceLabel(entry)}
                    </span>
                  </div>
                </article>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function EntryProteinShare({
  protein,
  proteinTarget,
}: {
  protein?: number | null;
  proteinTarget: number | null;
}) {
  if (proteinTarget == null || proteinTarget <= 0) {
    return null;
  }
  const share = Math.round(((protein ?? 0) / proteinTarget) * 100);
  return (
    <div className="entry-protein-share" aria-label={`${share}% da meta de proteína`}>
      <span>{share}%</span>
      <div className="entry-protein-share__track">
        <div
          className="entry-protein-share__fill"
          style={{ width: `${Math.min(100, Math.max(share > 0 ? 4 : 0, share))}%` }}
        />
      </div>
    </div>
  );
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function WeightStrip({
  trend,
  loading,
  onClick,
}: {
  trend?: WeightTrend;
  loading: boolean;
  onClick: () => void;
}) {
  if (loading) {
    return <p className="weight-strip">Peso: carregando...</p>;
  }
  return (
    <button type="button" className="entry-row-button weight-strip" onClick={onClick}>
      {!trend?.latest_kg ? (
        <span>Peso: nenhum registro recente.</span>
      ) : (
        <>
          <span>Peso recente</span>
          <strong>{formatKg(trend.latest_kg)}</strong>
          {trend.delta_kg != null ? (
            <span>
              {trend.delta_kg >= 0 ? "+" : ""}
              {formatKg(trend.delta_kg)} desde o início
            </span>
          ) : null}
        </>
      )}
    </button>
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

function findEntry(summary: DaySummary | undefined, entryId: string): DaySummaryEntry | null {
  if (!summary) {
    return null;
  }
  for (const entries of Object.values(summary.meals)) {
    const found = entries.find((entry) => entry.id === entryId);
    if (found) {
      return found;
    }
  }
  return null;
}

function isToday(day: string, today: string): boolean {
  return day === today;
}

function addDays(day: string, delta: number): string {
  const date = new Date(`${day}T12:00:00`);
  date.setDate(date.getDate() + delta);
  return date.toISOString().slice(0, 10);
}
