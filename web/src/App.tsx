import { AssistantRuntimeProvider, useAssistantToolUI, type ThreadMessageLike } from "@assistant-ui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  confirmProposal,
  createInitialProfile,
  defaultAgentSettings,
  draftLabelScan,
  draftRecipe,
  loadChatHistory,
  loadPeople,
  loadProposals,
  logWeight,
  parseOnboardingMessage,
  rejectProposal,
  repeatMeal,
  resolveProposalClarification,
  restoreDiaryEntry,
  STORAGE_KEYS,
  todayIsoForTimezone,
  updateProposalEntry,
  uploadDataUrlAttachment,
} from "./api";
import { ChatInterface } from "./components/ChatInterface";
import { DayCard } from "./components/DayCard";
import { ContextPanel } from "./components/ManualInputs";
import { QuickActionRow, ReplayBanner } from "./components/ModesAndTemplates";
import { ProposalCard } from "./components/ProposalCard";
import { ProposalInbox } from "./components/ProposalInbox";
import { WeekCard } from "./components/WeekCard";
import { useAgentRuntime } from "./hooks/useAgentRuntime";
import { queryKeys } from "./queryKeys";
import type {
  AgentChatResponse,
  AgentSettings,
  OnboardingDraft,
  Person,
  Proposal,
  ProposalCandidate,
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
  const [settings, setSettings] = useState<AgentSettings>(() => defaultAgentSettings());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [weightOpen, setWeightOpen] = useState(false);
  const [recipeOpen, setRecipeOpen] = useState(false);
  const [labelOpen, setLabelOpen] = useState(false);
  const [repeatOpen, setRepeatOpen] = useState(false);
  const [proposalInboxOpen, setProposalInboxOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; action?: { label: string; onClick: () => void } } | null>(
    null,
  );
  const [pendingReplay, setPendingReplay] = useState<string | null>(null);
  const [inlineProposalIds, setInlineProposalIds] = useState<Set<string>>(() => new Set());
  const [selectedDay, setSelectedDay] = useState<string>(() => todayIsoForTimezone(undefined));

  const peopleQuery = useQuery({
    queryKey: queryKeys.people(householdId),
    queryFn: () => loadPeople(householdId ?? ""),
    enabled: householdId != null,
  });

  const people = peopleQuery.data ?? [];
  const activePerson = people.find((person) => person.id === personId) ?? people[0] ?? null;
  const selectedPersonId = activePerson?.id ?? personId;

  const lastResetPersonRef = useRef<string | null>(null);
  useEffect(() => {
    if (selectedPersonId && lastResetPersonRef.current !== selectedPersonId) {
      lastResetPersonRef.current = selectedPersonId;
      setSelectedDay(todayIsoForTimezone(activePerson?.timezone));
    }
  }, [activePerson?.timezone, selectedPersonId]);

  useEffect(() => {
    setToast(null);
  }, [selectedPersonId, selectedDay]);

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
      queryClient.invalidateQueries({ queryKey: ["weekSummary", selectedPersonId] }),
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
    if (response.behavior_label === "log_weight") {
      void invalidateDailyReadModels();
    }
  }, [invalidateDailyReadModels, markProposalInline, upsertProposal]);

  const onProposal = useCallback(
    (proposal: Proposal) => {
      upsertProposal(proposal);
      markProposalInline(proposal);
    },
    [markProposalInline, upsertProposal],
  );

  const showToast = useCallback((message: string) => setToast({ message }), []);

  const onRuntimeError = useCallback((message: string) => {
    showToast(message);
  }, [showToast]);

  const proposalDecision = useMutation({
    mutationFn: ({ proposal, decision }: { proposal: Proposal; decision: "confirm" | "reject" }) =>
      decision === "confirm" ? confirmProposal(proposal.id) : rejectProposal(proposal.id),
    onSuccess: async (proposal) => {
      upsertProposal(proposal);
      await invalidateDailyReadModels();
    },
    onError: (error) => showToast(error instanceof Error ? error.message : "Não foi possível atualizar a proposta."),
  });

  const proposalEntryUpdate = useMutation({
    mutationFn: ({ proposal, entry, quantityG }: { proposal: Proposal; entry: ProposalEntry; quantityG: number }) =>
      updateProposalEntry({ proposalId: proposal.id, entryId: entry.id, quantityG }),
    onSuccess: async (proposal) => {
      upsertProposal(proposal);
      await invalidateDailyReadModels();
    },
    onError: (error) => showToast(error instanceof Error ? error.message : "Não foi possível editar a proposta."),
  });

  const weightCreate = useMutation({
    mutationFn: (weightKg: number) => logWeight({ personId: selectedPersonId ?? "", weightKg }),
    onSuccess: async () => {
      setWeightOpen(false);
      showToast("Peso registrado.");
      await invalidateDailyReadModels();
    },
    onError: (error) => showToast(error instanceof Error ? error.message : "Não foi possível registrar o peso."),
  });

  const recipeDraft = useMutation({
    mutationFn: (recipeText: string) => {
      if (!householdId || !selectedPersonId) {
        throw new Error("Selecione uma casa e perfil antes de criar receita.");
      }
      return draftRecipe({ householdId, personId: selectedPersonId, text: recipeText });
    },
    onSuccess: async (proposal) => {
      setRecipeOpen(false);
      upsertProposal(proposal);
      showToast("Receita rascunhada para revisão.");
      await invalidateDailyReadModels();
    },
    onError: (error) => showToast(error instanceof Error ? error.message : "Não foi possível rascunhar a receita."),
  });

  const labelDraft = useMutation({
    mutationFn: async (input: { text: string; files: File[] }) => {
      if (!householdId || !selectedPersonId) {
        throw new Error("Selecione uma casa e perfil antes de escanear rótulo.");
      }
      const attachmentIds = [];
      for (const file of input.files) {
        const dataUrl = await fileToDataUrl(file);
        const attachment = await uploadDataUrlAttachment({
          householdId,
          personId: selectedPersonId,
          dataUrl,
          filename: file.name,
        });
        attachmentIds.push(attachment.id);
      }
      return draftLabelScan({
        householdId,
        personId: selectedPersonId,
        text: input.text,
        attachmentIds,
      });
    },
    onSuccess: async (proposal) => {
      setLabelOpen(false);
      upsertProposal(proposal);
      showToast("Rótulo rascunhado para revisão.");
      await invalidateDailyReadModels();
    },
    onError: (error) => showToast(error instanceof Error ? error.message : "Não foi possível rascunhar o rótulo."),
  });

  const repeatDraft = useMutation({
    mutationFn: (input: { sourceDay: string; mealType: string }) => {
      if (!selectedPersonId) {
        throw new Error("Selecione um perfil antes de repetir refeição.");
      }
      return repeatMeal({
        personId: selectedPersonId,
        sourceDay: input.sourceDay,
        mealType: input.mealType,
      });
    },
    onSuccess: async (proposal) => {
      setRepeatOpen(false);
      upsertProposal(proposal);
      showToast("Refeição repetida como proposta.");
      await invalidateDailyReadModels();
    },
    onError: (error) => showToast(error instanceof Error ? error.message : "Não foi possível repetir a refeição."),
  });

  const clarificationResolve = useMutation({
    mutationFn: ({
      proposal,
      unresolvedIndex,
      candidate,
    }: {
      proposal: Proposal;
      unresolvedIndex: number;
      candidate: ProposalCandidate;
    }) =>
      resolveProposalClarification({
        proposalId: proposal.id,
        unresolvedIndex,
        foodVersionId: candidate.food_version_id,
      }),
    onSuccess: async (proposal) => {
      upsertProposal(proposal);
      await invalidateDailyReadModels();
    },
    onError: (error) => showToast(error instanceof Error ? error.message : "Não foi possível resolver a proposta."),
  });

  const entryRestore = useMutation({
    mutationFn: (entryId: string) => restoreDiaryEntry(entryId),
    onSuccess: async () => {
      showToast("Item restaurado.");
      await invalidateDailyReadModels();
    },
    onError: (error) => showToast(error instanceof Error ? error.message : "Não foi possível desfazer a exclusão."),
  });

  const onEntryDeleted = useCallback(
    (entryId: string) => {
      setToast({
        message: "Item excluído.",
        action: { label: "Desfazer", onClick: () => entryRestore.mutate(entryId) },
      });
    },
    [entryRestore],
  );

  const activeDraft = (proposalsQuery.data ?? []).find((proposal) =>
    ["draft", "needs_clarification"].includes(proposal.status),
  );
  const fallbackDraft = activeDraft && !inlineProposalIds.has(activeDraft.id) ? activeDraft : undefined;

  const changePerson = (nextPersonId: string) => {
    setPersonId(nextPersonId);
    localStorage.setItem(STORAGE_KEYS.personId, nextPersonId);
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
          aria-label="Abrir propostas"
          onClick={() => setProposalInboxOpen(true)}
        >
          Propostas
        </button>
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
            today={selectedDay}
            settings={settings}
            initialMessages={initialMessages}
            proposal={fallbackDraft}
            proposals={proposalsQuery.data ?? []}
            proposalBusy={proposalDecision.isPending || proposalEntryUpdate.isPending}
            onRepeatClick={() => setRepeatOpen(true)}
            onWeightClick={() => setWeightOpen(true)}
            onRecipeClick={() => setRecipeOpen(true)}
            onLabelClick={() => setLabelOpen(true)}
            onAgentResponse={onAgentResponse}
            onProposal={onProposal}
            onRuntimeError={onRuntimeError}
            pendingReplay={pendingReplay}
            onModelUnavailable={setPendingReplay}
            onReplayDismiss={() => setPendingReplay(null)}
            onConfirmProposal={(proposal) => proposalDecision.mutate({ proposal, decision: "confirm" })}
            onRejectProposal={(proposal) => proposalDecision.mutate({ proposal, decision: "reject" })}
            onUpdateProposalEntry={(proposal, entry, quantityG) =>
              proposalEntryUpdate.mutate({ proposal, entry, quantityG })
            }
            onResolveClarification={(proposal, unresolvedIndex, candidate) =>
              clarificationResolve.mutate({ proposal, unresolvedIndex, candidate })
            }
            onDayChange={setSelectedDay}
            onToast={showToast}
            onEntryDeleted={onEntryDeleted}
          />
        ) : (
          <section className="chat-column" aria-label="Conversa">
            <DayCard
              personId={selectedPersonId}
              day={selectedDay}
              onDayChange={setSelectedDay}
              onToast={showToast}
              onEntryDeleted={onEntryDeleted}
            />
            <div className="chat-loading" role="status">
              Carregando conversa...
            </div>
          </section>
        )}

        <aside className="desktop-read-column" aria-label="Resumo do dia">
          <DayCard
            personId={selectedPersonId}
            day={selectedDay}
            onDayChange={setSelectedDay}
            onToast={showToast}
            onEntryDeleted={onEntryDeleted}
          />
          <WeekCard personId={selectedPersonId} day={selectedDay} />
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

      {weightOpen ? (
        <WeightModal
          busy={weightCreate.isPending}
          onClose={() => setWeightOpen(false)}
          onSubmit={(weightKg) => weightCreate.mutate(weightKg)}
        />
      ) : null}

      {repeatOpen ? (
        <RepeatMealModal
          busy={repeatDraft.isPending}
          today={selectedDay}
          onClose={() => setRepeatOpen(false)}
          onSubmit={(input) => repeatDraft.mutate(input)}
        />
      ) : null}

      {recipeOpen ? (
        <RecipeModal
          busy={recipeDraft.isPending}
          onClose={() => setRecipeOpen(false)}
          onSubmit={(recipeText) => recipeDraft.mutate(recipeText)}
        />
      ) : null}

      {labelOpen ? (
        <LabelScanModal
          busy={labelDraft.isPending}
          onClose={() => setLabelOpen(false)}
          onSubmit={(input) => labelDraft.mutate(input)}
        />
      ) : null}

      {proposalInboxOpen ? (
        <ProposalInbox
          proposals={proposalsQuery.data ?? []}
          busy={proposalDecision.isPending || proposalEntryUpdate.isPending || clarificationResolve.isPending}
          onClose={() => setProposalInboxOpen(false)}
          onConfirm={(proposal) => proposalDecision.mutate({ proposal, decision: "confirm" })}
          onReject={(proposal) => proposalDecision.mutate({ proposal, decision: "reject" })}
          onUpdateEntry={(proposal, entry, quantityG) => proposalEntryUpdate.mutate({ proposal, entry, quantityG })}
          onResolveClarification={(proposal, unresolvedIndex, candidate) =>
            clarificationResolve.mutate({ proposal, unresolvedIndex, candidate })
          }
        />
      ) : null}

      {toast ? (
        <div className="toast" role="status" aria-live="polite">
          <span>{toast.message}</span>
          {toast.action ? (
            <button
              type="button"
              className="primary-action"
              onClick={() => {
                toast.action?.onClick();
                setToast(null);
              }}
            >
              {toast.action.label}
            </button>
          ) : null}
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
  today,
  settings,
  initialMessages,
  proposal,
  proposals,
  proposalBusy,
  onRepeatClick,
  onWeightClick,
  onRecipeClick,
  onLabelClick,
  onAgentResponse,
  onProposal,
  onRuntimeError,
  pendingReplay,
  onModelUnavailable,
  onReplayDismiss,
  onConfirmProposal,
  onRejectProposal,
  onUpdateProposalEntry,
  onResolveClarification,
  onDayChange,
  onToast,
  onEntryDeleted,
}: {
  householdId: string | null;
  personId: string;
  today: string;
  settings: AgentSettings;
  initialMessages: readonly ThreadMessageLike[];
  proposal?: Proposal;
  proposals: Proposal[];
  proposalBusy: boolean;
  onRepeatClick: () => void;
  onWeightClick: () => void;
  onRecipeClick: () => void;
  onLabelClick: () => void;
  onAgentResponse: (response: AgentChatResponse) => void;
  onProposal: (proposal: Proposal) => void;
  onRuntimeError: (message: string) => void;
  pendingReplay: string | null;
  onModelUnavailable: (replayMessage: string) => void;
  onReplayDismiss: () => void;
  onConfirmProposal: (proposal: Proposal) => void;
  onRejectProposal: (proposal: Proposal) => void;
  onUpdateProposalEntry: (proposal: Proposal, entry: ProposalEntry, quantityG: number) => void;
  onResolveClarification: (proposal: Proposal, unresolvedIndex: number, candidate: ProposalCandidate) => void;
  onDayChange: (day: string) => void;
  onToast: (message: string) => void;
  onEntryDeleted: (entryId: string) => void;
}) {
  const runtime = useAgentRuntime({
    householdId,
    personId,
    today,
    settings,
    initialMessages,
    onAgentResponse,
    onProposal,
    onRuntimeError,
    onModelUnavailable,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ProposalToolRenderer
        proposals={proposals}
        busy={proposalBusy}
        onConfirm={onConfirmProposal}
        onReject={onRejectProposal}
        onUpdateEntry={onUpdateProposalEntry}
        onResolveClarification={onResolveClarification}
      />
      <section className="chat-column" aria-label="Conversa">
        <DayCard
          personId={personId}
          day={today}
          onDayChange={onDayChange}
          onToast={onToast}
          onEntryDeleted={onEntryDeleted}
        />
        <QuickActionRow
          onRepeatClick={onRepeatClick}
          onWeightClick={onWeightClick}
          onRecipeClick={onRecipeClick}
          onLabelClick={onLabelClick}
        />
        <ChatInterface />
        {pendingReplay ? (
          <ReplayBanner message={pendingReplay} onDismiss={onReplayDismiss} />
        ) : null}
        <DraftProposalDock
          proposal={proposal}
          busy={proposalBusy}
          onConfirm={onConfirmProposal}
          onReject={onRejectProposal}
          onUpdateEntry={onUpdateProposalEntry}
          onResolveClarification={onResolveClarification}
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
  onResolveClarification,
}: {
  proposals: Proposal[];
  busy: boolean;
  onConfirm: (proposal: Proposal) => void;
  onReject: (proposal: Proposal) => void;
  onUpdateEntry: (proposal: Proposal, entry: ProposalEntry, quantityG: number) => void;
  onResolveClarification: (proposal: Proposal, unresolvedIndex: number, candidate: ProposalCandidate) => void;
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
            onResolveClarification={onResolveClarification}
          />
        );
      },
    }),
    [busy, onConfirm, onReject, onResolveClarification, onUpdateEntry, proposalById],
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
  onResolveClarification,
}: {
  proposal?: Proposal;
  busy: boolean;
  onConfirm: (proposal: Proposal) => void;
  onReject: (proposal: Proposal) => void;
  onUpdateEntry: (proposal: Proposal, entry: ProposalEntry, quantityG: number) => void;
  onResolveClarification: (proposal: Proposal, unresolvedIndex: number, candidate: ProposalCandidate) => void;
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
        onResolveClarification={onResolveClarification}
      />
    </section>
  );
}

