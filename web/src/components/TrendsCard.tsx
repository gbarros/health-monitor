import { useQuery } from "@tanstack/react-query";
import { loadWeekSummary } from "../api";
import { queryKeys } from "../queryKeys";
import type { Nutrients } from "../types";

type Props = {
  personId: string;
  day: string;
  today: string;
  onDayChange: (day: string) => void;
};

type Metric = {
  value: (nutrients: Nutrients | undefined) => number;
  target: (target: Nutrients | undefined) => number | null;
  formatValue: (value: number) => string;
  barClass: (value: number, target: number | null) => string;
};

const CALORIES_METRIC: Metric = {
  value: (nutrients) => nutrients?.calories_kcal ?? 0,
  target: (target) => target?.calories_kcal ?? null,
  formatValue: (value) => Math.round(value).toLocaleString("pt-BR"),
  barClass: (value, target) =>
    target != null && value > target ? "trend-bar--over" : "trend-bar--ok",
};

const PROTEIN_METRIC: Metric = {
  value: (nutrients) => nutrients?.protein_g ?? 0,
  target: (target) => target?.protein_g ?? null,
  formatValue: (value) => `${Math.round(value)}`,
  barClass: (value, target) =>
    target != null && value < target ? "trend-bar--partial" : "trend-bar--ok",
};

export function TrendsCard({ personId, day, today, onDayChange }: Props) {
  const { start, end } = weekWindow(day);
  const weekQuery = useQuery({
    queryKey: queryKeys.weekSummary(personId, start, end),
    queryFn: () => loadWeekSummary(personId, start, end),
  });

  const summary = weekQuery.data;
  if (weekQuery.isLoading) {
    return (
      <section className="trends-card" aria-label="Tendências dos últimos 7 dias">
        <div className="day-card-skeleton">Carregando tendências...</div>
      </section>
    );
  }
  if (!summary) {
    return null;
  }

  const dates = listDates(start, end);

  return (
    <section className="trends-card" aria-label="Tendências dos últimos 7 dias">
      <TrendChart
        title="Calorias"
        legend="barra = consumido · traço = meta"
        dates={dates}
        daily={summary.daily}
        dailyTargets={summary.daily_targets}
        metric={CALORIES_METRIC}
        selectedDay={day}
        today={today}
        onDayChange={onDayChange}
      />
      <TrendChart
        title="Proteína (g)"
        legend="traço = meta"
        dates={dates}
        daily={summary.daily}
        dailyTargets={summary.daily_targets}
        metric={PROTEIN_METRIC}
        selectedDay={day}
        today={today}
        onDayChange={onDayChange}
      />
    </section>
  );
}

function TrendChart({
  title,
  legend,
  dates,
  daily,
  dailyTargets,
  metric,
  selectedDay,
  today,
  onDayChange,
}: {
  title: string;
  legend: string;
  dates: string[];
  daily: Record<string, Nutrients>;
  dailyTargets: Record<string, Nutrients>;
  metric: Metric;
  selectedDay: string;
  today: string;
  onDayChange: (day: string) => void;
}) {
  const values = dates.map((date) => metric.value(daily[date]));
  const targets = dates.map((date) => metric.target(dailyTargets[date]));
  const scale = Math.max(...values, ...targets.map((target) => target ?? 0), 1);

  return (
    <div className="trend-chart">
      <div className="trend-chart__head">
        <span className="eyebrow">{title}</span>
        <small>{legend}</small>
      </div>
      <div className="trend-columns">
        {dates.map((date, index) => {
          const value = values[index];
          const target = targets[index];
          const heightPct = value > 0 ? Math.max(3, (value / scale) * 100) : 0;
          const targetPct = target != null ? Math.min(100, (target / scale) * 100) : null;
          const isSelected = date === selectedDay;
          const isToday = date === today;
          return (
            <button
              key={date}
              type="button"
              className={`trend-col${isSelected ? " is-selected" : ""}`}
              aria-label={`${weekdayLabel(date)} ${dayLabel(date)}: ${metric.formatValue(value)}${
                target != null ? ` de ${metric.formatValue(target)}` : ""
              }`}
              aria-pressed={isSelected}
              onClick={() => onDayChange(date)}
            >
              <span className="trend-col__value">{value > 0 ? metric.formatValue(value) : ""}</span>
              <span className="trend-col__area">
                <span
                  className={`trend-bar ${metric.barClass(value, target)}${isToday ? " trend-bar--today" : ""}`}
                  style={{ height: `${heightPct}%` }}
                />
                {targetPct != null ? (
                  <span className="trend-col__target" style={{ bottom: `${targetPct}%` }} />
                ) : null}
              </span>
              <span className="trend-col__day">
                {weekdayLabel(date)}
                <small>{dayLabel(date)}</small>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function weekWindow(day: string): { start: string; end: string } {
  const end = new Date(`${day}T12:00:00`);
  const start = new Date(end);
  start.setDate(end.getDate() - 6);
  return { start: isoDate(start), end: isoDate(end) };
}

function listDates(start: string, end: string): string[] {
  const dates: string[] = [];
  const cursor = new Date(`${start}T12:00:00`);
  const endDate = new Date(`${end}T12:00:00`);
  while (cursor <= endDate) {
    dates.push(isoDate(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return dates;
}

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function weekdayLabel(date: string): string {
  return new Intl.DateTimeFormat("pt-BR", { weekday: "short" })
    .format(new Date(`${date}T12:00:00`))
    .replace(".", "");
}

function dayLabel(date: string): string {
  return date.slice(8, 10);
}
