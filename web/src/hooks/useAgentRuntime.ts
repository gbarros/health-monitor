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
import { useMemo } from "react";
import {
  draftLabelScan,
  draftRecipe,
  draftTextMeal,
  sendAgentChat,
  uploadDataUrlAttachment,
} from "../api";
import type { AgentChatResponse, AgentSettings, ModeId, Proposal } from "../types";

type RuntimeContext = {
  householdId: string | null;
  personId: string | null;
  activeMode: ModeId;
  today: string;
  settings: AgentSettings;
  initialMessages: readonly ThreadMessageLike[];
  onAgentResponse: (response: AgentChatResponse) => void;
  onProposal: (proposal: Proposal) => void;
  onRuntimeError: (message: string) => void;
  onModeCompleted?: () => void;
};

export function useAgentRuntime(context: RuntimeContext) {
  const {
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
        if (!text && activeMode !== "label_scan") {
          return assistantText("Send a note or question and I will route it through the selected mode.");
        }

        try {
          if (activeMode === "text_meal") {
            const proposal = await draftTextMeal({
              personId,
              text,
              settings,
              signal: options.abortSignal,
            });
            onProposal(proposal);
            onModeCompleted?.();
            return assistantText(proposalReply(proposal, "Meal proposal drafted."));
          }

          if (activeMode === "recipe") {
            if (!householdId) {
              return assistantText("Select or create a household before drafting recipes.");
            }
            const proposal = await draftRecipe({
              householdId,
              personId,
              text,
              signal: options.abortSignal,
            });
            onProposal(proposal);
            onModeCompleted?.();
            return assistantText(proposalReply(proposal, "Recipe proposal drafted."));
          }

          if (activeMode === "label_scan") {
            if (!householdId) {
              return assistantText("Select or create a household before scanning labels.");
            }
            const attachmentIds = await uploadMessageAttachments({
              householdId,
              personId,
              parts: lastMessage.content,
            });
            const proposal = await draftLabelScan({
              householdId,
              personId,
              text,
              attachmentIds,
              signal: options.abortSignal,
            });
            onProposal(proposal);
            onModeCompleted?.();
            return assistantText(proposalReply(proposal, "Product label proposal drafted."));
          }

          const response = await sendAgentChat({
            personId,
            message: messageForMode(activeMode, text),
            settings,
            today,
            signal: options.abortSignal,
          });
          onAgentResponse(response);
          if (response.proposal) {
            onProposal(response.proposal);
          }
          return assistantText(chatReply(response));
        } catch (error) {
          const message = error instanceof Error ? error.message : "Unknown agent error";
          onRuntimeError(message);
          return assistantText(`I could not complete that request.\n\n${message}`);
        }
      },
    };
  }, [activeMode, householdId, onAgentResponse, onModeCompleted, onProposal, onRuntimeError, personId, settings, today]);

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

function textFromContent(content: readonly ThreadUserMessagePart[]): string {
  return content
    .filter((part): part is Extract<ThreadUserMessagePart, { type: "text" }> => part.type === "text")
    .map((part) => part.text)
    .join("\n")
    .trim();
}

function messageForMode(mode: ModeId, text: string): string {
  if (mode === "correction") {
    return `Correction request:\n${text}`;
  }
  if (mode === "review_note") {
    return `Review note request:\n${text}`;
  }
  return text;
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
