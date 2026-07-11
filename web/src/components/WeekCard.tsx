import { useQuery } from "@tanstack/react-query";
import { loadActiveGoal, loadReviewNotes, loadRollingSummary, loadWeekSummary, loadWeightTrend } from "../api";
import { queryKeys } from "../queryKeys";
import type { GoalProfile, Nutrients, RollingSummary, WeightEntry } from "../types";

export function WeekCard({ personId, day }: { personId: string; day: string }) {
  const { start, end } = weekWindow(day);
  const query = useQuery({
    queryKey: queryKeys.weekSummary(personId, start, end),
    queryFn: () => loadWeekSummary(personId, start, end),
  });
  const rollingQuery = useQuery({
    queryKey: queryKeys.rollingSummary(personId, day, 7),
    queryFn: () => loadRollingSummary({ personId, end: day, days: 7 }),
  });
  const rollingThirtyQuery = useQuery({
    queryKey: queryKeys.rollingSummary(personId, day, 30),
    queryFn: () => loadRollingSummary({ personId, end: day, days: 30 }),
  });
  const weightQuery = useQuery({
    queryKey: queryKeys.weightTrend(personId),
    queryFn: () => loadWeightTrend(personId),
  });
  const goalQuery = useQuery({
    queryKey: queryKeys.activeGoal(personId, day),
    queryFn: () => loadActiveGoal(personId, day),
  });
  const reviewNotesQuery = useQuery({
    queryKey: queryKeys.reviewNotes(personId),
    queryFn: () => loadReviewNotes(personId),
  });

  const summary = query.data;
  const rolling = rollingQuery.data;
  const rollingThirty = rollingThirtyQuery.data;
  const trendStart = addDays(day, -29);
  const trendWeights = (weightQuery.data?.entries ?? []).filter(
    (entry) => entry.measured_at.slice(0, 10) >= trendStart && entry.measured_at.slice(0, 10) <= day,
  );

  return (
    <section className="week-card" aria-label="Resumo da semana">
      <div className="section-heading">
        <span>Semana</span>
        <strong>{formatDay(start)} – {formatDay(end)}</strong>
      </div>
      {summary ? (
        <>
          {trendWeights.length > 1 ? <WeightTrendChart entries={trendWeights} goal={goalQuery.data ?? null} /> : null}

          <p className="week-card__summary">
            Média: {Math.round(summary.averages.calories_kcal ?? 0)} kcal/dia
            {summary.weight_delta_kg != null
              ? ` · Peso ${summary.weight_delta_kg > 0 ? "+" : ""}${summary.weight_delta_kg} kg`
              : ""}
          </p>
          <MacroSplit nutrients={summary.averages} />
          {rolling ? (
            <RollingStats rolling={rolling} rollingThirty={rollingThirty} />
          ) : null}

          {rollingThirty ? <CalorieTrendLine rolling={rollingThirty} /> : null}

          <details className="settings-disclosure">
            <summary>Tabela semanal</summary>
            <WeeklyTable daily={summary.daily} dailyTargets={summary.daily_targets} />
          </details>
        </>
      ) : (
        <p className="week-card__summary">Carregando semana...</p>
      )}

      {reviewNotesQuery.data?.length ? (
        <details className="settings-disclosure">
          <summary>Notas de revisão</summary>
          <div className="review-note-list">
            {reviewNotesQuery.data.map((note) => (
              <article key={note.id} className="review-note">
                <div className="proposal-card__meta">
                  <strong>{note.title}</strong>
                  <span>
                    {note.starts_on ? formatDay(note.starts_on) : "?"} – {note.ends_on ? formatDay(note.ends_on) : "?"} · {note.source}
                  </span>
                </div>
                <p>{note.body}</p>
              </article>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

function MacroSplit({ nutrients }: { nutrients: Nutrients }) {
  const segments = [
    { label: "Prot", grams: nutrients.protein_g ?? 0, kcalPerGram: 4, className: "macro-segment--protein" },
    { label: "Carb", grams: nutrients.carbs_g ?? 0, kcalPerGram: 4, className: "macro-segment--carbs" },
    { label: "Gord", grams: nutrients.fat_g ?? 0, kcalPerGram: 9, className: "macro-segment--fat" },
  ];
  const total = segments.reduce((sum, segment) => sum + segment.grams * segment.kcalPerGram, 0);
  if (total <= 0) {
    return null;
  }
  return (
    <div className="macro-split" aria-label="Divisão média de macros">
      <div className="macro-split-bar">
        {segments.map((segment) => (
          <span
            key={segment.label}
            className={segment.className}
            style={{
              width: `${segment.grams > 0 ? Math.max(4, ((segment.grams * segment.kcalPerGram) / total) * 100) : 0}%`,
            }}
          />
        ))}
      </div>
      <div className="macro-split-legend">
        {segments.map((segment) => (
          <span key={segment.label}>
            {segment.label} {roundOne(segment.grams)}g
          </span>
        ))}
      </div>
    </div>
  );
}

function RollingStats({
  rolling,
  rollingThirty,
}: {
  rolling: RollingSummary;
  rollingThirty?: RollingSummary;
}) {
  return (
    <div className="rolling-stat-grid" aria-label="Médias móveis">
      <RollingStatTile label="Média 7d" rolling={rolling} />
      {rollingThirty ? <RollingStatTile label="Média 30d" rolling={rollingThirty} /> : null}
    </div>
  );
}

function RollingStatTile({ label, rolling }: { label: string; rolling: RollingSummary }) {
  return (
    <div className="rolling-stat-tile">
      <span>{label}</span>
      <strong>{Math.round(rolling.averages.calories_kcal ?? 0)} kcal</strong>
      <small>
        ± {Math.round(rolling.stddev.calories_kcal ?? 0)} · {roundOne(rolling.averages.protein_g)}g prot ·{" "}
        média dos {rolling.days_with_data}/{rolling.days} dias registrados
      </small>
    </div>
  );
}

function CalorieTrendLine({ rolling }: { rolling: RollingSummary }) {
  const dates = Object.keys(rolling.daily).sort();
  const values = dates.map((date) => rolling.daily[date]?.calories_kcal ?? 0);
  const max = Math.max(...values, 1);
  const width = 420;
  const height = 96;
  const points = values
    .map((value, index) => {
      const x = dates.length > 1 ? (index / (dates.length - 1)) * width : width;
      const y = height - (value / max) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div className="calorie-trend" aria-label="Linha de kcal dos últimos 30 dias">
      <div className="section-heading">
        <span>30 dias kcal</span>
        <strong>{rolling.days_with_data}/{rolling.days}</strong>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
        <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2.5" />
      </svg>
      <div className="trend-axis">
        <span>{dates[0] ? formatDay(dates[0]) : ""}</span>
        <span>{dates.length ? formatDay(dates[dates.length - 1]) : ""}</span>
      </div>
    </div>
  );
}

function WeightTrendChart({ entries, goal }: { entries: WeightEntry[]; goal: GoalProfile | null }) {
  const sorted = [...entries].sort((a, b) => a.measured_at.localeCompare(b.measured_at));
  const values = sorted.map((entry) => entry.weight_kg);
  const guide = weightGoalGuide(sorted, goal);
  const guideValues = guide?.points.map((point) => point.weight_kg) ?? [];
  const min = Math.min(...values, ...guideValues);
  const max = Math.max(...values, ...guideValues);
  const range = max - min || 1;
  const width = 420;
  const height = 96;
  const points = trendPoints(
    sorted.map((entry) => ({ day: entry.measured_at.slice(0, 10), weight_kg: entry.weight_kg })),
    min,
    range,
    width,
    height,
  );
  const guidePoints = guide ? trendPoints(guide.points, min, range, width, height) : "";
  return (
    <div className="weight-trend-chart" aria-label="Tendência de peso">
      <div className="section-heading">
        <span>Peso 30 dias</span>
        <strong>{formatKg(sorted[sorted.length - 1].weight_kg)}</strong>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
        {guidePoints ? <polyline points={guidePoints} fill="none" stroke="currentColor" strokeDasharray="5 5" strokeWidth="2" /> : null}
        <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
      <div className="trend-axis">
        <span>{formatDay(sorted[0].measured_at.slice(0, 10))}</span>
        <span>{formatKg(sorted[0].weight_kg)} → {formatKg(sorted[sorted.length - 1].weight_kg)}</span>
        <span>{formatDay(sorted[sorted.length - 1].measured_at.slice(0, 10))}</span>
      </div>
      {guide ? <small>Guia: {guide.label}</small> : <small>Adicione uma meta em kg/sem nas notas para ver o guia.</small>}
    </div>
  );
}

function trendPoints(
  points: Array<{ day: string; weight_kg: number }>,
  min: number,
  range: number,
  width: number,
  height: number,
): string {
  const first = points[0]?.day ?? "";
  const last = points[points.length - 1]?.day ?? first;
  const totalDays = Math.max(1, daysBetween(first, last));
  return points
    .map((point) => {
      const x = (daysBetween(first, point.day) / totalDays) * width;
      const y = height - ((point.weight_kg - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function weightGoalGuide(
  entries: WeightEntry[],
  goal: GoalProfile | null,
): { label: string; points: Array<{ day: string; weight_kg: number }> } | null {
  const rate = parseKgPerWeek(goal?.notes ?? "");
  if (rate == null || entries.length < 2) {
    return null;
  }
  const first = entries[0];
  const last = entries[entries.length - 1];
  const firstDay = first.measured_at.slice(0, 10);
  const lastDay = last.measured_at.slice(0, 10);
  const projected = first.weight_kg + (rate / 7) * daysBetween(firstDay, lastDay);
  return {
    label: `${rate > 0 ? "+" : ""}${rate.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} kg/sem`,
    points: [
      { day: firstDay, weight_kg: first.weight_kg },
      { day: lastDay, weight_kg: projected },
    ],
  };
}

function parseKgPerWeek(notes: string): number | null {
  const match = notes.match(/([+-]?\d+(?:[,.]\d+)?)\s*kg\s*\/?\s*(?:sem|semana)/i);
  if (!match) {
    return null;
  }
  const value = Number(match[1].replace(",", "."));
  return Number.isFinite(value) ? value : null;
}

function WeeklyTable({
  daily,
  dailyTargets,
}: {
  daily: Record<string, Nutrients>;
  dailyTargets: Record<string, Nutrients>;
}) {
  const dates = Object.keys(daily).sort();
  return (
    <div className="table-scroll">
      <table className="weekly-table">
        <thead>
          <tr>
            <th>Dia</th>
            <th>kcal</th>
            <th>Prot</th>
            <th>Carb</th>
            <th>Gord</th>
            <th>Fibra</th>
            <th>Sódio</th>
            <th>Meta kcal</th>
          </tr>
        </thead>
        <tbody>
          {dates.map((date) => {
            const nutrients = daily[date];
            const target = dailyTargets[date];
            return (
              <tr key={date}>
                <td>{weekdayLabel(date)}</td>
                <td>{Math.round(nutrients.calories_kcal ?? 0)}</td>
                <td>{roundOne(nutrients.protein_g)}</td>
                <td>{roundOne(nutrients.carbs_g)}</td>
                <td>{roundOne(nutrients.fat_g)}</td>
                <td>{roundOne(nutrients.fiber_g)}</td>
                <td>{Math.round(nutrients.sodium_mg ?? 0)}</td>
                <td>{target?.calories_kcal != null ? Math.round(target.calories_kcal) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function weekWindow(day: string): { start: string; end: string } {
  const end = new Date(`${day}T12:00:00`);
  const start = new Date(end);
  start.setDate(end.getDate() - 6);
  return { start: isoDate(start), end: isoDate(end) };
}

function addDays(day: string, offset: number): string {
  const date = new Date(`${day}T12:00:00`);
  date.setDate(date.getDate() + offset);
  return isoDate(date);
}

function daysBetween(start: string, end: string): number {
  const startMs = new Date(`${start}T12:00:00`).getTime();
  const endMs = new Date(`${end}T12:00:00`).getTime();
  return Math.round((endMs - startMs) / 86_400_000);
}

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function weekdayLabel(date: string): string {
  return new Intl.DateTimeFormat("pt-BR", { weekday: "short" }).format(new Date(`${date}T12:00:00`));
}

function roundOne(value?: number | null): number {
  return Math.round((value ?? 0) * 10) / 10;
}

function formatKg(value: number): string {
  return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} kg`;
}

function formatDay(day: string): string {
  const [, month, date] = day.split("-");
  return `${date}/${month}`;
}
