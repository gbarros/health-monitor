import { AssistantRuntimeProvider, type ThreadMessageLike } from "@assistant-ui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useCallback, useMemo, useState } from "react";
import {
  confirmProposal,
  createInitialProfile,
  defaultAgentSettings,
  loadChatHistory,
  loadPeople,
  loadProposals,
  parseOnboardingMessage,
  rejectProposal,
  STORAGE_KEYS,
  todayIsoForTimezone,
} from "./api";
import { ChatInterface } from "./components/ChatInterface";
import { DayCard } from "./components/DayCard";
import { ContextPanel } from "./components/ManualInputs";
import { QuickActionRow } from "./components/ModesAndTemplates";
import { useAgentRuntime } from "./hooks/useAgentRuntime";
import { queryKeys } from "./queryKeys";
import type {
  AgentChatResponse,
  AgentSettings,
  ModeId,
  OnboardingDraft,
  Person,
  Proposal,
} from "./types";

function App() {
  const queryClient = useQueryClient();
  const [householdId, setHouseholdId] = useState<string | null>(() =>
    localStorage.getItem(STORAGE_KEYS.householdId),
  );
  const [personId, setPersonId] = useState<string | null>(() =>
    localStorage.getItem(STORAGE_KEYS.personId),
  );
  const [activeMode, setActiveMode] = useState<ModeId>("general_chat");
  const [settings, setSettings] = useState<AgentSettings>(() => defaultAgentSettings());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const peopleQuery = useQuery({
    queryKey: queryKeys.people(householdId),
    queryFn: () => loadPeople(householdId ?? ""),
    enabled: householdId != null,
  });

  const people = peopleQuery.data ?? [];
  const activePerson = people.find((person) => person.id === personId) ?? people[0] ?? null;
  const selectedPersonId = activePerson?.id ?? personId;
  const selectedDay = todayIsoForTimezone(activePerson?.timezone);

  const proposalsQuery = useQuery({
    queryKey: queryKeys.proposals(selectedPersonId),
    queryFn: () => loadProposals(selectedPersonId ?? ""),
    enabled: selectedPersonId != null,
  });

  const chatHistoryQuery = useQuery({
    queryKey: queryKeys.chatHistory(selectedPersonId),
    queryFn: () => loadChatHistory(selectedPersonId ?? ""),
    enabled: selectedPersonId != null,
  });

  const initialMessages = useMemo<ThreadMessageLike[]>(
    () =>
      (chatHistoryQuery.data ?? []).flatMap((turn) => [
        {
          role: "user" as const,
          content: [{ type: "text" as const, text: turn.user_message }],
        },
        {
          role: "assistant" as const,
          content: [{ type: "text" as const, text: turn.assistant_message }],
        },
      ]),
    [chatHistoryQuery.data],
  );

  const invalidateDailyReadModels = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.daySummary(selectedPersonId, selectedDay) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.activeGoal(selectedPersonId, selectedDay) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.weightTrend(selectedPersonId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.proposals(selectedPersonId) }),
    ]);
  }, [queryClient, selectedDay, selectedPersonId]);

  const upsertProposal = useCallback(
    (proposal: Proposal) => {
      queryClient.setQueryData<Proposal[]>(queryKeys.proposals(proposal.person_id), (current = []) => [
        proposal,
        ...current.filter((item) => item.id !== proposal.id),
      ]);
    },
    [queryClient],
  );

  const onAgentResponse = useCallback((response: AgentChatResponse) => {
    if (response.proposal) {
      upsertProposal(response.proposal);
    }
  }, [upsertProposal]);

  const onProposal = useCallback(
    (proposal: Proposal) => {
      upsertProposal(proposal);
    },
    [upsertProposal],
  );

  const onRuntimeError = useCallback((message: string) => {
    setToast(message);
  }, []);

  const proposalDecision = useMutation({
    mutationFn: ({ proposal, decision }: { proposal: Proposal; decision: "confirm" | "reject" }) =>
      decision === "confirm" ? confirmProposal(proposal.id) : rejectProposal(proposal.id),
    onSuccess: async (proposal) => {
      upsertProposal(proposal);
      await invalidateDailyReadModels();
    },
    onError: (error) => setToast(error instanceof Error ? error.message : "Não foi possível atualizar a proposta."),
  });

  const activeDraft = (proposalsQuery.data ?? []).find((proposal) =>
    ["draft", "needs_clarification"].includes(proposal.status),
  );

  const changePerson = (nextPersonId: string) => {
    setPersonId(nextPersonId);
    localStorage.setItem(STORAGE_KEYS.personId, nextPersonId);
    setActiveMode("general_chat");
  };

  const completeOnboarding = async (draft: OnboardingDraft) => {
    const { household, person } = await createInitialProfile(draft);
    setHouseholdId(household.id);
    setPersonId(person.id);
    await queryClient.invalidateQueries({ queryKey: queryKeys.people(household.id) });
  };

  if (!householdId || !selectedPersonId || !activePerson) {
    return <OnboardingScreen onCreate={completeOnboarding} />;
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <p className="eyebrow">Health Monitor</p>
          <h1>Diário</h1>
        </div>
        <PersonChips people={people} activePersonId={selectedPersonId} onChange={changePerson} />
        <button
          type="button"
          className="icon-button"
          aria-label="Abrir ajustes do agente"
          onClick={() => setSettingsOpen(true)}
        >
          Ajustes
        </button>
      </header>

      <main className="daily-layout">
        {chatHistoryQuery.isSuccess ? (
          <ChatWorkspace
            key={selectedPersonId}
            householdId={householdId}
            personId={selectedPersonId}
            activeMode={activeMode}
            today={selectedDay}
            settings={settings}
            initialMessages={initialMessages}
            proposal={activeDraft}
            proposalBusy={proposalDecision.isPending}
            onModeChange={setActiveMode}
            onToast={setToast}
            onAgentResponse={onAgentResponse}
            onProposal={onProposal}
            onRuntimeError={onRuntimeError}
            onModeCompleted={() => setActiveMode("general_chat")}
            onConfirmProposal={(proposal) => proposalDecision.mutate({ proposal, decision: "confirm" })}
            onRejectProposal={(proposal) => proposalDecision.mutate({ proposal, decision: "reject" })}
          />
        ) : (
          <section className="chat-column" aria-label="Conversa">
            <DayCard personId={selectedPersonId} day={selectedDay} />
            <div className="chat-loading" role="status">
              Carregando conversa...
            </div>
          </section>
        )}

        <aside className="desktop-read-column" aria-label="Resumo do dia">
          <DayCard personId={selectedPersonId} day={selectedDay} />
          <section className="week-placeholder">
            <p className="eyebrow">Semana</p>
            <p>Visão semanal entra na fase 5.</p>
          </section>
        </aside>
      </main>

      {settingsOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setSettingsOpen(false)}>
          <div
            className="settings-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Ajustes do agente"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="section-heading">
              <span>Ajustes do agente</span>
              <button type="button" onClick={() => setSettingsOpen(false)}>
                Fechar
              </button>
            </div>
            <ContextPanel
              people={people}
              personId={selectedPersonId}
              settings={settings}
              onPersonChange={changePerson}
              onSettingsChange={setSettings}
            />
          </div>
        </div>
      ) : null}

      {toast ? (
        <div className="toast" role="status" aria-live="polite">
          <span>{toast}</span>
          <button type="button" onClick={() => setToast(null)}>
            Fechar
          </button>
        </div>
      ) : null}
    </div>
  );
}