function WeightModal({
  busy,
  onClose,
  onSubmit,
}: {
  busy: boolean;
  onClose: () => void;
  onSubmit: (weightKg: number) => void;
}) {
  const [value, setValue] = useState("");
  const parsed = Number(value.replace(",", "."));
  const canSubmit = Number.isFinite(parsed) && parsed > 0;
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form
        className="small-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Registrar peso"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          if (canSubmit) {
            onSubmit(parsed);
          }
        }}
      >
        <div className="section-heading">
          <span>Registrar peso</span>
          <button type="button" onClick={onClose}>
            Fechar
          </button>
        </div>
        <label className="field">
          <span>Peso de hoje (kg)</span>
          <input
            autoFocus
            inputMode="decimal"
            value={value}
            placeholder="96,3"
            onChange={(event) => setValue(event.target.value)}
          />
        </label>
        <button type="submit" className="primary-action" disabled={busy || !canSubmit}>
          {busy ? "Registrando..." : "Registrar"}
        </button>
      </form>
    </div>
  );
}

function RepeatMealModal({
  busy,
  today,
  onClose,
  onSubmit,
}: {
  busy: boolean;
  today: string;
  onClose: () => void;
  onSubmit: (input: { sourceDay: string; mealType: string }) => void;
}) {
  const [sourceDay, setSourceDay] = useState(() => addDays(today, -1));
  const [mealType, setMealType] = useState("breakfast");
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form
        className="small-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Repetir refeição"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit({ sourceDay, mealType });
        }}
      >
        <div className="section-heading">
          <span>Repetir refeição</span>
          <button type="button" onClick={onClose}>
            Fechar
          </button>
        </div>
        <label className="field">
          <span>Dia de origem</span>
          <input type="date" value={sourceDay} onChange={(event) => setSourceDay(event.target.value)} />
        </label>
        <label className="field">
          <span>Refeição</span>
          <select value={mealType} onChange={(event) => setMealType(event.target.value)}>
            <option value="breakfast">Café</option>
            <option value="lunch">Almoço</option>
            <option value="snack">Lanche</option>
            <option value="dinner">Jantar</option>
          </select>
        </label>
        <button type="submit" className="primary-action" disabled={busy || !sourceDay}>
          {busy ? "Rascunhando..." : "Rascunhar repetição"}
        </button>
      </form>
    </div>
  );
}

