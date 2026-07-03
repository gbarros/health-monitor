import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  confirmProposal,
  createInitialProfile,
  defaultAgentSettings,
  loadChatHistory,
  loadPeople,
  parseOnboardingMessage,
  rejectProposal,
  STORAGE_KEYS,
} from "./api";
import { ChatInterface } from "./components/ChatInterface";
import { ContextPanel } from "./components/ManualInputs";
import { CHAT_MODES, ModesAndTemplates } from "./components/ModesAndTemplates";
import { useAgentRuntime } from "./hooks/useAgentRuntime";
import type {
  AgentChatResponse,
  AgentChatTurn,
  AgentSettings,
  AppEvent,
  ModeId,
  OnboardingDraft,
  Person,
  Proposal,
} from "./types";

function App() {
  const [householdId, setHouseholdId] = useState<string | null>(() =>
    localStorage.getItem(STORAGE_KEYS.householdId),
  );
  const [personId, setPersonId] = useState<string | null>(() =>
    localStorage.getItem(STORAGE_KEYS.personId),
  );
  const [people, setPeople] = useState<Person[]>([]);
  const [activeMode, setActiveMode] = useState<ModeId>("general_chat");
  const [settings, setSettings] = useState<AgentSettings>(() => defaultAgentSettings());
  const [events, setEvents] = useState<AppEvent[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [chatHistory, setChatHistory] = useState<AgentChatTurn[]>([]);
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const [isBooting, setIsBooting] = useState(true);

  const addEvent = useCallback((event: Omit<AppEvent, "id" | "createdAt">) => {
    setEvents((current) => [
      {
        ...event,
        id: crypto.randomUUID(),
        createdAt: new Date().toISOString(),
      },
      ...current,
    ].slice(0, 12));
  }, []);

  const refreshPeople = useCallback(async (nextHouseholdId: string, preferredPersonId?: string | null) => {
    const nextPeople = await loadPeople(nextHouseholdId);
    setPeople(nextPeople);
    const nextPersonId =
      preferredPersonId && nextPeople.some((person) => person.id === preferredPersonId)
        ? preferredPersonId
        : nextPeople[0]?.id ?? null;
    setPersonId(nextPersonId);
    if (nextPersonId) {
      localStorage.setItem(STORAGE_KEYS.personId, nextPersonId);
    }
  }, []);

  const refreshChatHistory = useCallback(async (nextPersonId: string | null) => {
    if (!nextPersonId) {
      setChatHistory([]);
      return;
    }
    const turns = await loadChatHistory(nextPersonId);
    setChatHistory([...turns].reverse());
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      if (!householdId) {
        setIsBooting(false);
        return;
      }
      try {
        await refreshPeople(householdId, personId);
      } catch (error) {
        localStorage.removeItem(STORAGE_KEYS.householdId);
        localStorage.removeItem(STORAGE_KEYS.personId);
        if (!cancelled) {
          setHouseholdId(null);
          setPersonId(null);
          addEvent({
            title: "Stored profile could not be loaded",
            detail: error instanceof Error ? error.message : "Unknown startup error",
            tone: "warning",
          });
        }
      } finally {
        if (!cancelled) {
          setIsBooting(false);
        }
      }
    }
    void boot();
    return () => {
      cancelled = true;
    };
  }, [addEvent, householdId, personId, refreshPeople]);

  useEffect(() => {
    void refreshChatHistory(personId).catch((error) => {
      addEvent({
        title: "Could not load chat history",
        detail: error instanceof Error ? error.message : "Unknown history error",
        tone: "warning",
      });
    });
  }, [addEvent, personId, refreshChatHistory]);

  const onAgentResponse = useCallback(
    (response: AgentChatResponse) => {
      addEvent({
        title: "Agent responded",
        detail: response.behavior_label,
        tone: response.proposal ? "success" : "info",
      });
      void refreshChatHistory(response.person_id);
    },
    [addEvent, refreshChatHistory],
  );

  const onProposal = useCallback(
    (proposal: Proposal) => {
      setProposals((current) => [proposal, ...current.filter((item) => item.id !== proposal.id)]);
      addEvent({
        title: "Proposal drafted",
        detail: `${proposal.proposal_type}: ${proposal.summary}`,
        tone: "success",
      });
    },
    [addEvent],
  );

  const onRuntimeError = useCallback(
    (message: string) => {
      addEvent({
        title: "Agent call failed",
        detail: message,
        tone: "danger",
      });
    },
    [addEvent],
  );

  const runtime = useAgentRuntime({
    householdId,
    personId,
    activeMode,
    settings,
    onAgentResponse,
    onProposal,
    onRuntimeError,
  });

  const selectedTurn = useMemo(
    () => chatHistory.find((turn) => turn.id === selectedTurnId) ?? chatHistory[0] ?? null,
    [chatHistory, selectedTurnId],
  );

  const changePerson = (nextPersonId: string) => {
    setPersonId(nextPersonId);
    localStorage.setItem(STORAGE_KEYS.personId, nextPersonId);
    setSelectedTurnId(null);
  };

  const completeOnboarding = async (draft: OnboardingDraft) => {
    const { household, person } = await createInitialProfile(draft);
    setHouseholdId(household.id);
    setPersonId(person.id);
    await refreshPeople(household.id, person.id);
    addEvent({
      title: "Profile created",
      detail: `${person.name} in ${household.name}`,
      tone: "success",
    });
  };

  const handleProposalDecision = async (proposal: Proposal, decision: "confirm" | "reject") => {
    const updated =
      decision === "confirm" ? await confirmProposal(proposal.id) : await rejectProposal(proposal.id);
    setProposals((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    addEvent({
      title: decision === "confirm" ? "Proposal applied" : "Proposal rejected",
      detail: updated.summary,
      tone: decision === "confirm" ? "success" : "warning",
    });
    if (householdId) {
      await refreshPeople(householdId, personId);
    }
  };

  if (isBooting) {
    return <div className="boot-screen">Loading Health Monitor...</div>;
  }

  if (!householdId || !personId) {
    return <OnboardingScreen onCreate={completeOnboarding} />;
  }

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="app-shell">
        <aside className="left-rail" aria-label="App context and modes">
          <div className="brand-block">
            <p className="eyebrow">Health Monitor</p>
            <h1>Daily agent</h1>
            <p>Chat first. Structured proposals before durable changes.</p>
          </div>
          <ModesAndTemplates activeMode={activeMode} onModeChange={setActiveMode} />
          <ContextPanel
            people={people}
            personId={personId}
            settings={settings}
            onPersonChange={changePerson}
            onSettingsChange={setSettings}
          />
        </aside>

        <main className="chat-main" aria-label="Agent chat">
          <header className="chat-header">
            <div>
              <p className="eyebrow">Current mode</p>
              <h2>{CHAT_MODES.find((mode) => mode.id === activeMode)?.label}</h2>
            </div>
            <p>{CHAT_MODES.find((mode) => mode.id === activeMode)?.description}</p>
          </header>
          <ChatInterface />
        </main>

        <aside className="right-rail" aria-label="Activity and proposals">
          <ProposalPanel proposals={proposals} onDecision={handleProposalDecision} />
          <HistoryPanel
            turns={chatHistory}
            selectedTurn={selectedTurn}
            onSelect={(turnId) => setSelectedTurnId(turnId)}
          />
          <ActivityPanel events={events} />
        </aside>
      </div>
    </AssistantRuntimeProvider>
  );
}

function OnboardingScreen({ onCreate }: { onCreate: (draft: OnboardingDraft) => Promise<void> }) {
  const [message, setMessage] = useState(
    [
      "Household: Casa",
      "Name: Gabriel",
      "Timezone: America/Sao_Paulo",
      "Targets: 2000 kcal, 150g protein, 180g carbs, 70g fat",
      "Activity: moderate",
    ].join("\n"),
  );
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await onCreate(parseOnboardingMessage(message));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create the first profile");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="onboarding-screen">
      <section className="onboarding-chat" aria-label="Chat-first onboarding">
        <div className="assistant-bubble">
          <p className="eyebrow">First profile</p>
          <h1>Tell me who this is for.</h1>
          <p>
            Start with a normal note. Include household, name, timezone, and any target macros you
            know. You can change goals later through proposal-gated chat.
          </p>
        </div>
        <form className="onboarding-composer" onSubmit={submit}>
          <label htmlFor="onboarding-message">Message</label>
          <textarea
            id="onboarding-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            rows={8}
          />
          {error ? <p className="form-error">{error}</p> : null}
          <button type="submit" className="primary-action" disabled={isSubmitting}>
            {isSubmitting ? "Creating..." : "Create profile from message"}
          </button>
        </form>
      </section>
    </main>
  );
}

