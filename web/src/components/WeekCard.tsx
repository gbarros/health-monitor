import { useQuery } from "@tanstack/react-query";
import { loadWeekSummary } from "../api";
import { queryKeys } from "../queryKeys";

export function WeekCard({ personId, day }: { personId: string; day: string }) {
  const { start, end } = weekWindow(day);
  const query = useQuery({
    queryKey: queryKeys.weekSummary(personId, start, end),
    queryFn: () => loadWeekSummary(personId, start, end),
  });
  const summary = query.data;
  return (
    <section className="week-card" aria-label="Resumo da semana">
      <div className="section-heading">
        <span>Semana</span>
        <strong>{start.slice(5)} - {end.slice(5)}</strong>
      </div>
      {summary ? (
        <>
          <div className="week-bars">
            {Object.entries(summary.daily).map(([date, nutrients]) => {
              const target = summary.daily_targets[date]?.calories_kcal ?? 2000;
              const value = nutrients.calories_kcal ?? 0;
              const percent = Math.max(4, Math.min(100, (value / target) * 100));
              return (
                <div key={date} className="week-bar-row">
                  <span>{weekdayLabel(date)}</span>
                  <div className="week-bar-track">
                    <div className="week-bar-fill" style={{ width: `${percent}%` }} />
                  </div>
                  <strong>{Math.round(value)}</strong>
                </div>
              );
            })}
          </div>
          <p className="week-card__summary">
            Média: {Math.round(summary.averages.calories_kcal ?? 0)} kcal/dia
            {summary.weight_delta_kg != null ? ` · Peso ${summary.weight_delta_kg > 0 ? "+" : ""}${summary.weight_delta_kg} kg` : ""}
          </p>
        </>
      ) : (
        <p className="week-card__summary">Carregando semana...</p>
      )}
    </section>
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
