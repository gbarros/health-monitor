import { useAui } from "@assistant-ui/react";

export function ManualInputs() {
  const aui = useAui();

  const handleWeightSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const weight = formData.get('weight');
    
    if (weight) {
      aui.thread().append({
        role: "user",
        content: [{ type: "text", text: `Log weight: ${weight} kg` }]
      });
      e.currentTarget.reset();
    }
  };

  return (
    <div>
      <h3>Manual Inputs</h3>
      <form onSubmit={handleWeightSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <label>
          Weight (kg):
          <input name="weight" type="number" step="0.1" required style={{ width: '100%', padding: '0.25rem' }} />
        </label>
        <button type="submit">Track via Agent</button>
      </form>
    </div>
  );
}
