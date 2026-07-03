import { useAui } from "@assistant-ui/react";

export function ModesAndTemplates() {
  const aui = useAui();

  const handleModeClick = (template: string) => {
    aui.thread().composer().setText(template);
  };

  return (
    <div>
      <h3>Modes & Templates</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <button onClick={() => handleModeClick("Meal note: \n- ")}>Meal</button>
        <button onClick={() => handleModeClick("Recipe: \nYield: \nIngredients:\n- ")}>Recipe</button>
        <button onClick={() => handleModeClick("Product label: ")}>Label</button>
        <button onClick={() => handleModeClick("Correction: ")}>Correction</button>
        <button onClick={() => handleModeClick("Review note: ")}>Review Note</button>
      </div>
    </div>
  );
}
