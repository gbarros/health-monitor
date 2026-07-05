import { useMemo, useState } from "react";
import type { Proposal, ProposalEntry } from "../types";
import { ProposalCard } from "./ProposalCard";

const STATUS_LABELS: Record<string, string> = {
  draft: "Rascunho",
  needs_clarification: "Precisa de contexto",
  applied: "Aplicada",
  rejected: "Rejeitada",
  superseded: "Substituída",
};

export function ProposalInbox({
  proposals,
  busy,
  onClose,
  onConfirm,
  onReject,
  onUpdateEntry,
}: {
  proposals: Proposal[];
  busy: boolean;
  onClose: () => void;
  onConfirm: (proposal: Proposal) => void;
  onReject: (proposal: Proposal) => void;
  onUpdateEntry: (proposal: Proposal, entry: ProposalEntry, quantityG: number) => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const byId = useMemo(() => new Map(proposals.map((proposal) => [proposal.id, proposal])), [proposals]);
  const sorted = useMemo(
    () =>
      [...proposals].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")),
    [proposals],
  );
  const selected = selectedId ? byId.get(selectedId) ?? null : null;

  return (
    <div className="sheet-backdrop" role="presentation" onClick={onClose}>
      <div
        className="sheet-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Propostas"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="section-heading">
          <span>{selected ? "Proposta" : "Propostas"}</span>
          <button type="button" onClick={selected ? () => setSelectedId(null) : onClose}>
            {selected ? "Voltar" : "Fechar"}
          </button>
        </div>

        {selected ? (
          <ProposalCard
            proposal={selected}
            busy={busy}
            onConfirm={onConfirm}
            onReject={onReject}
            onEntryQuantityChange={onUpdateEntry}
            onOpenSupersedingProposal={(proposalId) => setSelectedId(proposalId)}
          />
        ) : sorted.length === 0 ? (
          <p className="empty-copy">Nenhuma proposta ainda.</p>
        ) : (
          <div className="sheet-list">
            {sorted.map((proposal) => (
              <button
                key={proposal.id}
                type="button"
                className="entry-row-button sheet-list-row"
                onClick={() => setSelectedId(proposal.id)}
              >
                <span className="proposal-inbox-row">
                  <strong>{proposal.summary}</strong>
                  <span>
                    {proposal.totals?.calories_kcal != null ? `${Math.round(proposal.totals.calories_kcal)} kcal` : ""}
                  </span>
                </span>
                <span className={`status-pill status-pill--${proposal.status}`}>
                  {STATUS_LABELS[proposal.status] ?? proposal.status}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
