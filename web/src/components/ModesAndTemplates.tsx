import { useAui } from "@assistant-ui/react";
import type { ModeId } from "../types";

export const CHAT_MODES: Array<{
  id: ModeId;
  label: string;
  description: string;
  template: string;
}> = [
  {
    id: "general_chat",
    label: "Chat",
    description: "Questions, planning, profile or goal changes",
    template: "",
  },
  {
    id: "text_meal",
    label: "Meal note",
    description: "Paste or type a list of foods and portions",
    template: "- \n- \n\nContext: ",
  },
  {
    id: "label_scan",
    label: "Product label",
    description: "Attach photos or paste nutrition table/barcode text",
    template: "Product:\nBarcode:\nNutrition table:\n",
  },
  {
    id: "recipe",
    label: "Recipe",
    description: "Batch food, yield, ingredients, serving notes",
    template: "Recipe:\nYield:\nIngredients:\n- \n\nHow I will use it:\n",
  },
  {
    id: "correction",
    label: "Correction",
    description: "Fix a previous entry through a proposal",
    template: "Please correct: ",
  },
  {
    id: "review_note",
    label: "Review note",
    description: "Ask for a pattern, weekly note, or coaching observation",
    template: "Review note request: ",
  },
];

type Props = {
  activeMode: ModeId;
  onModeChange: (mode: ModeId) => void;
};

export function ModesAndTemplates({ activeMode, onModeChange }: Props) {
  const aui = useAui();

  const selectMode = (mode: ModeId, template: string) => {
    onModeChange(mode);
    if (template) {
      aui.thread().composer().setText(template);
    }
  };

  return (
    <section className="mode-panel" aria-label="Conversation modes">
      <div className="section-heading">
        <span>Modes</span>
        <strong>{CHAT_MODES.find((mode) => mode.id === activeMode)?.label}</strong>
      </div>
      <div className="mode-list">
        {CHAT_MODES.map((mode) => (
          <button
            key={mode.id}
            type="button"
            className={mode.id === activeMode ? "mode-card is-active" : "mode-card"}
            onClick={() => selectMode(mode.id, mode.template)}
            aria-pressed={mode.id === activeMode}
          >
            <span>{mode.label}</span>
            <small>{mode.description}</small>
          </button>
        ))}
      </div>
    </section>
  );
}
