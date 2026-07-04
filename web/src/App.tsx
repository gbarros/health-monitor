import { AssistantRuntimeProvider, useAssistantToolUI, type ThreadMessageLike } from "@assistant-ui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReadonlyJSONObject } from "assistant-stream/utils";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  ApiError,
  confirmProposal,
  defaultAgentSettings,
  loadActiveGoal,
  loadDaySummary,
  loadChatHistory,
  loadDiaryRange,
  loadJobs,
  loadOnboardingHistory,
  loadPeople,
  loadProposal,
  loadProposals,
  logWeight,
  rejectProposal,
  resolveProposalClarification,
  restoreDiaryEntry,
  sendAgentChat,
  STORAGE_KEYS,
  todayIsoForTimezone,
  updateProposalEntry,
  uploadDataUrlAttachment,
} from "./api";
import { ChatInterface } from "./components/ChatInterface";
import { DayCard } from "./components/DayCard";
import { FoodLibraryDrawer } from "./components/FoodLibraryDrawer";
import { JobsSheet } from "./components/JobsSheet";
import { ContextPanel, DataPortabilityPanel } from "./components/ManualInputs";
import { QuickActionRow, ReplayBanner } from "./components/ModesAndTemplates";
import { ProposalCard } from "./components/ProposalCard";
import { ProposalInbox } from "./components/ProposalInbox";
import { WeekCard } from "./components/WeekCard";
import { useAgentRuntime } from "./hooks/useAgentRuntime";
import { useOnboardingRuntime } from "./hooks/useOnboardingRuntime";
import { enqueue, forPerson, readOutbox, removeById, writeOutbox, clearForPerson } from "./outbox";
import type { OutboxItem } from "./outbox";
import { queryKeys } from "./queryKeys";
import type {
  AgentChatResponse,
  AgentChatTurn,
  AgentSettings,
  BackgroundJob,
  DaySummaryEntry,
  OnboardingTurn,
  Person,
  Proposal,
  ProposalCandidate,
  ProposalEntry,
} from "./types";

type AppView = "chat" | "panel" | "data" | "settings";

const TOP_LEVEL_VIEWS: readonly AppView[] = ["chat", "panel", "data", "settings"];

