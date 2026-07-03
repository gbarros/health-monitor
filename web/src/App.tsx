import { AssistantRuntimeProvider, useAssistantToolUI, type ThreadMessageLike } from "@assistant-ui/react";
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
  updateProposalEntry,
} from "./api";
import { ChatInterface } from "./components/ChatInterface";
import { DayCard } from "./components/DayCard";
import { ContextPanel } from "./components/ManualInputs";
import { QuickActionRow } from "./components/ModesAndTemplates";
import { ProposalCard } from "./components/ProposalCard";
import { useAgentRuntime } from "./hooks/useAgentRuntime";
import { queryKeys } from "./queryKeys";
import type {
  AgentChatResponse,
  AgentSettings,
  ModeId,
  OnboardingDraft,
  Person,
  Proposal,
  ProposalEntry,
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
  const [inlineProposalIds, setInlineProposalIds] = useState<Set<string>>(() => new Set());

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
      queryClient.setQueryData<Proposal[]>(queryKeys.proposals(proposal.person_id), (current = []) => {
        const supersededId =
          typeof proposal.payload?.["amended_from_proposal_id"] === "string"
            ? proposal.payload["amended_from_proposal_id"]
            : null;
        const currentWithSuperseded = current.map((item) =>
          supersededId != null && item.id === supersededId
            ? {
                ...item,
                status: "superseded",
                payload: { ...(item.payload ?? {}), superseded_by_proposal_id: proposal.id },
              }
            : item,
        );
        return [proposal, ...currentWithSuperseded.filter((item) => item.id !== proposal.id)];
      });
    },
    [queryClient],
  );

  const markProposalInline = useCallback((proposal: Proposal) => {
    setInlineProposalIds((current) => new Set(current).add(proposal.id));
  }, []);

  const onAgentResponse = useCallback((response: AgentChatResponse) => {
    if (response.proposal) {
      upsertProposal(response.proposal);
      markProposalInline(response.proposal);
    }
  }, [markProposalInline, upsertProposal]);

  const onProposal = useCallback(
    (proposal: Proposal) => {
      upsertProposal(proposal);
      markProposalInline(proposal);
    },
    [markProposalInline, upsertProposal],
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

  const proposalEntryUpdate = useMutation({
    mutationFn: ({ proposal, entry, quantityG }: { proposal: Proposal; entry: ProposalEntry; quantityG: number }) =>
      updateProposalEntry({ proposalId: proposal.id, entryId: entry.id, quantityG }),
    onSuccess: async (proposal) => {
      upsertProposal(proposal);
      await invalidateDailyReadModels();
    },
    onError: (error) => setToast(error instanceof Error ? error.message : "Não foi possível editar a proposta."),
  });

  const activeDraft = (proposalsQuery.data ?? []).find((proposal) =>
    ["draft", "needs_clarification"].includes(proposal.status),
  );
  const fallbackDraft = activeDraft && !inlineProposalIds.has(activeDraft.id) ? activeDraft : undefined;

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
            proposal={fallbackDraft}
            openDraftProposalId={activeDraft?.status === "draft" ? activeDraft.id : null}
            proposals={proposalsQuery.data ?? []}
            proposalBusy={proposalDecision.isPending || proposalEntryUpdate.isPending}
            onModeChange={setActiveMode}
            onToast={setToast}
            onAgentResponse={onAgentResponse}
            onProposal={onProposal}
            onRuntimeError={onRuntimeError}
            onModeCompleted={() => setActiveMode("general_chat")}
            onConfirmProposal={(proposal) => proposalDecision.mutate({ proposal, decision: "confirm" })}
            onRejectProposal={(proposal) => proposalDecision.mutate({ proposal, decision: "reject" })}
            onUpdateProposalEntry={(proposal, entry, quantityG) =>
              proposalEntryUpdate.mutate({ proposal, entry, quantityG })
            }
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
  proposals,
  openDraftProposalId,
  proposalBusy,
  onModeChange,
  onToast,
  onAgentResponse,
  onProposal,
  onRuntimeError,
  onModeCompleted,
  onConfirmProposal,
  onRejectProposal,
  onUpdateProposalEntry,
}: {
  householdId: string | null;
  personId: string;
  activeMode: ModeId;
  today: string;
  settings: AgentSettings;
  initialMessages: readonly ThreadMessageLike[];
  proposal?: Proposal;
  proposals: Proposal[];
  openDraftProposalId: string | null;
  proposalBusy: boolean;
  onModeChange: (mode: ModeId) => void;
  onToast: (message: string) => void;
  onAgentResponse: (response: AgentChatResponse) => void;
  onProposal: (proposal: Proposal) => void;
  onRuntimeError: (message: string) => void;
  onModeCompleted: () => void;
  onConfirmProposal: (proposal: Proposal) => void;
  onRejectProposal: (proposal: Proposal) => void;
  onUpdateProposalEntry: (proposal: Proposal, entry: ProposalEntry, quantityG: number) => void;
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
    openDraftProposalId,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ProposalToolRenderer
        proposals={proposals}
        busy={proposalBusy}
        onConfirm={onConfirmProposal}
        onReject={onRejectProposal}
        onUpdateEntry={onUpdateProposalEntry}
      />
      <section className="chat-column" aria-label="Conversa">
        <DayCard personId={personId} day={today} />
        <QuickActionRow onModeChange={onModeChange} onToast={onToast} />
        <ChatInterface />
        <DraftProposalDock
          proposal={proposal}
          busy={proposalBusy}
          onConfirm={onConfirmProposal}
          onReject={onRejectProposal}
          onUpdateEntry={onUpdateProposalEntry}
        />
      </section>
    </AssistantRuntimeProvider>
  );
}

function ProposalToolRenderer({
  proposals,
  busy,
  onConfirm,
  onReject,
  onUpdateEntry,
}: {
  proposals: Proposal[];
  busy: boolean;
  onConfirm: (proposal: Proposal) => void;
  onReject: (proposal: Proposal) => void;
  onUpdateEntry: (proposal: Proposal, entry: ProposalEntry, quantityG: number) => void;
}) {
  const proposalById = useMemo(() => new Map(proposals.map((proposal) => [proposal.id, proposal])), [proposals]);
  const tool = useMemo(
    () => ({
      toolName: "draft_proposal",
      display: "standalone" as const,
      render: ({ args, result }: { args?: { proposal?: Proposal }; result?: { proposal?: Proposal } }) => {
        const rawProposal = result?.proposal ?? args?.proposal;
        const proposal = rawProposal ? proposalById.get(rawProposal.id) ?? rawProposal : null;
        if (!proposal) {
          return null;
        }
        return (
          <ProposalCard
            proposal={proposal}
            busy={busy}
            onConfirm={onConfirm}
            onReject={onReject}
            onEntryQuantityChange={onUpdateEntry}
          />
        );
      },
    }),
    [busy, onConfirm, onReject, onUpdateEntry, proposalById],
  );
  useAssistantToolUI(tool);
  return null;
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
  onUpdateEntry,
}: {
  proposal?: Proposal;
  busy: boolean;
  onConfirm: (proposal: Proposal) => void;
  onReject: (proposal: Proposal) => void;
  onUpdateEntry: (proposal: Proposal, entry: ProposalEntry, quantityG: number) => void;
}) {
  if (!proposal) {
    return null;
  }
  return (
    <section className="draft-dock" aria-label="Proposta pendente">
      <ProposalCard
        proposal={proposal}
        busy={busy}
        onConfirm={onConfirm}
        onReject={onReject}
        onEntryQuantityChange={onUpdateEntry}
      />
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

export default App;
