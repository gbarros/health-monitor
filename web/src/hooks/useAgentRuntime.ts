import {
  CompositeAttachmentAdapter,
  SimpleImageAttachmentAdapter,
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
import {
  ApiError,
  sendAgentChat,
  uploadDataUrlAttachment,
} from "../api";
import type { AgentChatResponse, AgentSettings, Proposal } from "../types";

type RuntimeContext = {
  householdId: string | null;
  personId: string | null;
  today: string;
  settings: AgentSettings;
  initialMessages: readonly ThreadMessageLike[];
  onAgentResponse: (response: AgentChatResponse) => void;
  onProposal: (proposal: Proposal) => void;
  onRuntimeError: (message: string) => void;
  onModelUnavailable: (replayMessage: string) => void;
};

export function useAgentRuntime(context: RuntimeContext) {
  const {
    householdId,
    personId,
    today,
    settings,
    initialMessages,
    onAgentResponse,
    onProposal,
    onRuntimeError,
    onModelUnavailable,
  } = context;

  const adapter = useMemo<ChatModelAdapter>(() => {
    return {
      async run(options: ChatModelRunOptions): Promise<ChatModelRunResult> {
        const lastMessage = options.messages.at(-1);
        if (!lastMessage || lastMessage.role !== "user") {
          return { content: [] };
        }

        if (!personId) {
          return assistantText(
            "Create a profile first. The first screen accepts a normal message with household, person, timezone, and target details.",
          );
        }

        const text = textFromContent(lastMessage.content);
        if (!text && !messageHasUploadableAttachment(lastMessage.content)) {
          return assistantText("Escreva uma refeição, pergunta, correção ou anexe uma foto de rótulo.");
        }

        try {
          const attachmentIds = householdId
            ? await uploadMessageAttachments({
              householdId,
              personId,
              parts: lastMessage.content,
            })
            : [];
          const response = await sendAgentChat({
            personId,
            message: text,
            settings,
            today,
            attachmentIds,
            signal: options.abortSignal,
          });
          onAgentResponse(response);
          if (response.proposal) {
            onProposal(response.proposal);
            return assistantProposal(response.proposal, chatReply(response));
          }
          return assistantText(chatReply(response));
        } catch (error) {
          if (error instanceof ApiError && error.type === "model_unavailable") {
            onModelUnavailable(error.replayMessage ?? text);
            return assistantText(
              "⚠️ Modelo local indisponível — sua mensagem não foi processada nem registrada. " +
                "Quando o modelo voltar, toque em Reenviar.",
            );
          }
          const message = error instanceof Error ? error.message : "Unknown agent error";
          onRuntimeError(message);
          return assistantText(`Não consegui completar esse pedido.\n\n${message}`);
        }
      },
    };
  }, [householdId, onAgentResponse, onModelUnavailable, onProposal, onRuntimeError, personId, settings, today]);

  const attachments = useMemo(
    () => new CompositeAttachmentAdapter([new SimpleImageAttachmentAdapter(), new SimpleTextAttachmentAdapter()]),
    [],
  );

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

function messageHasUploadableAttachment(content: readonly ThreadUserMessagePart[]): boolean {
  return content.some((part) => part.type === "image" || part.type === "file");
}

function chatReply(response: AgentChatResponse): string {
  const lines = [response.message];
  if (response.proposal) {
    lines.push("");
    lines.push(proposalReply(response.proposal, "Proposal drafted."));
  }
  if (response.citations.length) {
    lines.push("");
    lines.push(`Citations: ${response.citations.length}`);
  }
  return lines.join("\n");
}

function proposalReply(proposal: Proposal, intro: string): string {
  const totals = proposal.totals;
  const totalsText = totals
    ? [
        totals.calories_kcal != null ? `${totals.calories_kcal} kcal` : null,
        totals.protein_g != null ? `${totals.protein_g}g protein` : null,
        totals.carbs_g != null ? `${totals.carbs_g}g carbs` : null,
        totals.fat_g != null ? `${totals.fat_g}g fat` : null,
      ]
        .filter(Boolean)
        .join(", ")
    : "";
  return [
    intro,
    proposal.summary,
    `Type: ${proposal.proposal_type}`,
    `Status: ${proposal.status}`,
    totalsText ? `Totals: ${totalsText}` : null,
    "Review it in the proposal panel before anything durable is applied.",
  ]
    .filter(Boolean)
    .join("\n");
}

async function uploadMessageAttachments(input: {
  householdId: string;
  personId: string;
  parts: readonly ThreadUserMessagePart[];
}): Promise<string[]> {
  const ids: string[] = [];
  for (const part of input.parts) {
    if (part.type === "image") {
      const attachment = await uploadDataUrlAttachment({
        householdId: input.householdId,
        personId: input.personId,
        dataUrl: part.image,
        filename: part.filename,
      });
      ids.push(attachment.id);
    }
    if (part.type === "file" && part.data.startsWith("data:")) {
      const attachment = await uploadDataUrlAttachment({
        householdId: input.householdId,
        personId: input.personId,
        dataUrl: part.data,
        filename: part.filename,
        objectType: "document",
      });
      ids.push(attachment.id);
    }
  }
  return ids;
}
