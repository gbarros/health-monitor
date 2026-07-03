import type { AgentSettings, Person } from "../types";

type Props = {
  people: Person[];
  personId: string | null;
  settings: AgentSettings;
  onPersonChange: (personId: string) => void;
  onSettingsChange: (settings: AgentSettings) => void;
};

export function ContextPanel({
  people,
  personId,
  settings,
  onPersonChange,
  onSettingsChange,
}: Props) {
  return (
    <section className="context-panel" aria-label="Contexto atual">
      <div className="section-heading">
        <span>Contexto</span>
        <strong>{people.find((person) => person.id === personId)?.name ?? "Sem perfil"}</strong>
      </div>

      <label className="field">
        <span>Perfil</span>
        <select
          value={personId ?? ""}
          onChange={(event) => onPersonChange(event.target.value)}
          disabled={!people.length}
        >
          {people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.name}
            </option>
          ))}
        </select>
      </label>

      <details className="settings-disclosure">
        <summary>Modelo e esforço</summary>
        <label className="field">
          <span>Runtime</span>
          <select
            value={settings.agent_runtime}
            onChange={(event) =>
              onSettingsChange({
                ...settings,
                agent_runtime: event.target.value as AgentSettings["agent_runtime"],
              })
            }
          >
            <option value="pydantic-ai">PydanticAI / Ollama</option>
            <option value="deterministic">Fallback determinístico</option>
          </select>
        </label>
        <label className="field">
          <span>Modelo</span>
          <input
            value={settings.model_profile}
            onChange={(event) => onSettingsChange({ ...settings, model_profile: event.target.value })}
            placeholder="qwen3.6:latest"
          />
        </label>
        <label className="field">
          <span>Esforço</span>
          <select
            value={settings.effort}
            onChange={(event) =>
              onSettingsChange({ ...settings, effort: event.target.value as AgentSettings["effort"] })
            }
          >
            <option value="low">Baixo</option>
            <option value="normal">Normal</option>
            <option value="medium">Médio</option>
            <option value="high">Alto</option>
          </select>
        </label>
        <label className="field">
          <span>Loops de ferramenta</span>
          <input
            type="number"
            min={1}
            max={12}
            value={settings.max_tool_loops}
            onChange={(event) =>
              onSettingsChange({
                ...settings,
                max_tool_loops: Number(event.target.value) || settings.max_tool_loops,
              })
            }
          />
        </label>
        <label className="check-field">
          <input
            type="checkbox"
            checked={settings.research_lookup}
            onChange={(event) =>
              onSettingsChange({ ...settings, research_lookup: event.target.checked })
            }
          />
          <span>Permitir pesquisa controlada</span>
        </label>
      </details>
    </section>
  );
}
