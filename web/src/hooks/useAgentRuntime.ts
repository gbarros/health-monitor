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
  enqueueAgentChatJob,
  streamAgentChatEvents,
  uploadDataUrlAttachment,
} from "../api";
import type { AgentChatStreamEvent } from "../api";
import type { AgentChatResponse, AgentSettings, BackgroundJob, Proposal } from "../types";

type RuntimeContext = {
  householdId: string | null;
  personId: string | null;
  today: string;
  settings: AgentSettings;
  initialMessages: readonly ThreadMessageLike[];
  backgroundJobsEnabled: boolean;
  onAgentResponse: (response: AgentChatResponse) => void;
  onProposal: (proposal: Proposal) => void;
  onRuntimeError: (message: string) => void;
  onSendFailed: (text: string, reason: "model_unavailable" | "network") => void;
  onJobQueued: (job: BackgroundJob) => void;
};

export function useAgentRuntime(context: RuntimeContext) {
  const {
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
  } = context;

  const adapter = useMemo<ChatModelAdapter>(() => {
    return {
      async *run(options: ChatModelRunOptions): AsyncGenerator<ChatModelRunResult, void> {
        const lastMessage = options.messages.at(-1);
        if (!lastMessage || lastMessage.role !== "user") {
          yield { content: [] };
          return;
        }

        if (!personId) {
          yield assistantText(
            "Create a profile first. The first screen accepts a normal message with household, person, timezone, and target details.",
          );
          return;
        }

        const text = textFromContent(lastMessage.content);
        if (!text && !messageHasUploadableAttachment(lastMessage.content)) {
          yield assistantText("Escreva uma refeição, pergunta, correção ou anexe uma foto de rótulo.");
          return;
        }

        try {
          const attachmentIds = householdId
            ? await uploadMessageAttachments({
              householdId,
              personId,
              parts: lastMessage.content,
            })
            : [];

          if (backgroundJobsEnabled) {
            const job = await enqueueAgentChatJob({
              personId,
              message: text,
              settings,
              today,
              attachmentIds,
            });
            onJobQueued(job);
            yield completeResult(assistantText("Na fila do worker… acompanhe em Tarefas."));
            return;
          }

          const events: AgentChatStreamEvent[] = [];
          let finalResponse: AgentChatResponse | null = null;
          for await (const event of streamAgentChatEvents({
            personId,
            message: text,
            settings,
            today,
            attachmentIds,
            signal: options.abortSignal,
          })) {
            events.push(event);
            if (event.event === "error" && isObject(event.data)) {
              throw new ApiError(
                String(event.data["message"] ?? "Erro do agente"),
                String(event.data["type"] ?? "agent_error"),
                typeof event.data["replay_message"] === "string" ? event.data["replay_message"] : null,
              );
            }
            if (event.event === "final" && isAgentChatResponse(event.data)) {
              finalResponse = event.data;
              continue;
            }
            const thinking = joinDeltaText(events, "thinking_delta");
            const partial = streamingReply(events);
            const content: AssistantContentPart[] = [];
            if (thinking) {
              content.push(reasoningPart(thinking));
            }
            if (partial) {
              content.push({ type: "text", text: partial });
            }
            if (content.length) {
              yield { content };
            }
          }
          if (finalResponse == null) {
            throw new Error("Resposta final ausente no stream do agente.");
          }
          onAgentResponse(finalResponse);
          const finalThinking = joinDeltaText(events, "thinking_delta");
          const finalContent: AssistantContentPart[] = [];
          if (finalThinking) {
            finalContent.push(reasoningPart(finalThinking));
          }
          finalContent.push({ type: "text", text: chatReply(finalResponse, events) });
          if (finalResponse.proposal) {
            onProposal(finalResponse.proposal);
            finalContent.push(proposalPart(finalResponse.proposal));
          }
          yield completeResult({ content: finalContent });
          return;
        } catch (error) {
          if (error instanceof ApiError && error.type === "model_unavailable") {
            onSendFailed(error.replayMessage ?? text, "model_unavailable");
            yield completeResult(assistantText(
              "⚠️ Modelo local indisponível — sua mensagem não foi processada nem registrada. " +
                "Quando o modelo voltar, toque em Reenviar.",
            ));
            return;
          }
          if (error instanceof TypeError) {
            onSendFailed(text, "network");
            yield completeResult(assistantText(
              "⚠️ Sem conexão — sua mensagem não foi enviada. Quando a conexão voltar, toque em Reenviar.",
            ));
            return;
          }
          const message = error instanceof Error ? error.message : "Unknown agent error";
          onRuntimeError(message);
          yield completeResult(assistantText(`Não consegui completar esse pedido.\n\n${message}`));
          return;
        }
      },
    };
  }, [
    backgroundJobsEnabled,
    householdId,
    onAgentResponse,
    onJobQueued,
    onProposal,
    onRuntimeError,
    onSendFailed,
    personId,
    settings,
    today,
  ]);

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

function completeResult(result: ChatModelRunResult): ChatModelRunResult {
  return {
    ...result,
    status: { type: "complete", reason: "stop" },
  };
}

type AssistantContentPart = ChatModelRunResult["content"] extends readonly (infer P)[] | undefined ? P : never;

function proposalPart(proposal: Proposal): AssistantContentPart {
  const proposalJson = JSON.parse(JSON.stringify(proposal)) as ReadonlyJSONObject;
  return {
    type: "tool-call",
    toolCallId: `proposal-${proposal.id}`,
    toolName: "draft_proposal",
    args: { proposal: proposalJson },
    argsText: JSON.stringify({ proposal: proposalJson }),
    result: { proposal },
  };
}

function reasoningPart(text: string): AssistantContentPart {
  return { type: "reasoning", text };
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

function chatReply(response: AgentChatResponse, events: readonly AgentChatStreamEvent[] = []): string {
  const lines = toolProgressLines(events);
  if (lines.length) {
    lines.push("");
  }
  lines.push(response.message);
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

function streamingReply(events: readonly AgentChatStreamEvent[]): string {
  // Thinking is rendered separately as a collapsible part, not inline text.
  const blocks: string[] = [];
  const lines = toolProgressLines(events);
  if (lines.length) {
    blocks.push(lines.join("\n"));
  }
  const text = joinDeltaText(events, "text_delta");
  if (text) {
    blocks.push(text);
  }
  return blocks.join("\n\n");
}

function joinDeltaText(events: readonly AgentChatStreamEvent[], kind: "text_delta" | "thinking_delta"): string {
  return events
    .filter((event): event is AgentChatStreamEvent & { data: Record<string, unknown> } => event.event === kind && isObject(event.data))
    .map((event) => String(event.data["text"] ?? ""))
    .join("");
}

function toolProgressLines(events: readonly AgentChatStreamEvent[]): string[] {
  const toolCalls = events.filter(
    (event): event is AgentChatStreamEvent & { data: Record<string, unknown> } =>
      event.event === "tool_call" && isObject(event.data),
  );
  if (!toolCalls.length) {
    return [];
  }
  return [
    "Ferramentas consultadas:",
    ...toolCalls.map((event) => {
      const name = String(event.data["name"] ?? "tool").replaceAll("_", " ");
      const status = String(event.data["status"] ?? "?");
      return `- ${name}: ${status}`;
    }),
  ];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isAgentChatResponse(value: unknown): value is AgentChatResponse {
  return isObject(value) && typeof value["run_id"] === "string" && typeof value["message"] === "string";
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
