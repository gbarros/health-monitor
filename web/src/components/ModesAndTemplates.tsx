import { useState } from "react";

type Props = {
  onLogFoodClick?: () => void;
  onRepeatClick?: () => void;
  onWeightClick?: () => void;
  onRecipeClick?: () => void;
  onLabelClick?: () => void;
};

export function ReplayBanner({
  count,
  busy,
  onReplay,
  onDiscardAll,
}: {
  count: number;
  busy: boolean;
  onReplay: () => void;
  onDiscardAll: () => void;
}) {
  const [confirmingDiscard, setConfirmingDiscard] = useState(false);
  return (
    <div className="replay-banner" role="alert">
      <span>
        {count} {count === 1 ? "mensagem aguardando" : "mensagens aguardando"} reenvio.
      </span>
      <div className="replay-banner__actions">
        <button
          type="button"
          onClick={() => (confirmingDiscard ? onDiscardAll() : setConfirmingDiscard(true))}
          disabled={busy}
        >
          {confirmingDiscard ? "Confirmar descartar" : "Descartar"}
        </button>
        <button type="button" className="primary-action" onClick={onReplay} disabled={busy}>
          {busy ? "Reenviando..." : "Reenviar"}
        </button>
      </div>
    </div>
  );
}

export function QuickActionRow({ onLogFoodClick, onRepeatClick, onWeightClick, onRecipeClick, onLabelClick }: Props) {
  return (
    <nav className="quick-action-row" aria-label="Ações rápidas">
      <button type="button" onClick={onLogFoodClick}>
        Registrar alimento
      </button>
      <button type="button" onClick={onRepeatClick}>
        Repetir refeição
      </button>
      <button type="button" onClick={onWeightClick}>
        Peso
      </button>
      <button
        type="button"
        onClick={onRecipeClick}
      >
        Receita/lote
      </button>
      <button
        type="button"
        onClick={onLabelClick}
      >
        Escanear rótulo
      </button>
    </nav>
  );
}