function RecipeModal({
  busy,
  onClose,
  onSubmit,
}: {
  busy: boolean;
  onClose: () => void;
  onSubmit: (recipeText: string) => void;
}) {
  const [name, setName] = useState("");
  const [yieldG, setYieldG] = useState("");
  const [ingredients, setIngredients] = useState("");
  const canSubmit = name.trim() && ingredients.trim();
  const recipeText = [
    `Recipe: ${name.trim()}`,
    yieldG.trim() ? `Yield: ${yieldG.trim()} g` : "",
    "Ingredients:",
    ingredients.trim(),
  ]
    .filter(Boolean)
    .join("\n");
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form
        className="small-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Criar receita ou lote"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          if (canSubmit) {
            onSubmit(recipeText);
          }
        }}
      >
        <div className="section-heading">
          <span>Receita/lote</span>
          <button type="button" onClick={onClose}>
            Fechar
          </button>
        </div>
        <label className="field">
          <span>Nome</span>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="iogurte lean+" />
        </label>
        <label className="field">
          <span>Rendimento total (g)</span>
          <input inputMode="decimal" value={yieldG} onChange={(event) => setYieldG(event.target.value)} placeholder="1000" />
        </label>
        <label className="field">
          <span>Ingredientes, um por linha</span>
          <textarea
            rows={7}
            value={ingredients}
            onChange={(event) => setIngredients(event.target.value)}
            placeholder={"500g iogurte\n30g whey\n100g morango"}
          />
        </label>
        <button type="submit" className="primary-action" disabled={busy || !canSubmit}>
          {busy ? "Rascunhando..." : "Rascunhar receita"}
        </button>
      </form>
    </div>
  );
}