function ChatWorkspace({
  householdId,
  personId,
  activeMode,
  today,
  settings,
  initialMessages,
  proposal,
  proposalBusy,
  onModeChange,
  onToast,
  onAgentResponse,
  onProposal,
  onRuntimeError,
  onModeCompleted,
  onConfirmProposal,
  onRejectProposal,
}: {
  householdId: string | null;
  personId: string;
  activeMode: ModeId;
  today: string;
  settings: AgentSettings;
  initialMessages: readonly ThreadMessageLike[];
  proposal?: Proposal;
  proposalBusy: boolean;
  onModeChange: (mode: ModeId) => void;
  onToast: (message: string) => void;
  onAgentResponse: (response: AgentChatResponse) => void;
  onProposal: (proposal: Proposal) => void;
  onRuntimeError: (message: string) => void;
  onModeCompleted: () => void;
  onConfirmProposal: (proposal: Proposal) => void;
  onRejectProposal: (proposal: Proposal) => void;
}) {
  const runtime = useAgentRuntime({
    householdId,
    personId,
    activeMode,
    today,
    settings,
    initialMessages,
    onAgentResponse,
    onProposal,
    onRuntimeError,
    onModeCompleted,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <section className="chat-column" aria-label="Conversa">
        <DayCard personId={personId} day={today} />
        <QuickActionRow onModeChange={onModeChange} onToast={onToast} />
        <ChatInterface />
        <DraftProposalDock
          proposal={proposal}
          busy={proposalBusy}
          onConfirm={onConfirmProposal}
          onReject={onRejectProposal}
        />
      </section>
    </AssistantRuntimeProvider>
  );
}

function PersonChips({
  people,
  activePersonId,
  onChange,
}: {
  people: Person[];
  activePersonId: string;
  onChange: (personId: string) => void;
}) {
  return (
    <div className="person-chips" aria-label="Selecionar perfil">
      {people.map((person) => (
        <button
          key={person.id}
          type="button"
          className={person.id === activePersonId ? "person-chip is-active" : "person-chip"}
          onClick={() => onChange(person.id)}
          aria-pressed={person.id === activePersonId}
        >
          <span>{person.name.slice(0, 1).toLocaleUpperCase("pt-BR")}</span>
          {person.name}
        </button>
      ))}
    </div>
  );
}

function DraftProposalDock({
  proposal,
  busy,
  onConfirm,
  onReject,
}: {
  proposal?: Proposal;
  busy: boolean;
  onConfirm: (proposal: Proposal) => void;
  onReject: (proposal: Proposal) => void;
}) {
  if (!proposal) {
    return null;
  }
  const canConfirm = proposal.status === "draft";
  return (
    <section className="draft-dock" aria-label="Proposta pendente">
      <div>
        <p className="eyebrow">Proposta</p>
        <h3>{proposal.summary}</h3>
        <p>{proposalTotals(proposal)}</p>
      </div>
      <div className="proposal-actions">
        <button type="button" onClick={() => onReject(proposal)} disabled={busy}>
          Rejeitar
        </button>
        <button type="button" className="primary-action" onClick={() => onConfirm(proposal)} disabled={busy || !canConfirm}>
          {canConfirm ? "Confirmar" : "Precisa revisar"}
        </button>
      </div>
    </section>
  );
}

function OnboardingScreen({ onCreate }: { onCreate: (draft: OnboardingDraft) => Promise<void> }) {
  const exampleMessage = [
    "Somos a Casa.",
    "Meu nome é Gabriel e meu fuso é America/Sao_Paulo.",
    "Por enquanto use metas de 2000 kcal, 150g proteína, 180g carboidratos, 70g gordura, 30g fibra e 2300mg sódio.",
    "Minha atividade é moderada.",
  ].join("\n");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!message.trim()) {
      setError("Escreva uma mensagem curta para criar o primeiro perfil.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await onCreate(parseOnboardingMessage(message));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível criar o primeiro perfil.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="onboarding-screen">
      <section className="onboarding-chat" aria-label="Cadastro por conversa">
        <div className="onboarding-thread">
          <div className="assistant-bubble">
            <p className="eyebrow">Primeiro perfil</p>
            <h1>Vamos começar pelo básico.</h1>
            <p>
              Me diga quem vai usar este diário e, se já souber, as metas iniciais. Pode ser texto livre;
              depois qualquer ajuste de perfil ou meta vira proposta no chat.
            </p>
          </div>
        </div>
        <div className="onboarding-example-row">
          <button type="button" onClick={() => setMessage(exampleMessage)}>
            Usar exemplo editável
          </button>
        </div>
        <form className="onboarding-composer" onSubmit={submit}>
          <label htmlFor="onboarding-message">Sua mensagem</label>
          <textarea
            id="onboarding-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            rows={8}
            placeholder="Ex.: Somos a Casa. Meu nome é Gabriel, fuso America/Sao_Paulo. Quero começar com 2000 kcal, 150g proteína..."
          />
          <p className="onboarding-helper">
            A criação inicial é direta para destravar o app. Depois disso, mudanças passam por propostas confirmáveis.
          </p>
          {error ? <p className="form-error">{error}</p> : null}
          <button type="submit" className="primary-action" disabled={isSubmitting}>
            {isSubmitting ? "Criando..." : "Criar primeiro perfil"}
          </button>
        </form>
      </section>
    </main>
  );
}

function proposalTotals(proposal: Proposal): string {
  const totals = proposal.totals;
  if (!totals) {
    return "Sem totais nutricionais nesta proposta.";
  }
  return [
    totals.calories_kcal != null ? `${Math.round(totals.calories_kcal)} kcal` : null,
    totals.protein_g != null ? `${Math.round(totals.protein_g)}g prot` : null,
    totals.carbs_g != null ? `${Math.round(totals.carbs_g)}g carb` : null,
    totals.fat_g != null ? `${Math.round(totals.fat_g)}g gord` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

export default App;