function App() {
  const queryClient = useQueryClient();
  const location = useLocation();
  const activeView = viewFromPath(location.pathname);
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
  const [foodLibraryOpen, setFoodLibraryOpen] = useState(false);
  const [jobsSheetOpen, setJobsSheetOpen] = useState(false);
  const [addingPerson, setAddingPerson] = useState(false);
  const [backgroundJobsEnabled, setBackgroundJobsEnabled] = useState(false);
  const [toast, setToast] = useState<{ message: string; action?: { label: string; onClick: () => void } } | null>(
    null,
  );
  const [inlineProposalIds, setInlineProposalIds] = useState<Set<string>>(() => new Set());
  const [selectedDay, setSelectedDayState] = useState<string>(
    () => localStorage.getItem(STORAGE_KEYS.selectedDay) ?? todayIsoForTimezone(undefined),
  );
  const setSelectedDay = useCallback((day: string) => {
    localStorage.setItem(STORAGE_KEYS.selectedDay, day);
    setSelectedDayState(day);
  }, []);
  const [outbox, setOutbox] = useState<OutboxItem[]>(() => readOutbox());
  const [outboxBannerDismissed, setOutboxBannerDismissed] = useState(false);
  const [outboxReplaying, setOutboxReplaying] = useState(false);
  const [chatReloadKey, setChatReloadKey] = useState(0);

  useEffect(() => {
    const onOnline = () => setOutboxBannerDismissed(false);
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, []);

  const peopleQuery = useQuery({
    queryKey: queryKeys.people(householdId),
    queryFn: () => loadPeople(householdId ?? ""),
    enabled: householdId != null,
  });

  const people = peopleQuery.data ?? [];
  const activePerson = people.find((person) => person.id === personId) ?? people[0] ?? null;
  const selectedPersonId = activePerson?.id ?? personId;

  const lastResetPersonRef = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    if (!selectedPersonId) {
      return;
    }
    const previous = lastResetPersonRef.current;
    lastResetPersonRef.current = selectedPersonId;
    if (previous !== undefined && previous !== selectedPersonId) {
      setSelectedDay(todayIsoForTimezone(activePerson?.timezone));
    }
  }, [activePerson?.timezone, selectedPersonId, setSelectedDay]);

  useEffect(() => {
    setToast(null);
  }, [selectedPersonId, selectedDay]);

  const proposalsQuery = useQuery({
    queryKey: queryKeys.proposals(selectedPersonId),
    queryFn: () => loadProposals(selectedPersonId ?? ""),
    enabled: selectedPersonId != null,
  });

  const jobsQuery = useQuery({
    queryKey: queryKeys.jobs(selectedPersonId),
    queryFn: () => loadJobs(selectedPersonId ?? ""),
    enabled: selectedPersonId != null,
    refetchInterval: (query) => {
      const jobs = query.state.data ?? [];
      return jobs.some((job) => job.status === "pending" || job.status === "running") ? 4000 : false;
    },
  });
  const activeJobCount = (jobsQuery.data ?? []).filter(
    (job) => job.status === "pending" || job.status === "running",
  ).length;

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
      queryClient.invalidateQueries({ queryKey: ["diaryRange", selectedPersonId] }),
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

  const onSendFailed = useCallback(
    (text: string, reason: "model_unavailable" | "network") => {
      if (!selectedPersonId) {
        return;
      }
      const item: OutboxItem = {
        id: `outbox-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        person_id: selectedPersonId,
        text,
        created_at: new Date().toISOString(),
        reason,
      };
      setOutbox((current) => {
        const next = enqueue(current, item);
        writeOutbox(next);
        return next;
      });
      setOutboxBannerDismissed(false);
    },
    [selectedPersonId],
  );

  const outboxForCurrentPerson = selectedPersonId ? forPerson(outbox, selectedPersonId) : [];

  const replayOutbox = useCallback(async () => {
    if (!selectedPersonId || outboxReplaying) {
      return;
    }
    setOutboxReplaying(true);
    try {
      for (const item of forPerson(outbox, selectedPersonId)) {
        try {
          const response = await sendAgentChat({
            personId: item.person_id,
            message: item.text,
            settings,
            today: selectedDay,
          });
          onAgentResponse(response);
          setOutbox((current) => {
            const next = removeById(current, item.id);
            writeOutbox(next);
            return next;
          });
          await queryClient.invalidateQueries({ queryKey: queryKeys.chatHistory(selectedPersonId) });
          setChatReloadKey((key) => key + 1);
        } catch (error) {
          const message =
            error instanceof ApiError
              ? error.message
              : error instanceof TypeError
                ? "Ainda sem conexão."
                : error instanceof Error
                  ? error.message
                  : "Falha desconhecida.";
          showToast(`Reenvio interrompido: ${message}`);
          break;
        }
      }
    } finally {
      setOutboxReplaying(false);
    }
  }, [onAgentResponse, outbox, outboxReplaying, queryClient, selectedDay, selectedPersonId, settings, showToast]);

  const discardOutbox = useCallback(() => {
    if (!selectedPersonId) {
      return;
    }
    setOutbox((current) => {
      const next = clearForPerson(current, selectedPersonId);
      writeOutbox(next);
      return next;
    });
  }, [selectedPersonId]);

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

  const promptBuilderSend = useMutation({
    mutationFn: async (input: {
      message: string;
      intent: "log_food" | "recipe" | "label_scan" | "repeat_meal";
      files?: File[];
    }) => {
      if (!householdId || !selectedPersonId) {
        throw new Error("Selecione uma casa e perfil antes de conversar com o agente.");
      }
      const attachmentIds = [];
      for (const file of input.files ?? []) {
        const dataUrl = await fileToDataUrl(file);
        const attachment = await uploadDataUrlAttachment({
          householdId,
          personId: selectedPersonId,
          dataUrl,
          filename: file.name,
        });
        attachmentIds.push(attachment.id);
      }
      return sendAgentChat({
        personId: selectedPersonId,
        message: input.message,
        intent: input.intent,
        settings,
        today: selectedDay,
        attachmentIds,
      });
    },
    onSuccess: async (response) => {
      onAgentResponse(response);
      setRecipeOpen(false);
      setLabelOpen(false);
      setRepeatOpen(false);
      showToast("Mensagem enviada ao agente.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.chatHistory(selectedPersonId) });
      setChatReloadKey((key) => key + 1);
      await invalidateDailyReadModels();
    },
    onError: (error) => showToast(error instanceof Error ? error.message : "Não foi possível enviar ao agente."),
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

  const onJobQueued = useCallback(
    (job: BackgroundJob) => {
      queryClient.setQueryData<BackgroundJob[]>(queryKeys.jobs(selectedPersonId), (current = []) => [
        job,
        ...current,
      ]);
    },
    [queryClient, selectedPersonId],
  );

  const openJobResult = useCallback(
    async (job: BackgroundJob) => {
      const proposalId = job.result?.["proposal_id"];
      if (typeof proposalId === "string") {
        try {
          const proposal = await loadProposal(proposalId);
          upsertProposal(proposal);
          setJobsSheetOpen(false);
          setProposalInboxOpen(true);
        } catch (error) {
          showToast(error instanceof Error ? error.message : "Não foi possível abrir a proposta do job.");
        }
        return;
      }
      if (typeof job.result?.["chat_turn_id"] === "string" && selectedPersonId) {
        await queryClient.invalidateQueries({ queryKey: queryKeys.chatHistory(selectedPersonId) });
        setChatReloadKey((key) => key + 1);
        setJobsSheetOpen(false);
        showToast("Resposta do chat atualizada.");
      }
    },
    [queryClient, selectedPersonId, showToast, upsertProposal],
  );

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

  const completeOnboarding = async (applied: Proposal) => {
    const payload = applied.payload ?? {};
    const nextHouseholdId = typeof payload.created_household_id === "string" ? payload.created_household_id : null;
    const nextPersonId = typeof payload.created_person_id === "string" ? payload.created_person_id : null;
    if (!nextHouseholdId || !nextPersonId) {
      throw new Error("A proposta aplicada não retornou os ids criados.");
    }
    localStorage.setItem(STORAGE_KEYS.householdId, nextHouseholdId);
    localStorage.setItem(STORAGE_KEYS.personId, nextPersonId);
    localStorage.removeItem(STORAGE_KEYS.onboardingSessionId);
    setHouseholdId(nextHouseholdId);
    setPersonId(nextPersonId);
    setAddingPerson(false);
    await queryClient.invalidateQueries({ queryKey: queryKeys.people(nextHouseholdId) });
  };

  if (addingPerson && householdId) {
    return (
      <OnboardingScreen
        householdId={householdId}
        onCancel={() => setAddingPerson(false)}
        onComplete={completeOnboarding}
      />
    );
  }

  if (!householdId || !selectedPersonId || !activePerson) {
    return <OnboardingScreen onComplete={completeOnboarding} />;
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <p className="eyebrow">Health Monitor</p>
          <h1>{viewTitle(activeView)}</h1>
        </div>
        <PersonChips
          people={people}
          activePersonId={selectedPersonId}
          onChange={changePerson}
          onAddPerson={() => setAddingPerson(true)}
        />
        <nav className="app-nav" aria-label="Navegação principal">
          {TOP_LEVEL_VIEWS.map((view) => (
            <NavLink
              key={view}
              to={viewPath(view)}
              className={({ isActive }) => {
                const active = isActive || (view === "chat" && location.pathname === "/");
                return active ? "nav-tab is-active" : "nav-tab";
              }}
              aria-current={view === activeView ? "page" : undefined}
            >
              {viewTitle(view)}
            </NavLink>
          ))}
        </nav>
        <div className="header-actions">
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
            aria-label="Abrir alimentos"
            onClick={() => setFoodLibraryOpen(true)}
          >
            Alimentos
          </button>
          <button
            type="button"
            className="icon-button"
            aria-label="Abrir tarefas"
            onClick={() => setJobsSheetOpen(true)}
          >
            Tarefas{activeJobCount > 0 ? <span className="badge-count">{activeJobCount}</span> : null}
          </button>
        </div>
      </header>

      <main className="app-main">
        {activeView === "chat" ? (
          chatHistoryQuery.isSuccess ? (
            <ChatWorkspace
              key={`${selectedPersonId}-${chatReloadKey}`}
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
              onSendFailed={onSendFailed}
              backgroundJobsEnabled={backgroundJobsEnabled}
              onJobQueued={onJobQueued}
              outboxCount={outboxForCurrentPerson.length}
              outboxBannerVisible={outboxForCurrentPerson.length > 0 && !outboxBannerDismissed}
              outboxReplaying={outboxReplaying}
              onOutboxReplay={replayOutbox}
              onOutboxDiscard={() => {
                discardOutbox();
                setOutboxBannerDismissed(true);
              }}
              onConfirmProposal={(proposal) => proposalDecision.mutate({ proposal, decision: "confirm" })}
              onRejectProposal={(proposal) => proposalDecision.mutate({ proposal, decision: "reject" })}
              onUpdateProposalEntry={(proposal, entry, quantityG) =>
                proposalEntryUpdate.mutate({ proposal, entry, quantityG })
              }
              onResolveClarification={(proposal, unresolvedIndex, candidate) =>
                clarificationResolve.mutate({ proposal, unresolvedIndex, candidate })
              }
              onDayChange={setSelectedDay}
            />
          ) : (
            <section className="chat-column" aria-label="Conversa">
              <div className="chat-loading" role="status">
                Carregando conversa...
              </div>
            </section>
          )
        ) : null}

        {activeView === "panel" ? (
          <section className="page-grid" aria-label="Painel">
          <DayCard
            personId={selectedPersonId}
            day={selectedDay}
            onDayChange={setSelectedDay}
            onToast={showToast}
            onEntryDeleted={onEntryDeleted}
          />
          <WeekCard personId={selectedPersonId} day={selectedDay} />
          </section>
        ) : null}

        {activeView === "data" ? (
          <DataPage
            personId={selectedPersonId}
            selectedDay={selectedDay}
            proposals={proposalsQuery.data ?? []}
            jobs={jobsQuery.data ?? []}
            turns={chatHistoryQuery.data ?? []}
          />
        ) : null}

        {activeView === "settings" ? (
          <section className="settings-page" aria-label="Ajustes">
            <ContextPanel
              people={people}
              personId={selectedPersonId}
              settings={settings}
              onPersonChange={changePerson}
              onSettingsChange={setSettings}
            />
            <label className="check-field">
              <input
                type="checkbox"
                checked={backgroundJobsEnabled}
                onChange={(event) => setBackgroundJobsEnabled(event.target.checked)}
              />
              <span>Processar em segundo plano</span>
            </label>
            <DataPortabilityPanel onToast={showToast} />
          </section>
        ) : null}
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
            <label className="check-field">
              <input
                type="checkbox"
                checked={backgroundJobsEnabled}
                onChange={(event) => setBackgroundJobsEnabled(event.target.checked)}
              />
              <span>Processar em segundo plano</span>
            </label>
            <DataPortabilityPanel onToast={showToast} />
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
          busy={promptBuilderSend.isPending}
          today={selectedDay}
          onClose={() => setRepeatOpen(false)}
          onSubmit={(message) => promptBuilderSend.mutate({ message, intent: "repeat_meal" })}
        />
      ) : null}

      {recipeOpen ? (
        <RecipeModal
          busy={promptBuilderSend.isPending}
          onClose={() => setRecipeOpen(false)}
          onSubmit={(message) => promptBuilderSend.mutate({ message, intent: "recipe" })}
        />
      ) : null}

      {labelOpen ? (
        <LabelScanModal
          busy={promptBuilderSend.isPending}
          onClose={() => setLabelOpen(false)}
          onSubmit={(input) =>
            promptBuilderSend.mutate({ message: input.message, files: input.files, intent: "label_scan" })
          }
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

      {foodLibraryOpen ? (
        <FoodLibraryDrawer
          householdId={householdId}
          personId={selectedPersonId}
          onClose={() => setFoodLibraryOpen(false)}
          onToast={showToast}
          onProposalDrafted={(proposal) => {
            upsertProposal(proposal);
            setFoodLibraryOpen(false);
            setProposalInboxOpen(true);
          }}
          onLoggedDirectly={() => {
            void invalidateDailyReadModels();
          }}
        />
      ) : null}

      {jobsSheetOpen && selectedPersonId ? (
        <JobsSheet
          personId={selectedPersonId}
          onClose={() => setJobsSheetOpen(false)}
          onToast={showToast}
          onOpenResult={openJobResult}
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
  onSendFailed,
  backgroundJobsEnabled,
  onJobQueued,
  outboxCount,
  outboxBannerVisible,
  outboxReplaying,
  onOutboxReplay,
  onOutboxDiscard,
  onConfirmProposal,
  onRejectProposal,
  onUpdateProposalEntry,
  onResolveClarification,
  onDayChange,
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
  onSendFailed: (text: string, reason: "model_unavailable" | "network") => void;
  backgroundJobsEnabled: boolean;
  onJobQueued: (job: BackgroundJob) => void;
  outboxCount: number;
  outboxBannerVisible: boolean;
  outboxReplaying: boolean;
  onOutboxReplay: () => void;
  onOutboxDiscard: () => void;
  onConfirmProposal: (proposal: Proposal) => void;
  onRejectProposal: (proposal: Proposal) => void;
  onUpdateProposalEntry: (proposal: Proposal, entry: ProposalEntry, quantityG: number) => void;
  onResolveClarification: (proposal: Proposal, unresolvedIndex: number, candidate: ProposalCandidate) => void;
  onDayChange: (day: string) => void;
}) {
  const runtime = useAgentRuntime({
    householdId,
    personId,
    today,
    settings,
    initialMessages,
    backgroundJobsEnabled,
    onAgentResponse,
    onProposal,
    onRuntimeError,
    onSendFailed,
    onJobQueued,
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
        <DaySummaryStrip personId={personId} day={today} onDayChange={onDayChange} />
        <QuickActionRow
          onRepeatClick={onRepeatClick}
          onWeightClick={onWeightClick}
          onRecipeClick={onRecipeClick}
          onLabelClick={onLabelClick}
        />
        <ChatInterface />
        {outboxBannerVisible ? (
          <ReplayBanner
            count={outboxCount}
            busy={outboxReplaying}
            onReplay={onOutboxReplay}
            onDiscardAll={onOutboxDiscard}
          />
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

function viewFromPath(pathname: string): AppView {
  if (pathname === "/panel") return "panel";
  if (pathname === "/data") return "data";
  if (pathname === "/settings") return "settings";
  return "chat";
}

function viewPath(view: AppView): string {
  if (view === "chat") return "/chat";
  return `/${view}`;
}

function viewTitle(view: AppView): string {
  if (view === "panel") return "Painel";
  if (view === "data") return "Dados";
  if (view === "settings") return "Ajustes";
  return "Chat";
}

function DaySummaryStrip({
  personId,
  day,
  onDayChange,
}: {
  personId: string;
  day: string;
  onDayChange: (day: string) => void;
}) {
  const summaryQuery = useQuery({
    queryKey: queryKeys.daySummary(personId, day),
    queryFn: () => loadDaySummary(personId, day),
  });
  const goalQuery = useQuery({
    queryKey: queryKeys.activeGoal(personId, day),
    queryFn: () => loadActiveGoal(personId, day),
  });
  const totals = summaryQuery.data?.totals;
  const target = summaryQuery.data?.target ?? goalQuery.data?.targets;
  const calories = Math.round(totals?.calories_kcal ?? 0);
  const calorieTarget = Math.round(target?.calories_kcal ?? 0);
  const remaining = calorieTarget > 0 ? calorieTarget - calories : null;
  return (
    <section className="day-summary-strip" aria-label="Resumo rápido do dia">
      <div>
        <strong>
          {calories}
          {calorieTarget > 0 ? ` / ${calorieTarget}` : ""} kcal
        </strong>
        <span>{remaining != null ? `Restante ${remaining}` : "Sem meta calórica ativa"}</span>
      </div>
      <div className="day-nav compact-day-nav">
        <button type="button" onClick={() => onDayChange(addDays(day, -1))} aria-label="Dia anterior">
          ‹
        </button>
        <label className="day-date-button">
          <span>{day}</span>
          <input type="date" value={day} onChange={(event) => onDayChange(event.target.value)} />
        </label>
        <button type="button" onClick={() => onDayChange(addDays(day, 1))} aria-label="Próximo dia">
          ›
        </button>
      </div>
    </section>
  );
}

function DataPage({
  personId,
  selectedDay,
  proposals,
  jobs,
  turns,
}: {
  personId: string;
  selectedDay: string;
  proposals: Proposal[];
  jobs: BackgroundJob[];
  turns: AgentChatTurn[];
}) {
  const [rangeStart, setRangeStart] = useState(selectedDay);
  const [rangeEnd, setRangeEnd] = useState(selectedDay);
  useEffect(() => {
    setRangeStart(selectedDay);
    setRangeEnd(selectedDay);
  }, [selectedDay]);
  const rangeQueryStart = rangeStart <= rangeEnd ? rangeStart : rangeEnd;
  const rangeQueryEnd = rangeStart <= rangeEnd ? rangeEnd : rangeStart;
  const diaryRangeQuery = useQuery({
    queryKey: queryKeys.diaryRange(personId, rangeQueryStart, rangeQueryEnd),
    queryFn: () => loadDiaryRange(personId, rangeQueryStart, rangeQueryEnd),
  });
  const entries = diaryRangeQuery.data ?? [];
  return (
    <section className="data-page" aria-label="Dados">
      <div className="data-range-controls" aria-label="Intervalo do diário">
        <label className="field">
          <span>Início</span>
          <input type="date" value={rangeStart} onChange={(event) => setRangeStart(event.target.value)} />
        </label>
        <label className="field">
          <span>Fim</span>
          <input type="date" value={rangeEnd} onChange={(event) => setRangeEnd(event.target.value)} />
        </label>
      </div>
      <DataTable
        title={
          rangeQueryStart === rangeQueryEnd
            ? `Diário de ${rangeQueryStart}`
            : `Diário de ${rangeQueryStart} a ${rangeQueryEnd}`
        }
        empty="Nenhum item registrado neste intervalo."
        columns={["Hora", "Refeição", "Alimento", "g", "kcal", "Fonte", "Conf."]}
        rows={entries.map((entry) => diaryEntryRow(entry))}
      />
      <DataTable
        title="Propostas"
        empty="Nenhuma proposta."
        columns={["Criada", "Tipo", "Status", "Resumo"]}
        rows={proposals.map((proposal) => [
          formatDateTime(proposal.created_at),
          proposal.proposal_type,
          proposal.status,
          proposal.summary,
        ])}
      />
      <DataTable
        title="Jobs"
        empty="Nenhuma tarefa."
        columns={["Criado", "Tipo", "Status", "Tentativas", "Erro"]}
        rows={jobs.map((job) => [formatDateTime(job.created_at), job.job_type, job.status, String(job.attempts), job.last_error ?? ""])}
      />
      <DataTable
        title="Chat turns"
        empty="Nenhuma conversa."
        columns={["Criado", "Usuário", "Agente", "Comportamento"]}
        rows={turns.map((turn) => [
          formatDateTime(turn.created_at),
          turn.user_message,
          turn.assistant_message,
          turn.behavior_label,
        ])}
      />
    </section>
  );
}

function DataTable({
  title,
  empty,
  columns,
  rows,
}: {
  title: string;
  empty: string;
  columns: string[];
  rows: string[][];
}) {
  const csv = [columns, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
  const download = () => {
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${title.toLocaleLowerCase("pt-BR").replace(/[^a-z0-9]+/gi, "-")}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return (
    <section className="data-section">
      <div className="section-heading">
        <span>{title}</span>
        <button type="button" onClick={download} disabled={rows.length === 0}>
          CSV
        </button>
      </div>
      {rows.length ? (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-copy">{empty}</p>
      )}
    </section>
  );
}

function diaryEntryRow(entry: DaySummaryEntry): string[] {
  return [
    formatDateTime(entry.logged_at),
    entry.meal_type,
    `${entry.food_name}${entry.brand ? ` (${entry.brand})` : ""}`,
    Math.round(entry.quantity_g).toString(),
    Math.round(entry.nutrients.calories_kcal ?? 0).toString(),
    entry.source,
    `${Math.round(entry.confidence * 100)}%`,
  ];
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
  onAddPerson,
}: {
  people: Person[];
  activePersonId: string;
  onChange: (personId: string) => void;
  onAddPerson: () => void;
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
      <button type="button" className="person-chip add-person-chip" onClick={onAddPerson}>
        <span>+</span>
        Pessoa
      </button>
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
  onSubmit: (message: string) => void;
}) {
  const [sourceDay, setSourceDay] = useState(() => addDays(today, -1));
  const [mealType, setMealType] = useState("breakfast");
  const mealLabel = mealTypeLabel(mealType);
  const message = `Repetir ${mealLabel} de ${sourceDay} no dia ${today}.`;
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
          onSubmit(message);
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
          {busy ? "Enviando..." : "Enviar ao chat"}
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
  const [notes, setNotes] = useState("");
  const canSubmit = name.trim() || yieldG.trim() || ingredients.trim() || notes.trim();
  const recipeText = [
    "Receita/lote:",
    name.trim() ? `Nome: ${name.trim()}` : "",
    yieldG.trim() ? `Rendimento total: ${yieldG.trim()} g` : "",
    ingredients.trim() ? "Ingredientes:" : "",
    ingredients.trim(),
    notes.trim() ? `Observações: ${notes.trim()}` : "",
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
        <label className="field">
          <span>Texto livre</span>
          <textarea
            rows={3}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Qualquer detalhe que ajude o agente."
          />
        </label>
        <button type="submit" className="primary-action" disabled={busy || !canSubmit}>
          {busy ? "Enviando..." : "Enviar ao chat"}
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
  onSubmit: (input: { message: string; files: File[] }) => void;
}) {
  const [product, setProduct] = useState("");
  const [barcode, setBarcode] = useState("");
  const [tableText, setTableText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const text = [
    "Rótulo:",
    product.trim() ? `Produto: ${product.trim()}` : "",
    barcode.trim() ? `Código de barras: ${barcode.trim()}` : "",
    files.length ? `${files.length} foto(s) anexada(s).` : "",
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
            onSubmit({ message: text, files });
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
          {busy ? "Enviando..." : "Enviar ao chat"}
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

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function csvCell(value: string): string {
  return `"${value.replaceAll('"', '""')}"`;
}

function mealTypeLabel(mealType: string): string {
  if (mealType === "breakfast") return "o café";
  if (mealType === "lunch") return "o almoço";
  if (mealType === "snack") return "o lanche";
  if (mealType === "dinner") return "o jantar";
  return `a refeição ${mealType}`;
}

function addDays(day: string, delta: number): string {
  const date = new Date(`${day}T12:00:00`);
  date.setDate(date.getDate() + delta);
  return date.toISOString().slice(0, 10);
}

function OnboardingScreen({
  householdId = null,
  onCancel,
  onComplete,
}: {
  householdId?: string | null;
  onCancel?: () => void;
  onComplete: (proposal: Proposal) => Promise<void>;
}) {
  const [sessionId] = useState(() => {
    const existing = localStorage.getItem(STORAGE_KEYS.onboardingSessionId);
    if (existing) return existing;
    const next = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEYS.onboardingSessionId, next);
    return next;
  });
  const [turns, setTurns] = useState<OnboardingTurn[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadOnboardingHistory(sessionId)
      .then(async (history) => {
        const proposalIds = Array.from(
          new Set(history.map((turn) => turn.proposal_id).filter((id): id is string => id != null)),
        );
        const loadedProposals = await Promise.all(proposalIds.map((proposalId) => loadProposal(proposalId)));
        if (!cancelled) {
          setTurns(history);
          setProposals(loadedProposals);
          setHistoryLoaded(true);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Não foi possível carregar o cadastro.");
          setHistoryLoaded(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const initialMessages = useMemo<ThreadMessageLike[]>(
    () => onboardingMessagesFromTurns(turns, proposals),
    [proposals, turns],
  );

  const upsertProposal = useCallback((proposal: Proposal) => {
    setProposals((current) => [proposal, ...current.filter((item) => item.id !== proposal.id)]);
  }, []);

  const confirmSetup = async (proposal: Proposal) => {
    setIsConfirming(true);
    setError(null);
    try {
      const applied = await confirmProposal(proposal.id);
      await onComplete(applied);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível confirmar a proposta.");
    } finally {
      setIsConfirming(false);
    }
  };

  const rejectSetup = async (proposal: Proposal) => {
    setError(null);
    try {
      const rejected = await rejectProposal(proposal.id);
      upsertProposal(rejected);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível rejeitar a proposta.");
    }
  };

  return (
    <main className="onboarding-screen">
      <section className="onboarding-chat" aria-label="Cadastro por conversa">
        <header className="onboarding-header">
          <div className="section-heading">
            <span>{householdId ? "Novo perfil" : "Primeiro perfil"}</span>
            {onCancel ? (
              <button type="button" onClick={onCancel}>
                Cancelar
              </button>
            ) : null}
          </div>
          <h1>{householdId ? "Adicionar pessoa pelo chat." : "Vamos configurar pelo chat."}</h1>
          <p>
            {householdId
              ? "Responda em texto livre. O agente cria uma proposta para incluir a pessoa nessa casa."
              : "Responda em texto livre. O agente cria uma proposta de casa, perfil e metas para você confirmar."}
          </p>
        </header>
        {error ? <p className="form-error onboarding-error">{error}</p> : null}
        {historyLoaded ? (
          <OnboardingThreadWorkspace
            key={`${sessionId}-${initialMessages.length}`}
            sessionId={sessionId}
            householdId={householdId}
            initialMessages={initialMessages}
            proposals={proposals}
            busy={isConfirming}
            onTurn={(turn) => setTurns((current) => [...current, turn])}
            onProposal={upsertProposal}
            onRuntimeError={setError}
            onConfirmProposal={(proposal) => {
              void confirmSetup(proposal);
            }}
            onRejectProposal={(proposal) => {
              void rejectSetup(proposal);
            }}
          />
        ) : (
          <div className="onboarding-status" role="status">
            Carregando cadastro...
          </div>
        )}
      </section>
    </main>
  );
}

function OnboardingThreadWorkspace({
  sessionId,
  householdId,
  initialMessages,
  proposals,
  busy,
  onTurn,
  onProposal,
  onRuntimeError,
  onConfirmProposal,
  onRejectProposal,
}: {
  sessionId: string;
  householdId?: string | null;
  initialMessages: readonly ThreadMessageLike[];
  proposals: Proposal[];
  busy: boolean;
  onTurn: (turn: OnboardingTurn) => void;
  onProposal: (proposal: Proposal) => void;
  onRuntimeError: (message: string) => void;
  onConfirmProposal: (proposal: Proposal) => void;
  onRejectProposal: (proposal: Proposal) => void;
}) {
  const runtime = useOnboardingRuntime({
    sessionId,
    householdId,
    settings: defaultAgentSettings(),
    initialMessages,
    onTurn,
    onProposal,
    onRuntimeError,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ProposalToolRenderer
        proposals={proposals}
        busy={busy}
        onConfirm={onConfirmProposal}
        onReject={onRejectProposal}
        onUpdateEntry={() => undefined}
        onResolveClarification={() => undefined}
      />
      <ChatInterface
        welcomeMessage={
          householdId
            ? "Oi! Vou adicionar uma pessoa nesta casa. Qual é o nome dela, fuso e objetivo inicial?"
            : "Oi! Vou configurar o diário. Como você se chama, e quais metas quer começar usando?"
        }
        suggestions={[
          {
            text: householdId ? "Adicionar rápido" : "Começar rápido",
            prompt: householdId
              ? "Adicionar Ana, fuso America/Sao_Paulo. Ela quer começar com 1800 kcal e 120g de proteína."
              : "Sou Gabriel, fuso America/Sao_Paulo. Quero começar com 2000 kcal e 150g de proteína.",
          },
          {
            text: "Deixar o agente sugerir",
            prompt: "Quero perder gordura. Pode sugerir metas iniciais para mim.",
          },
        ]}
        placeholder="Escreva seu nome, fuso, objetivo, metas ou peça para o agente sugerir..."
        allowAttachments={false}
      />
    </AssistantRuntimeProvider>
  );
}

function onboardingMessagesFromTurns(
  turns: readonly OnboardingTurn[],
  proposals: readonly Proposal[],
): ThreadMessageLike[] {
  const proposalById = new Map(proposals.map((proposal) => [proposal.id, proposal]));
  return turns.flatMap((turn) => [
    {
      role: "user" as const,
      content: [{ type: "text" as const, text: turn.user_message }],
    },
    {
      role: "assistant" as const,
      content: assistantContentForOnboardingTurn(turn, proposalById.get(turn.proposal_id ?? "")),
    },
  ]);
}

function assistantContentForOnboardingTurn(turn: OnboardingTurn, proposal?: Proposal) {
  const content = [{ type: "text" as const, text: turn.assistant_message }];
  if (!proposal) {
    return content;
  }
  const proposalJson = JSON.parse(JSON.stringify(proposal)) as ReadonlyJSONObject;
  return [
    ...content,
    {
      type: "tool-call" as const,
      toolCallId: `proposal-${proposal.id}`,
      toolName: "draft_proposal",
      args: { proposal: proposalJson },
      argsText: JSON.stringify({ proposal: proposalJson }),
      result: { proposal },
    },
  ];
}

export default App;
