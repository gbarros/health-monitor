import { useQuery } from "@tanstack/react-query";
import { loadReviewNotes, loadRollingSummary, loadWeekSummary, loadWeightTrend } from "../api";
import { queryKeys } from "../queryKeys";
import type { Nutrients, RollingSummary, WeightEntry } from "../types";

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
  const reviewNotesQuery = useQuery({
    queryKey: queryKeys.reviewNotes(personId),
    queryFn: () => loadReviewNotes(personId),
  });

  const summary = query.data;
  const rolling = rollingQuery.data;
  const rollingThirty = rollingThirtyQuery.data;
  const weekWeights = (weightQuery.data?.entries ?? []).filter(
    (entry) => entry.measured_at.slice(0, 10) >= start && entry.measured_at.slice(0, 10) <= end,
  );

  return (
    <section className="week-card" aria-label="Resumo da semana">
      <div className="section-heading">
        <span>Semana</span>
        <strong>
          {start.slice(5)} - {end.slice(5)}
        </strong>
      </div>
      {summary ? (
        <>
          <div className="week-bars">
            {Object.entries(summary.daily).map(([date, nutrients]) => {
              const target = summary.daily_targets[date]?.calories_kcal;
              const value = nutrients.calories_kcal ?? 0;
              const scale = Math.max(target ?? 2000, value, 1);
              const percent = Math.max(4, Math.min(100, (value / scale) * 100));
              const targetPercent = target != null ? Math.min(100, (target / scale) * 100) : null;
              return (
                <div key={date} className="week-bar-row">
                  <span>{weekdayLabel(date)}</span>
                  <div className="week-bar-track">
                    <div className="week-bar-fill" style={{ width: `${percent}%` }} />
                    {targetPercent != null ? (
                      <div className="week-bar-target" style={{ left: `${targetPercent}%` }} />
                    ) : null}
                  </div>
                  <strong>{Math.round(value)}</strong>
                </div>
              );
            })}
          </div>

          {weekWeights.length > 1 ? <WeightSparkline entries={weekWeights} /> : null}

          <p className="week-card__summary">
            Média: {Math.round(summary.averages.calories_kcal ?? 0)} kcal/dia
            {summary.weight_delta_kg != null
              ? ` · Peso ${summary.weight_delta_kg > 0 ? "+" : ""}${summary.weight_delta_kg} kg`
              : ""}
          </p>
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
                    {note.starts_on ?? "?"} - {note.ends_on ?? "?"} · {note.source}
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
        {rolling.days_with_data}/{rolling.days} dias
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
        <span>{dates[0]?.slice(5) ?? ""}</span>
        <span>{dates[dates.length - 1]?.slice(5) ?? ""}</span>
      </div>
    </div>
  );
}

function WeightSparkline({ entries }: { entries: WeightEntry[] }) {
  const sorted = [...entries].sort((a, b) => a.measured_at.localeCompare(b.measured_at));
  const values = sorted.map((entry) => entry.weight_kg);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 280;
  const height = 36;
  const points = sorted
    .map((entry, index) => {
      const x = (index / (sorted.length - 1)) * width;
      const y = height - ((entry.weight_kg - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div className="weight-sparkline" aria-label="Tendência de peso na semana">
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
        <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
      <span>
        {formatKg(sorted[0].weight_kg)} → {formatKg(sorted[sorted.length - 1].weight_kg)}
      </span>
    </div>
  );
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