function LabelScanModal({
  busy,
  onClose,
  onSubmit,
}: {
  busy: boolean;
  onClose: () => void;
  onSubmit: (input: { text: string; files: File[] }) => void;
}) {
  const [product, setProduct] = useState("");
  const [barcode, setBarcode] = useState("");
  const [tableText, setTableText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const text = [
    product.trim() ? `Produto: ${product.trim()}` : "",
    barcode.trim() ? `Código de barras: ${barcode.trim()}` : "",
    tableText.trim(),
  ]
    .filter(Boolean)
    .join("\n");
  const canSubmit = text.trim() || files.length > 0;
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form
        className="small-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Escanear rótulo"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          if (canSubmit) {
            onSubmit({ text, files });
          }
        }}
      >
        <div className="section-heading">
          <span>Escanear rótulo</span>
          <button type="button" onClick={onClose}>
            Fechar
          </button>
        </div>
        <label className="field">
          <span>Fotos do rótulo</span>
          <input
            type="file"
            accept="image/*"
            multiple
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
        </label>
        <label className="field">
          <span>Produto</span>
          <input value={product} onChange={(event) => setProduct(event.target.value)} placeholder="Iogurte Batavo" />
        </label>
        <label className="field">
          <span>Código de barras</span>
          <input inputMode="numeric" value={barcode} onChange={(event) => setBarcode(event.target.value)} />
        </label>
        <label className="field">
          <span>Tabela colada (opcional)</span>
          <textarea rows={6} value={tableText} onChange={(event) => setTableText(event.target.value)} />
        </label>
        <button type="submit" className="primary-action" disabled={busy || !canSubmit}>
          {busy ? "Rascunhando..." : "Rascunhar rótulo"}
        </button>
      </form>
    </div>
  );
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Não foi possível ler o arquivo."));
    reader.readAsDataURL(file);
  });
}

function addDays(day: string, delta: number): string {
  const date = new Date(`${day}T12:00:00`);
  date.setDate(date.getDate() + delta);
  return date.toISOString().slice(0, 10);
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
