import { useAui } from "@assistant-ui/react";

type Props = {
  onRepeatClick?: () => void;
  onWeightClick?: () => void;
  onRecipeClick?: () => void;
  onLabelClick?: () => void;
};

export function ReplayBanner({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  const aui = useAui();
  const replay = () => {
    aui.thread().append({ content: [{ type: "text", text: message }] });
    onDismiss();
  };
  return (
    <div className="replay-banner" role="alert">
      <span>Modelo indisponível — 1 mensagem aguardando reenvio.</span>
      <div className="replay-banner__actions">
        <button type="button" onClick={onDismiss}>
          Descartar
        </button>
        <button type="button" className="primary-action" onClick={replay}>
          Reenviar
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