function ProposalPanel({
  proposals,
  onDecision,
}: {
  proposals: Proposal[];
  onDecision: (proposal: Proposal, decision: "confirm" | "reject") => Promise<void>;
}) {
  return (
    <section className="side-panel">
      <div className="section-heading">
        <span>Proposals</span>
        <strong>{proposals.filter((proposal) => proposal.status === "draft").length} draft</strong>
      </div>
      {proposals.length === 0 ? (
        <p className="empty-copy">Drafts from meals, labels, recipes, corrections, and goal changes appear here.</p>
      ) : (
        <div className="stack-list">
          {proposals.map((proposal) => (
            <article key={proposal.id} className="proposal-card">
              <div>
                <p className="eyebrow">{proposal.proposal_type}</p>
                <h3>{proposal.summary}</h3>
                <p>{proposalTotals(proposal)}</p>
              </div>
              <span className={`status-chip status-${proposal.status}`}>{proposal.status}</span>
              {proposal.status === "draft" ? (
                <div className="proposal-actions">
                  <button type="button" onClick={() => void onDecision(proposal, "reject")}>
                    Reject
                  </button>
                  <button
                    type="button"
                    className="primary-action"
                    onClick={() => void onDecision(proposal, "confirm")}
                  >
                    Confirm
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function HistoryPanel({
  turns,
  selectedTurn,
  onSelect,
}: {
  turns: AgentChatTurn[];
  selectedTurn: AgentChatTurn | null;
  onSelect: (turnId: string) => void;
}) {
  return (
    <section className="side-panel">
      <div className="section-heading">
        <span>History</span>
        <strong>{turns.length}</strong>
      </div>
      {turns.length === 0 ? (
        <p className="empty-copy">Previous agent turns will stay inspectable here.</p>
      ) : (
        <>
          <div className="history-list">
            {turns.slice(0, 8).map((turn) => (
              <button
                key={turn.id}
                type="button"
                className={turn.id === selectedTurn?.id ? "history-item is-active" : "history-item"}
                onClick={() => onSelect(turn.id)}
              >
                <span>{turn.user_message}</span>
                <small>{turn.behavior_label}</small>
              </button>
            ))}
          </div>
          {selectedTurn ? (
            <article className="selected-turn">
              <p className="eyebrow">Selected turn</p>
              <h3>{selectedTurn.user_message}</h3>
              <p>{selectedTurn.assistant_message}</p>
            </article>
          ) : null}
        </>
      )}
    </section>
  );
}

function ActivityPanel({ events }: { events: AppEvent[] }) {
  return (
    <section className="side-panel">
      <div className="section-heading">
        <span>Activity</span>
        <strong>{events.length}</strong>
      </div>
      {events.length === 0 ? (
        <p className="empty-copy">Runtime calls, errors, and proposal changes show up here.</p>
      ) : (
        <div className="stack-list">
          {events.map((event) => (
            <article key={event.id} className={`activity-item tone-${event.tone}`}>
              <strong>{event.title}</strong>
              <p>{event.detail}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function proposalTotals(proposal: Proposal): string {
  const totals = proposal.totals;
  if (!totals) {
    return "No nutrition totals on this proposal.";
  }
  return [
    totals.calories_kcal != null ? `${totals.calories_kcal} kcal` : null,
    totals.protein_g != null ? `${totals.protein_g}g protein` : null,
    totals.carbs_g != null ? `${totals.carbs_g}g carbs` : null,
    totals.fat_g != null ? `${totals.fat_g}g fat` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

export default App;
