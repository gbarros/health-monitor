import {
  CompositeAttachmentAdapter,
  SimpleTextAttachmentAdapter,
  useLocalRuntime,
} from "@assistant-ui/react";
import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  ChatModelRunResult,
  ThreadMessageLike,
  ThreadUserMessagePart,
} from "@assistant-ui/react";
import type { ReadonlyJSONObject } from "assistant-stream/utils";
import { useMemo } from "react";
import { ApiError, loadProposal, sendOnboardingChat } from "../api";
import type { AgentSettings, OnboardingTurn, Proposal } from "../types";

type OnboardingRuntimeContext = {
  sessionId: string;
  householdId?: string | null;
  settings: AgentSettings;
  initialMessages: readonly ThreadMessageLike[];
  onTurn: (turn: OnboardingTurn) => void;
  onProposal: (proposal: Proposal) => void;
  onRuntimeError: (message: string) => void;
};

export function useOnboardingRuntime(context: OnboardingRuntimeContext) {
  const { sessionId, householdId, settings, initialMessages, onTurn, onProposal, onRuntimeError } = context;

  const adapter = useMemo<ChatModelAdapter>(() => {
    return {
      async run(options: ChatModelRunOptions): Promise<ChatModelRunResult> {
        const lastMessage = options.messages.at(-1);
        if (!lastMessage || lastMessage.role !== "user") {
          return { content: [] };
        }

        const text = textFromContent(lastMessage.content);
        if (!text) {
          return assistantText("Escreva uma mensagem para continuar o cadastro.");
        }

        try {
          const turn = await sendOnboardingChat({
            sessionId,
            householdId,
            message: text,
            agentSettings: settings,
          });
          if (turn.proposal_id) {
            const proposal = await loadProposal(turn.proposal_id);
            onTurn(turn);
            onProposal(proposal);
            return assistantProposal(proposal, turn.assistant_message);
          }
          onTurn(turn);
          return assistantText(turn.assistant_message);
        } catch (error) {
          if (error instanceof ApiError && error.type === "model_unavailable") {
            return assistantText(
              "Modelo local indisponível. O cadastro por conversa precisa do modelo ativo; tente reenviar quando ele voltar.",
            );
          }
          const message = error instanceof Error ? error.message : "Unknown onboarding error";
          onRuntimeError(message);
          return assistantText(`Não consegui continuar o cadastro.\n\n${message}`);
        }
      },
    };
  }, [householdId, onProposal, onRuntimeError, onTurn, sessionId, settings]);

  const attachments = useMemo(() => new CompositeAttachmentAdapter([new SimpleTextAttachmentAdapter()]), []);

  return useLocalRuntime(adapter, {
    initialMessages,
    adapters: { attachments },
  });
}

function assistantText(text: string): ChatModelRunResult {
  return {
    content: [{ type: "text", text }],
  };
}

function assistantProposal(proposal: Proposal, text: string): ChatModelRunResult {
  const proposalJson = JSON.parse(JSON.stringify(proposal)) as ReadonlyJSONObject;
  return {
    content: [
      { type: "text", text },
      {
        type: "tool-call",
        toolCallId: `proposal-${proposal.id}`,
        toolName: "draft_proposal",
        args: { proposal: proposalJson },
        argsText: JSON.stringify({ proposal: proposalJson }),
        result: { proposal },
      },
    ],
  };
}

function textFromContent(content: readonly ThreadUserMessagePart[]): string {
  return content
    .filter((part): part is Extract<ThreadUserMessagePart, { type: "text" }> => part.type === "text")
    .map((part) => part.text)
    .join("\n")
    .trim();
}
