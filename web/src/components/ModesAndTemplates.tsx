import { useAui } from "@assistant-ui/react";
import type { ModeId } from "../types";

type Props = {
  onModeChange: (mode: ModeId) => void;
  onToast: (message: string) => void;
};

export function QuickActionRow({ onModeChange, onToast }: Props) {
  const aui = useAui();

  const setComposer = (mode: ModeId, template: string) => {
    onModeChange(mode);
    aui.thread().composer().setText(template);
  };

  return (
    <nav className="quick-action-row" aria-label="Ações rápidas">
      <button type="button" onClick={() => onToast("Repetir refeição entra na fase 5.")}>
        Repetir refeição
      </button>
      <button type="button" onClick={() => onToast("Registro rápido de peso entra na fase 3.")}>
        Peso
      </button>
      <button
        type="button"
        onClick={() =>
          setComposer("recipe", "Receita/lote:\nRendimento total:\nIngredientes:\n- ")
        }
      >
        Receita/lote
      </button>
      <button
        type="button"
        onClick={() =>
          setComposer("label_scan", "Produto:\nCódigo de barras:\nTabela nutricional:\n")
        }
      >
        Escanear rótulo
      </button>
      <button type="button" onClick={() => setComposer("text_meal", "")}>
        Registrar refeição
      </button>
    </nav>
  );
}
