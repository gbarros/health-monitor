import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { deleteDiaryEntry, updateDiaryEntry, updateWeightEntry } from "../api";
import { queryKeys } from "../queryKeys";
import type { DaySummaryEntry, WeightEntry } from "../types";

const MEAL_TYPE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "breakfast", label: "Café" },
  { value: "lunch", label: "Almoço" },
  { value: "snack", label: "Lanche" },
  { value: "dinner", label: "Janta" },
  { value: "late", label: "Madrugada" },
];

export function EntrySheet({
  entry,
  personId,
  day,
  onClose,
  onToast,
  onDeleted,
}: {
  entry: DaySummaryEntry;
  personId: string;
  day: string;
  onClose: () => void;
  onToast: (message: string) => void;
  onDeleted: (entryId: string) => void;
}) {
  const queryClient = useQueryClient();
  const [quantityText, setQuantityText] = useState(String(entry.quantity_g));
  const [mealType, setMealType] = useState(entry.meal_type);

  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.daySummary(personId, day) }),
      queryClient.invalidateQueries({ queryKey: ["weekSummary", personId] }),
    ]);

  const save = useMutation({
    mutationFn: () =>
      updateDiaryEntry({
        entryId: entry.id,
        quantityG: Number(quantityText.replace(",", ".")),
        mealType,
      }),
    onSuccess: async () => {
      await invalidate();
      onClose();
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível editar o item."),
  });

  const remove = useMutation({
    mutationFn: () => deleteDiaryEntry(entry.id),
    onSuccess: async () => {
      await invalidate();
      onDeleted(entry.id);
      onClose();
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível excluir o item."),
  });

  const parsedQuantity = Number(quantityText.replace(",", "."));
  const canSave = Number.isFinite(parsedQuantity) && parsedQuantity > 0;

  return (
    <div className="sheet-backdrop" role="presentation" onClick={onClose}>
      <div
        className="sheet-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Detalhe do item"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="section-heading">
          <span>{entry.food_name}</span>
          <button type="button" onClick={onClose}>
            Fechar
          </button>
        </div>
        <div className="sheet-entry-detail">
          <span>{[entry.brand, entry.food_version_label].filter(Boolean).join(" · ")}</span>
          <span>Fonte: {entry.source}</span>
          <span>
            Evidência: {entry.evidence_status} · confiança {Math.round((entry.confidence ?? 0) * 100)}%
          </span>
          <span>Registrado às {formatTime(entry.logged_at)}</span>
        </div>
        <div className="macro-grid" aria-label="Nutrientes do item">
          <span>
            <strong>{Math.round(entry.nutrients.calories_kcal ?? 0)}</strong>
            <small>kcal</small>
          </span>
          <span>
            <strong>{Math.round(entry.nutrients.protein_g ?? 0)}g</strong>
            <small>Prot</small>
          </span>
          <span>
            <strong>{Math.round(entry.nutrients.carbs_g ?? 0)}g</strong>
            <small>Carb</small>
          </span>
          <span>
            <strong>{Math.round(entry.nutrients.fat_g ?? 0)}g</strong>
            <small>Gord</small>
          </span>
          <span>
            <strong>{Math.round(entry.nutrients.fiber_g ?? 0)}g</strong>
            <small>Fibra</small>
          </span>
          <span>
            <strong>{Math.round(entry.nutrients.sodium_mg ?? 0)}mg</strong>
            <small>Sódio</small>
          </span>
        </div>
        <label className="field">
          <span>Quantidade (g)</span>
          <input
            inputMode="decimal"
            value={quantityText}
            onChange={(event) => setQuantityText(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Refeição</span>
          <select value={mealType} onChange={(event) => setMealType(event.target.value)}>
            {MEAL_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <div className="proposal-actions">
          <button type="button" onClick={() => remove.mutate()} disabled={remove.isPending || save.isPending}>
            {remove.isPending ? "Excluindo..." : "Excluir"}
          </button>
          <button
            type="button"
            className="primary-action"
            onClick={() => save.mutate()}
            disabled={!canSave || save.isPending || remove.isPending}
          >
            {save.isPending ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function WeightSheet({
  entries,
  onClose,
  onToast,
}: {
  entries: WeightEntry[];
  onClose: () => void;
  onToast: (message: string) => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  return (
    <div className="sheet-backdrop" role="presentation" onClick={onClose}>
      <div
        className="sheet-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Histórico de peso"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="section-heading">
          <span>Histórico de peso</span>
          <button type="button" onClick={onClose}>
            Fechar
          </button>
        </div>
        {entries.length === 0 ? <p className="empty-copy">Nenhum registro de peso ainda.</p> : null}
        <div className="sheet-list">
          {entries.map((entry) =>
            editingId === entry.id ? (
              <WeightEditRow
                key={entry.id}
                entry={entry}
                onToast={onToast}
                onDone={() => setEditingId(null)}
              />
            ) : (
              <button
                key={entry.id}
                type="button"
                className="entry-row-button sheet-list-row"
                onClick={() => setEditingId(entry.id)}
              >
                <span>
                  {formatDateTime(entry.measured_at)}
                  {entry.note ? ` · ${entry.note}` : ""}
                </span>
                <strong>{entry.weight_kg.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} kg</strong>
              </button>
            ),
          )}
        </div>
      </div>
    </div>
  );
}

function WeightEditRow({
  entry,
  onToast,
  onDone,
}: {
  entry: WeightEntry;
  onToast: (message: string) => void;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [weightText, setWeightText] = useState(String(entry.weight_kg));
  const [note, setNote] = useState(entry.note ?? "");
  const [measuredAt, setMeasuredAt] = useState(entry.measured_at.slice(0, 16));

  const save = useMutation({
    mutationFn: () =>
      updateWeightEntry({
        entryId: entry.id,
        weightKg: Number(weightText.replace(",", ".")),
        measuredAtLocal: measuredAt,
        note: note.trim() || undefined,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.weightTrend(entry.person_id) });
      onDone();
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível editar o peso."),
  });

  const parsed = Number(weightText.replace(",", "."));
  const canSave = Number.isFinite(parsed) && parsed > 0;

  return (
    <div className="sheet-list-row" style={{ gridTemplateColumns: "1fr" }}>
      <label className="field">
        <span>Data/hora</span>
        <input type="datetime-local" value={measuredAt} onChange={(event) => setMeasuredAt(event.target.value)} />
      </label>
      <label className="field">
        <span>Peso (kg)</span>
        <input inputMode="decimal" value={weightText} onChange={(event) => setWeightText(event.target.value)} />
      </label>
      <label className="field">
        <span>Nota</span>
        <input value={note} onChange={(event) => setNote(event.target.value)} />
      </label>
      <div className="proposal-actions">
        <button type="button" onClick={onDone} disabled={save.isPending}>
          Cancelar
        </button>
        <button type="button" className="primary-action" onClick={() => save.mutate()} disabled={!canSave || save.isPending}>
          {save.isPending ? "Salvando..." : "Salvar"}
        </button>
      </div>
    </div>
  );
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}
