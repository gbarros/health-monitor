import { useAui } from "@assistant-ui/react";

type Props = {
  onToast: (message: string) => void;
  onWeightClick?: () => void;
  onRecipeClick?: () => void;
  onLabelClick?: () => void;
};

export function QuickActionRow({ onToast, onWeightClick, onRecipeClick, onLabelClick }: Props) {
  const aui = useAui();

  const setComposer = (template: string) => {
    aui.thread().composer().setText(template);
  };

  return (
    <nav className="quick-action-row" aria-label="Ações rápidas">
      <button type="button" onClick={() => onToast("Repetir refeição entra na fase 5.")}>
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
