import { useAui } from "@assistant-ui/react";
import { useState } from "react";

type Props = {
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

export function QuickActionRow({ onRepeatClick, onWeightClick, onRecipeClick, onLabelClick }: Props) {
  const aui = useAui();

  const setComposer = (template: string) => {
    aui.thread().composer().setText(template);
  };

  return (
    <nav className="quick-action-row" aria-label="Ações rápidas">
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
      <button type="button" onClick={() => setComposer("Almoço:\n")}>
        Registrar refeição
      </button>
    </nav>
  );
}
