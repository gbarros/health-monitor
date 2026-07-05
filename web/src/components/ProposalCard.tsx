import { useEffect, useState } from "react";
import type { Proposal, ProposalEntry } from "../types";

export function ProposalCard({
  proposal,
  busy = false,
  onConfirm,
  onReject,
  onEntryQuantityChange,
  onOpenSupersedingProposal,
  showDetails = true,
}: {
  proposal: Proposal;
  busy?: boolean;
  onConfirm: (proposal: Proposal) => void;
  onReject: (proposal: Proposal) => void;
  onEntryQuantityChange?: (proposal: Proposal, entry: ProposalEntry, quantityG: number) => void;
  onOpenSupersedingProposal?: (proposalId: string) => void;
  showDetails?: boolean;
}) {
  const entries = proposal.entries ?? [];
  const canConfirm = proposal.status === "draft";
  const canReject = proposal.status === "draft" || proposal.status === "needs_clarification";
  const supersededBy = proposal.payload?.["superseded_by_proposal_id"];
  return (
    <section className="proposal-card" aria-label="Proposta de registro">
      <div className="proposal-card__header">
        <div>
          <p className="eyebrow">Proposta</p>
          <h3>{proposal.summary}</h3>
          <p className="proposal-card__meta">
            {proposalStatusLabel(proposal.status)}
            {proposal.payload?.["amended_from_proposal_id"] ? " · atualizada por mensagem" : ""}
          </p>
        </div>
        <span className={`status-pill status-pill--${proposal.status}`}>{proposal.status}</span>
      </div>

      {entries.length ? (
        <div className="proposal-entry-list">
          {entries.map((entry) => (
            <ProposalEntryRow
              key={entry.id}
              proposal={proposal}
              entry={entry}
              evidence={proposal.evidence?.find(
                (item) => item.food_version_id === entry.food_version_id,
              )}
              busy={busy || !canConfirm}
              onEntryQuantityChange={onEntryQuantityChange}
            />
          ))}
        </div>
      ) : (
        <p className="proposal-card__empty">A proposta precisa de mais informação antes de confirmar.</p>
      )}

      <div className="proposal-card__totals">{proposalTotals(proposal)}</div>

      {typeof supersededBy === "string" ? (
        <button
          type="button"
          className="compact-button"
          onClick={() => onOpenSupersedingProposal?.(supersededBy)}
        >
          Ver proposta que substituiu esta →
        </button>
      ) : null}

      <div className="proposal-actions">
        <button type="button" onClick={() => onReject(proposal)} disabled={busy || !canReject}>
          Rejeitar
        </button>
        <button type="button" className="primary-action" onClick={() => onConfirm(proposal)} disabled={busy || !canConfirm}>
          {canConfirm ? "Confirmar" : "Precisa revisar"}
        </button>
      </div>

      {showDetails ? <ProposalDetails proposal={proposal} /> : null}
    </section>
  );
}

