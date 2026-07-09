import { AssistantRuntimeProvider, useAssistantToolUI, type ThreadMessageLike } from "@assistant-ui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReadonlyJSONObject } from "assistant-stream/utils";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { PanelLeftCloseIcon, PanelLeftOpenIcon, SquarePenIcon, WrenchIcon } from "lucide-react";
import {
  ApiError,
  confirmProposal,
  defaultAgentSettings,
  activateChatSession,
  deleteDiaryEntry,
  deleteMemoryNote,
  loadChatSessions,
  loadMemoryNotes,
  loadActiveGoal,
  loadDaySummary,
  loadChatHistory,
  loadDiaryRange,
  loadFoods,
  loadJobs,
  loadOnboardingHistory,
  loadPeople,
  loadProposal,
  loadProposals,
  loadWeightTrend,
  logWeight,
  startNewChatSession,
  readStoredAgentSettings,
  readStoredBackgroundJobs,
  writeStoredAgentSettings,
  writeStoredBackgroundJobs,
  rejectProposal,
  restoreDiaryEntry,
  sendAgentChat,
  STORAGE_KEYS,
  todayIsoForTimezone,
  updateDiaryEntry,
  updateProposalEntry,
  updateWeightEntry,
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
  ChatSession,
  DaySummaryEntry,
  FoodResponse,
  OnboardingTurn,
  Person,
  Proposal,
  ProposalEntry,
  WeightEntry,
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
  const [settings, setSettingsState] = useState<AgentSettings>(() => readStoredAgentSettings());
  const setSettings = useCallback((next: AgentSettings) => {
    writeStoredAgentSettings(next);
    setSettingsState(next);
  }, []);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [logFoodOpen, setLogFoodOpen] = useState(false);
  const [weightOpen, setWeightOpen] = useState(false);
  const [recipeOpen, setRecipeOpen] = useState(false);
  const [labelOpen, setLabelOpen] = useState(false);
  const [repeatOpen, setRepeatOpen] = useState(false);
  const [proposalInboxOpen, setProposalInboxOpen] = useState(false);
  const [foodLibraryOpen, setFoodLibraryOpen] = useState(false);
  const [jobsSheetOpen, setJobsSheetOpen] = useState(false);
  const [addingPerson, setAddingPerson] = useState(false);
  const [backgroundJobsEnabled, setBackgroundJobsEnabledState] = useState(() => readStoredBackgroundJobs());
  const setBackgroundJobsEnabled = useCallback((enabled: boolean) => {
    writeStoredBackgroundJobs(enabled);
    setBackgroundJobsEnabledState(enabled);
  }, []);
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

  const chatSessionsQuery = useQuery({
    queryKey: ["chatSessions", selectedPersonId],
    queryFn: () => loadChatSessions(selectedPersonId ?? ""),
    enabled: selectedPersonId != null,
  });
  const activeSessionId = (chatSessionsQuery.data ?? []).find((session) => session.active)?.id ?? null;

  // The thread reads one query keyed by (person, session) so turns are always
  // consistent with the session they belong to — two independent queries used
  // to race after Nova conversa / reopen and briefly render the wrong thread.
  const sessionHistoryQuery = useQuery({
    queryKey: ["chatHistorySession", selectedPersonId, activeSessionId],
    queryFn: () => loadChatHistory(selectedPersonId ?? "", activeSessionId ?? undefined),
    enabled: selectedPersonId != null && activeSessionId != null,
  });

  const sessionTurns = useMemo(() => {
    if (activeSessionId != null) {
      return sessionHistoryQuery.data ?? [];
    }
    return chatHistoryQuery.data ?? [];
  }, [activeSessionId, chatHistoryQuery.data, sessionHistoryQuery.data]);

  const proposalsById = useMemo(
    () => new Map((proposalsQuery.data ?? []).map((proposal) => [proposal.id, proposal])),
    [proposalsQuery.data],
  );

  // Proposals referenced by visible turns render as interactive cards
  // in-thread (same as live responses), so the fallback dock stays hidden
  // after a reload.
  const initialMessages = useMemo<ThreadMessageLike[]>(
    () =>
      sessionTurns.flatMap((turn) => {
        const proposal = turn.proposal_id ? proposalsById.get(turn.proposal_id) : undefined;
        const assistantContent: ThreadMessageLike["content"] = [
          { type: "text" as const, text: turn.assistant_message },
        ];
        if (proposal) {
          const proposalJson = JSON.parse(JSON.stringify(proposal)) as ReadonlyJSONObject;
          (assistantContent as unknown[]).push({
            type: "tool-call" as const,
            toolCallId: `proposal-${proposal.id}`,
            toolName: "draft_proposal",
            args: { proposal: proposalJson },
            argsText: JSON.stringify({ proposal: proposalJson }),
            result: { proposal: proposalJson },
          });
        }
        return [
          {
            role: "user" as const,
            content: [{ type: "text" as const, text: turn.user_message }],
          },
          {
            role: "assistant" as const,
            content: assistantContent,
          },
        ];
      }),
    [proposalsById, sessionTurns],
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
          await queryClient.invalidateQueries({ queryKey: ["chatHistorySession", selectedPersonId] });
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

  const newChatSession = useMutation({
    mutationFn: () => startNewChatSession(selectedPersonId ?? ""),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.chatHistory(selectedPersonId) }),
        queryClient.invalidateQueries({ queryKey: ["chatHistorySession", selectedPersonId] }),
        queryClient.invalidateQueries({ queryKey: ["chatSessions", selectedPersonId] }),
      ]);
      showToast("Nova conversa iniciada. As anteriores ficam em Conversas.");
    },
    onError: (error) =>
      showToast(error instanceof Error ? error.message : "Não foi possível iniciar nova conversa."),
  });

  const activateSession = useMutation({
    mutationFn: (sessionId: string) => activateChatSession(selectedPersonId ?? "", sessionId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.chatHistory(selectedPersonId) }),
        queryClient.invalidateQueries({ queryKey: ["chatHistorySession", selectedPersonId] }),
        queryClient.invalidateQueries({ queryKey: ["chatSessions", selectedPersonId] }),
      ]);
      setSessionsOpen(false);
      showToast("Conversa reaberta. Novas mensagens continuam nela.");
    },
    onError: (error) =>
      showToast(error instanceof Error ? error.message : "Não foi possível reabrir a conversa."),
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
      setLogFoodOpen(false);
      setRecipeOpen(false);
      setLabelOpen(false);
      setRepeatOpen(false);
      showToast("Mensagem enviada ao agente.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.chatHistory(selectedPersonId) });
      await queryClient.invalidateQueries({ queryKey: ["chatHistorySession", selectedPersonId] });
      setChatReloadKey((key) => key + 1);
      await invalidateDailyReadModels();
    },
    onError: (error) => showToast(error instanceof Error ? error.message : "Não foi possível enviar ao agente."),
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
        await queryClient.invalidateQueries({ queryKey: ["chatHistorySession", selectedPersonId] });
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
  const historyProposalIds = useMemo(
    () => new Set(sessionTurns.map((turn) => turn.proposal_id).filter(Boolean)),
    [sessionTurns],
  );
  const fallbackDraft =
    activeDraft && !inlineProposalIds.has(activeDraft.id) && !historyProposalIds.has(activeDraft.id)
      ? activeDraft
      : undefined;

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
          chatHistoryQuery.isSuccess && (proposalsQuery.isSuccess || proposalsQuery.isError) && (chatSessionsQuery.isSuccess || chatSessionsQuery.isError) && (activeSessionId == null || sessionHistoryQuery.isSuccess) ? (
            <ChatWorkspace
              key={`${selectedPersonId}-${chatReloadKey}-${activeSessionId ?? "none"}`}
              householdId={householdId}
              personId={selectedPersonId}
              today={selectedDay}
              settings={settings}
              initialMessages={initialMessages}
              proposal={fallbackDraft}
              proposals={proposalsQuery.data ?? []}
              proposalBusy={proposalDecision.isPending || proposalEntryUpdate.isPending}
              onLogFoodClick={() => setLogFoodOpen(true)}
              onRepeatClick={() => setRepeatOpen(true)}
              onWeightClick={() => setWeightOpen(true)}
              onNewSessionClick={() => newChatSession.mutate()}
              onSessionsClick={() => setSessionsOpen(true)}
              sessions={chatSessionsQuery.data ?? []}
              sessionBusy={activateSession.isPending || newChatSession.isPending}
              onActivateSession={(sessionId) => activateSession.mutate(sessionId)}
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
            householdId={householdId}
            personId={selectedPersonId}
            selectedDay={selectedDay}
            proposals={proposalsQuery.data ?? []}
            jobs={jobsQuery.data ?? []}
            turns={chatHistoryQuery.data ?? []}
            onToast={showToast}
            onEntryDeleted={onEntryDeleted}
            onDataChanged={invalidateDailyReadModels}
          />
        ) : null}

        {activeView === "settings" ? (
          <section className="settings-page" aria-label="Ajustes">
            <p className="settings-autosave-note">
              <small>Alterações são salvas automaticamente neste dispositivo.</small>
            </p>
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

      {sessionsOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setSessionsOpen(false)}>
          <div
            className="settings-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Conversas"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="section-heading">
              <span>Conversas</span>
              <button type="button" onClick={() => setSessionsOpen(false)}>
                Fechar
              </button>
            </div>
            <div className="session-list">
              {(chatSessionsQuery.data ?? []).map((session) => (
                <button
                  key={session.id}
                  type="button"
                  className={`session-row${session.active ? " is-active" : ""}`}
                  disabled={session.active || activateSession.isPending}
                  onClick={() => activateSession.mutate(session.id)}
                >
                  <strong>{session.preview || "Conversa sem mensagens"}</strong>
                  <span>
                    {session.last_at ? formatDateTime(session.last_at) : "agora"} ·{" "}
                    {session.turn_count} {session.turn_count === 1 ? "mensagem" : "mensagens"}
                    {session.active ? " · ativa" : ""}
                  </span>
                </button>
              ))}
              {(chatSessionsQuery.data ?? []).length === 0 ? (
                <p className="empty-copy">Nenhuma conversa ainda.</p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

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

      {logFoodOpen ? (
        <LogFoodModal
          busy={promptBuilderSend.isPending}
          onClose={() => setLogFoodOpen(false)}
          onSubmit={(input) =>
            promptBuilderSend.mutate({ message: input.message, files: input.files, intent: "log_food" })
          }
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
          busy={proposalDecision.isPending || proposalEntryUpdate.isPending}
          onClose={() => setProposalInboxOpen(false)}
          onConfirm={(proposal) => proposalDecision.mutate({ proposal, decision: "confirm" })}
          onReject={(proposal) => proposalDecision.mutate({ proposal, decision: "reject" })}
          onUpdateEntry={(proposal, entry, quantityG) => proposalEntryUpdate.mutate({ proposal, entry, quantityG })}
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
  onLogFoodClick,
  onRepeatClick,
  onWeightClick,
  onNewSessionClick,
  onSessionsClick,
  sessions,
  sessionBusy,
  onActivateSession,
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
  onLogFoodClick: () => void;
  onRepeatClick: () => void;
  onWeightClick: () => void;
  onNewSessionClick: () => void;
  onSessionsClick: () => void;
  sessions: ChatSession[];
  sessionBusy: boolean;
  onActivateSession: (sessionId: string) => void;
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
      />
      <ToolTraceRenderer />
      <section className="chat-workspace" aria-label="Conversa">
        <SessionSidebar
          sessions={sessions}
          busy={sessionBusy}
          onActivate={onActivateSession}
          onNewSession={onNewSessionClick}
        />
        <div className="chat-main">
          <div className="chat-top">
            <DaySummaryStrip personId={personId} day={today} onDayChange={onDayChange} />
            <QuickActionRow
              onLogFoodClick={onLogFoodClick}
              onRepeatClick={onRepeatClick}
              onWeightClick={onWeightClick}
              onRecipeClick={onRecipeClick}
              onLabelClick={onLabelClick}
            />
            <div className="chat-session-bar">
              <button type="button" className="chat-session-new" onClick={onSessionsClick}>
                Conversas
              </button>
              <button type="button" className="chat-session-new" onClick={onNewSessionClick}>
                Nova conversa
              </button>
            </div>
          </div>
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
          />
        </div>
        <aside className="chat-rail" aria-label="Resumo do dia">
          <DaySummaryStrip personId={personId} day={today} onDayChange={onDayChange} />
          <QuickActionRow
            onLogFoodClick={onLogFoodClick}
            onRepeatClick={onRepeatClick}
            onWeightClick={onWeightClick}
            onRecipeClick={onRecipeClick}
            onLabelClick={onLabelClick}
          />
        </aside>
      </section>
    </AssistantRuntimeProvider>
  );
}


function SessionSidebar({
  sessions,
  busy,
  onActivate,
  onNewSession,
}: {
  sessions: ChatSession[];
  busy: boolean;
  onActivate: (sessionId: string) => void;
  onNewSession: () => void;
}) {
  const [collapsed, setCollapsedState] = useState(
    () => localStorage.getItem("health-monitor.session-sidebar") === "collapsed",
  );
  const setCollapsed = (value: boolean) => {
    localStorage.setItem("health-monitor.session-sidebar", value ? "collapsed" : "open");
    setCollapsedState(value);
  };
  return (
    <aside className={`session-sidebar${collapsed ? " is-collapsed" : ""}`} aria-label="Conversas">
      <div className="session-sidebar__head">
        {!collapsed ? <span className="eyebrow">Conversas</span> : null}
        <button
          type="button"
          className="session-sidebar__toggle"
          aria-label={collapsed ? "Expandir lista de conversas" : "Recolher lista de conversas"}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? <PanelLeftOpenIcon size={18} /> : <PanelLeftCloseIcon size={18} />}
        </button>
      </div>
      <button
        type="button"
        className="session-sidebar__new"
        disabled={busy}
        aria-label="Nova conversa"
        onClick={onNewSession}
      >
        <SquarePenIcon size={16} />
        {!collapsed ? <span>Nova conversa</span> : null}
      </button>
      {!collapsed ? (
        <div className="session-sidebar__list">
          {sessions.map((session) => (
            <button
              key={session.id}
              type="button"
              className={`session-sidebar__item${session.active ? " is-active" : ""}`}
              disabled={session.active || busy}
              onClick={() => onActivate(session.id)}
            >
              <strong>{session.preview || "Conversa sem mensagens"}</strong>
              <span>
                {session.last_at ? formatDateTime(session.last_at) : "agora"} - {session.turn_count}
              </span>
            </button>
          ))}
          {sessions.length === 0 ? <p className="empty-copy">Nenhuma conversa ainda.</p> : null}
        </div>
      ) : null}
    </aside>
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
  householdId,
  personId,
  selectedDay,
  proposals,
  jobs,
  turns,
  onToast,
  onEntryDeleted,
  onDataChanged,
}: {
  householdId: string;
  personId: string;
  selectedDay: string;
  proposals: Proposal[];
  jobs: BackgroundJob[];
  turns: AgentChatTurn[];
  onToast: (message: string) => void;
  onEntryDeleted: (entryId: string) => void;
  onDataChanged: () => Promise<void>;
}) {
  const [rangeStart, setRangeStart] = useState(selectedDay);
  const [rangeEnd, setRangeEnd] = useState(selectedDay);
  const [editingEntryId, setEditingEntryId] = useState<string | null>(null);
  const [editingWeightId, setEditingWeightId] = useState<string | null>(null);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null);
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
  const weightTrendQuery = useQuery({
    queryKey: queryKeys.weightTrend(personId),
    queryFn: () => loadWeightTrend(personId),
  });
  const foodsQuery = useQuery({
    queryKey: queryKeys.foods(householdId, personId),
    queryFn: () => loadFoods({ householdId, personId }),
  });
  const memoryNotesQuery = useQuery({
    queryKey: ["memoryNotes", personId],
    queryFn: () => loadMemoryNotes(personId),
  });
  const memoryNoteDelete = useMutation({
    mutationFn: (noteId: string) => deleteMemoryNote(noteId),
    onSuccess: async () => {
      await memoryNotesQuery.refetch();
      onToast("Nota de memória excluída.");
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível excluir a nota."),
  });
  const entries = diaryRangeQuery.data ?? [];
  const foods = foodsQuery.data ?? [];
  const selectedProposal = proposals.find((proposal) => proposal.id === selectedProposalId) ?? null;
  const weights = (weightTrendQuery.data?.entries ?? []).filter((entry) => {
    const measuredDay = entry.measured_at.slice(0, 10);
    return measuredDay >= rangeQueryStart && measuredDay <= rangeQueryEnd;
  });
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
        columns={["Hora", "Refeição", "Alimento", "g", "kcal", "Fonte", "Conf.", "Ações"]}
        rows={entries.map((entry) =>
          diaryEntryRow(entry, {
            editing: editingEntryId === entry.id,
            onEdit: () => setEditingEntryId(entry.id),
            onCancel: () => setEditingEntryId(null),
            onDone: () => setEditingEntryId(null),
            onToast,
            onEntryDeleted,
            onDataChanged,
          }),
        )}
      />
      <DataTable
        title="Propostas"
        empty="Nenhuma proposta."
        columns={["Criada", "Tipo", "Status", "Resumo", "Ações"]}
        rows={proposals.map((proposal) => proposalRow(proposal, () => setSelectedProposalId(proposal.id)))}
      />
      {selectedProposal ? (
        <section className="data-section proposal-detail-section" aria-label="Detalhes da proposta">
          <div className="section-heading">
            <span>Detalhes da proposta</span>
            <button type="button" onClick={() => setSelectedProposalId(null)}>
              Fechar
            </button>
          </div>
          <ProposalCard
            proposal={selectedProposal}
            busy
            onConfirm={() => undefined}
            onReject={() => undefined}
            showDetails
          />
        </section>
      ) : null}
      <DataTable
        title="Pesos"
        empty="Nenhum peso registrado neste intervalo."
        columns={["Medido em", "kg", "Fonte", "Nota", "Ações"]}
        rows={weights.map((entry) =>
          weightEntryRow(entry, {
            editing: editingWeightId === entry.id,
            onEdit: () => setEditingWeightId(entry.id),
            onCancel: () => setEditingWeightId(null),
            onDone: () => setEditingWeightId(null),
            onToast,
            onDataChanged,
          }),
        )}
      />
      <DataTable
        title="Alimentos e versões"
        empty="Nenhum alimento cadastrado."
        columns={["Alimento", "Versão", "kcal/100g", "P/C/G", "Fonte", "Conf.", "Aliases", "Códigos"]}
        rows={foods.map((item) => foodVersionRow(item))}
      />
      <DataTable
        title="Jobs"
        empty="Nenhuma tarefa."
        columns={["Criado", "Tipo", "Status", "Tentativas", "Erro"]}
        rows={jobs.map((job) => [formatDateTime(job.created_at), job.job_type, job.status, String(job.attempts), job.last_error ?? ""])}
      />
      <DataTable
        title="Memória do agente"
        empty="Nenhuma nota de memória. Peça no chat: “lembre que…”"
        columns={["Atualizado", "Título", "Conteúdo", ""]}
        rows={(memoryNotesQuery.data ?? []).map((note) => [
          formatDateTime(note.updated_at),
          note.title,
          note.body,
          <button
            key={`delete-${note.id}`}
            type="button"
            className="compact-button"
            disabled={memoryNoteDelete.isPending}
            onClick={() => memoryNoteDelete.mutate(note.id)}
          >
            Excluir
          </button>,
        ])}
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
  rows: DataRow[];
}) {
  const csv = [columns, ...rows].map((row) => row.map((cell) => csvCell(cellToCsvValue(cell))).join(",")).join("\n");
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

type DataRow = Array<string | ReactNode>;

function cellToCsvValue(cell: string | ReactNode): string {
  return typeof cell === "string" ? cell : "";
}

function diaryEntryRow(
  entry: DaySummaryEntry,
  controls: {
    editing: boolean;
    onEdit: () => void;
    onCancel: () => void;
    onDone: () => void;
    onToast: (message: string) => void;
    onEntryDeleted: (entryId: string) => void;
    onDataChanged: () => Promise<void>;
  },
): DataRow {
  return [
    formatDateTime(entry.logged_at),
    entry.meal_type,
    `${entry.food_name}${entry.brand ? ` (${entry.brand})` : ""}`,
    Math.round(entry.quantity_g).toString(),
    Math.round(entry.nutrients.calories_kcal ?? 0).toString(),
    entry.source,
    `${Math.round(entry.confidence * 100)}%`,
    controls.editing ? (
      <DiaryEntryInlineEditor key={entry.id} entry={entry} {...controls} />
    ) : (
      <button type="button" onClick={controls.onEdit}>
        Editar
      </button>
    ),
  ];
}

function DiaryEntryInlineEditor({
  entry,
  onCancel,
  onDone,
  onToast,
  onEntryDeleted,
  onDataChanged,
}: {
  entry: DaySummaryEntry;
  onCancel: () => void;
  onDone: () => void;
  onToast: (message: string) => void;
  onEntryDeleted: (entryId: string) => void;
  onDataChanged: () => Promise<void>;
}) {
  const [quantityText, setQuantityText] = useState(String(entry.quantity_g));
  const [mealType, setMealType] = useState(entry.meal_type);
  const save = useMutation({
    mutationFn: () =>
      updateDiaryEntry({
        entryId: entry.id,
        quantityG: Number(quantityText.replace(",", ".")),
        mealType,
      }),
    onSuccess: async () => {
      await onDataChanged();
      onDone();
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível editar o item."),
  });
  const remove = useMutation({
    mutationFn: () => deleteDiaryEntry(entry.id),
    onSuccess: async () => {
      await onDataChanged();
      onEntryDeleted(entry.id);
      onDone();
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível excluir o item."),
  });
  const parsedQuantity = Number(quantityText.replace(",", "."));
  const canSave = Number.isFinite(parsedQuantity) && parsedQuantity > 0;
  return (
    <div className="inline-edit-controls">
      <input
        aria-label="Quantidade em gramas"
        inputMode="decimal"
        value={quantityText}
        onChange={(event) => setQuantityText(event.target.value)}
      />
      <select aria-label="Refeição" value={mealType} onChange={(event) => setMealType(event.target.value)}>
        <option value="breakfast">Café</option>
        <option value="lunch">Almoço</option>
        <option value="snack">Lanche</option>
        <option value="dinner">Janta</option>
        <option value="late">Madrugada</option>
      </select>
      <button type="button" onClick={() => save.mutate()} disabled={!canSave || save.isPending || remove.isPending}>
        {save.isPending ? "Salvando..." : "Salvar"}
      </button>
      <button type="button" onClick={() => remove.mutate()} disabled={save.isPending || remove.isPending}>
        {remove.isPending ? "Excluindo..." : "Excluir"}
      </button>
      <button type="button" onClick={onCancel} disabled={save.isPending || remove.isPending}>
        Cancelar
      </button>
    </div>
  );
}

function weightEntryRow(
  entry: WeightEntry,
  controls: {
    editing: boolean;
    onEdit: () => void;
    onCancel: () => void;
    onDone: () => void;
    onToast: (message: string) => void;
    onDataChanged: () => Promise<void>;
  },
): DataRow {
  return [
    formatDateTime(entry.measured_at),
    entry.weight_kg.toLocaleString("pt-BR", { maximumFractionDigits: 2 }),
    entry.source,
    entry.note ?? "",
    controls.editing ? (
      <WeightInlineEditor key={entry.id} entry={entry} {...controls} />
    ) : (
      <button type="button" onClick={controls.onEdit}>
        Editar
      </button>
    ),
  ];
}

function WeightInlineEditor({
  entry,
  onCancel,
  onDone,
  onToast,
  onDataChanged,
}: {
  entry: WeightEntry;
  onCancel: () => void;
  onDone: () => void;
  onToast: (message: string) => void;
  onDataChanged: () => Promise<void>;
}) {
  const [measuredAt, setMeasuredAt] = useState(entry.measured_at.slice(0, 16));
  const [weightText, setWeightText] = useState(String(entry.weight_kg));
  const [note, setNote] = useState(entry.note ?? "");
  const save = useMutation({
    mutationFn: () =>
      updateWeightEntry({
        entryId: entry.id,
        measuredAtLocal: measuredAt,
        weightKg: Number(weightText.replace(",", ".")),
        note: note.trim() || undefined,
      }),
    onSuccess: async () => {
      await onDataChanged();
      onDone();
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível editar o peso."),
  });
  const parsedWeight = Number(weightText.replace(",", "."));
  const canSave = Number.isFinite(parsedWeight) && parsedWeight > 0 && measuredAt.length > 0;
  return (
    <div className="inline-edit-controls inline-weight-controls">
      <input
        aria-label="Data e hora do peso"
        type="datetime-local"
        value={measuredAt}
        onChange={(event) => setMeasuredAt(event.target.value)}
      />
      <input
        aria-label="Peso em kg"
        inputMode="decimal"
        value={weightText}
        onChange={(event) => setWeightText(event.target.value)}
      />
      <input aria-label="Nota do peso" value={note} onChange={(event) => setNote(event.target.value)} />
      <button type="button" onClick={() => save.mutate()} disabled={!canSave || save.isPending}>
        {save.isPending ? "Salvando..." : "Salvar"}
      </button>
      <button type="button" onClick={onCancel} disabled={save.isPending}>
        Cancelar
      </button>
    </div>
  );
}

function proposalRow(proposal: Proposal, onDetails: () => void): DataRow {
  return [
    formatDateTime(proposal.created_at),
    proposal.proposal_type,
    proposal.status,
    proposal.summary,
    (
      <button type="button" onClick={onDetails}>
        Detalhes
      </button>
    ),
  ];
}

function foodVersionRow(item: FoodResponse): string[] {
  const nutrients = item.version.nutrients_per_100g;
  return [
    [item.food.brand, item.food.name].filter(Boolean).join(" · "),
    `${item.version.label}${item.is_default ? " (padrão)" : ""}${item.food.archived ? " (arquivado)" : ""}`,
    Math.round(nutrients.calories_kcal ?? 0).toString(),
    `${roundOne(nutrients.protein_g)} / ${roundOne(nutrients.carbs_g)} / ${roundOne(nutrients.fat_g)}`,
    item.version.source,
    `${Math.round(item.version.confidence * 100)}%`,
    item.aliases.join(", "),
    item.barcodes.join(", "),
  ];
}

function roundOne(value?: number | null): number {
  return Math.round((value ?? 0) * 10) / 10;
}

function ToolTraceRenderer() {
  const tool = useMemo(
    () => ({
      toolName: "agent_tool_trace",
      display: "standalone" as const,
      render: ({ args }: { args?: { name?: string; status?: string } }) => {
        const status = String(args?.status ?? "");
        return (
          <div className={`tool-trace-chip${status === "failed" ? " is-failed" : ""}`}>
            <WrenchIcon size={12} aria-hidden="true" />
            <span>{String(args?.name ?? "ferramenta")}</span>
            {status ? <span className="tool-trace-chip__status">{status}</span> : null}
          </div>
        );
      },
    }),
    [],
  );
  useAssistantToolUI(tool);
  return null;
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

function LogFoodModal({
  busy,
  onClose,
  onSubmit,
}: {
  busy: boolean;
  onClose: () => void;
  onSubmit: (input: { message: string; files: File[] }) => void;
}) {
  const [name, setName] = useState("");
  const [portion, setPortion] = useState("");
  const [notes, setNotes] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const message = [
    "Registrar alimento:",
    name.trim() ? `Nome: ${name.trim()}` : "",
    portion.trim() ? `Porção consumida: ${portion.trim()}` : "",
    files.length ? `${files.length} foto(s) anexada(s).` : "",
    notes.trim() ? `Detalhes: ${notes.trim()}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form
        className="small-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Registrar alimento"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit({
            message: message || "Registrar alimento. Preciso que você me ajude a completar os detalhes.",
            files,
          });
        }}
      >
        <div className="section-heading">
          <span>Registrar alimento</span>
          <button type="button" onClick={onClose}>
            Fechar
          </button>
        </div>
        <label className="field">
          <span>Fotos do alimento ou rótulo</span>
          <input
            type="file"
            accept="image/*"
            multiple
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
        </label>
        <label className="field">
          <span>Nome</span>
          <input
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="requeijão light"
          />
        </label>
        <label className="field">
          <span>Porção consumida</span>
          <input
            value={portion}
            onChange={(event) => setPortion(event.target.value)}
            placeholder="30g, 1 fatia, 1 pote"
          />
        </label>
        <label className="field">
          <span>Texto livre</span>
          <textarea
            rows={4}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Marca, horário, refeição, ou qualquer dúvida."
          />
        </label>
        <button type="submit" className="primary-action" disabled={busy}>
          {busy ? "Enviando..." : "Enviar ao chat"}
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
          onSubmit(recipeText || "Receita/lote. Preciso que você me ajude a completar os detalhes.");
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
        <button type="submit" className="primary-action" disabled={busy}>
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
  const appendFiles = (incoming: FileList | null) => {
    if (incoming?.length) {
      setFiles((current) => [...current, ...Array.from(incoming)]);
    }
  };
  const text = [
    "Rótulo:",
    product.trim() ? `Produto: ${product.trim()}` : "",
    barcode.trim() ? `Código de barras: ${barcode.trim()}` : "",
    files.length
      ? `${files.length} foto(s) anexada(s) — podem conter a tabela nutricional e/ou o código de barras.`
      : "",
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
        <div className="field">
          <span>Fotos — tabela nutricional e/ou código de barras</span>
          <div className="modal-grid two">
            <label className="field">
              <span>Tirar foto</span>
              <input
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(event) => {
                  appendFiles(event.target.files);
                  event.target.value = "";
                }}
              />
            </label>
            <label className="field">
              <span>Da galeria</span>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(event) => {
                  appendFiles(event.target.files);
                  event.target.value = "";
                }}
              />
            </label>
          </div>
          {files.length ? (
            <span className="field-note">
              {files.length} foto(s) anexada(s).{" "}
              <button type="button" className="compact-button" onClick={() => setFiles([])}>
                Limpar
              </button>
            </span>
          ) : null}
        </div>
        <label className="field">
          <span>Produto (opcional)</span>
          <input value={product} onChange={(event) => setProduct(event.target.value)} placeholder="Iogurte Batavo" />
        </label>
        <label className="field">
          <span>Código de barras (se preferir digitar)</span>
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