function ProposalDetails({ proposal }: { proposal: Proposal }) {
  const run = proposal.agent_run;
  return (
    <details className="settings-disclosure proposal-details">
      <summary>Detalhes</summary>
      <div className="proposal-audit">
        <span>Criada: {formatDateTime(proposal.created_at)}</span>
        {proposal.confirmed_at ? <span>Confirmada: {formatDateTime(proposal.confirmed_at)}</span> : null}
        {proposal.rejected_at ? <span>Rejeitada: {formatDateTime(proposal.rejected_at)}</span> : null}
        {typeof proposal.payload?.["amended_from_proposal_id"] === "string" ? (
          <span>Substitui proposta {String(proposal.payload["amended_from_proposal_id"]).slice(0, 8)}</span>
        ) : null}
      </div>
      {run ? (
        <div className="proposal-agent-run">
          <span>
            Execução: {run.runtime ?? "?"} · modelo {run.model_name ?? "?"} · {run.tool_loop_count ?? 0} chamadas
          </span>
          {run.fallback_reason ? (
            <p className="form-error">Fallback usado: {run.fallback_reason}</p>
          ) : null}
          {run.tool_calls.length ? (
            <div className="tool-trace">
              {run.tool_calls.map((call) => (
                <div key={call.id} className="tool-trace-row">
                  <div className="tool-trace-row__header">
                    <strong>{humanizeToolName(call.tool_name)}</strong>
                    <span className={`status-pill status-pill--${call.status}`}>{call.status}</span>
                  </div>
                  {call.input_summary ? <span>Entrada: {call.input_summary}</span> : null}
                  {call.output_summary ? <span>Saída: {call.output_summary}</span> : null}
                  {call.error ? <span className="form-error">Erro: {call.error}</span> : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </details>
  );
}

function humanizeToolName(toolName: string): string {
  return toolName.replaceAll("_", " ");
}

function formatDateTime(iso?: string | null): string {
  if (!iso) {
    return "?";
  }
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function ProposalEntryRow({
  proposal,
  entry,
  evidence,
  busy,
  onEntryQuantityChange,
}: {
  proposal: Proposal;
  entry: ProposalEntry;
  evidence?: Record<string, unknown>;
  busy: boolean;
  onEntryQuantityChange?: (proposal: Proposal, entry: ProposalEntry, quantityG: number) => void;
}) {
  const [quantityText, setQuantityText] = useState(formatQuantity(entry.quantity_g));
  useEffect(() => {
    setQuantityText(formatQuantity(entry.quantity_g));
  }, [entry.quantity_g]);
  const confidence = Number(evidence?.confidence ?? entry.confidence ?? 0);
  const confidenceText = confidenceLabel(evidence, confidence);
  const parsedQuantity = Number(quantityText.replace(",", "."));
  const canSave =
    onEntryQuantityChange != null &&
    Number.isFinite(parsedQuantity) &&
    parsedQuantity > 0 &&
    Math.abs(parsedQuantity - entry.quantity_g) > 0.001;

  return (
    <div className="proposal-entry-row">
      <div className="proposal-entry-row__main">
        <strong>{entry.food_name ?? "Item"}</strong>
        <span>
          {entry.food_version_label ?? entry.food_version_id} · {mealLabel(entry.meal_type)}
        </span>
      </div>
      <label className="quantity-editor">
        <span>g</span>
        <input
          type="number"
          inputMode="decimal"
          min="0"
          step="1"
          value={quantityText}
          disabled={busy}
          onChange={(event) => setQuantityText(event.target.value)}
          onBlur={() => {
            if (canSave) {
              onEntryQuantityChange?.(proposal, entry, parsedQuantity);
            }
          }}
          aria-label={`Quantidade em gramas para ${entry.food_name ?? "item"}`}
        />
      </label>
      <span className="confidence-badge">{confidenceText}</span>
    </div>
  );
}

function confidenceLabel(evidence: Record<string, unknown> | undefined, confidence: number): string {
  if (String(evidence?.source_type ?? "").includes("range")) {
    return "faixa";
  }
  return confidence ? `${Math.round(confidence * 100)}%` : "conf.";
}

function proposalTotals(proposal: Proposal): string {
  const totals = proposal.totals;
  if (!totals) {
    return "Sem totais nutricionais.";
  }
  return [
    totals.calories_kcal != null ? `${Math.round(totals.calories_kcal)} kcal` : null,
    totals.protein_g != null ? `${roundOne(totals.protein_g)}g prot` : null,
    totals.carbs_g != null ? `${roundOne(totals.carbs_g)}g carb` : null,
    totals.fat_g != null ? `${roundOne(totals.fat_g)}g gord` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

function proposalStatusLabel(status: string): string {
  if (status === "draft") return "Aguardando confirmação";
  if (status === "needs_clarification") return "Precisa de mais contexto";
  if (status === "applied") return "Aplicada";
  if (status === "rejected") return "Rejeitada";
  if (status === "superseded") return "Substituída";
  return status;
}

function mealLabel(mealType: string): string {
  const labels: Record<string, string> = {
    breakfast: "café",
    lunch: "almoço",
    dinner: "jantar",
    snack: "lanche",
  };
  return labels[mealType] ?? mealType;
}

function formatQuantity(value: number): string {
  return Number.isInteger(value) ? String(value) : String(roundOne(value));
}

function roundOne(value: number): number {
  return Math.round(value * 10) / 10;
}
