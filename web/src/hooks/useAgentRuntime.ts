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

          // The assistant message is an ordered transcript of the run:
          // thought blocks, in-between messages, and tool meta lines stay in
          // sequence (texting style) instead of collapsing into one reply.
          const segments: StreamSegment[] = [];
          let toolCount = 0;
          let finalResponse: AgentChatResponse | null = null;
          for await (const event of streamAgentChatEvents({
            personId,
            message: text,
            settings,
            today,
            attachmentIds,
            signal: options.abortSignal,
          })) {
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
            if ((event.event === "thinking_delta" || event.event === "text_delta") && isObject(event.data)) {
              const kind = event.event === "thinking_delta" ? ("reasoning" as const) : ("text" as const);
              const delta = String(event.data["text"] ?? "");
              const last = segments.at(-1);
              if (last && last.kind === kind) {
                last.text += delta;
              } else if (delta) {
                segments.push({ kind, text: delta });
              }
            } else if (event.event === "tool_call" && isObject(event.data)) {
              const name = String(event.data["name"] ?? "ferramenta");
              // The wrap-up record of the whole run is bookkeeping, not a tool.
              if (name !== "pydantic_ai_chat") {
                segments.push({
                  kind: "tool",
                  id: toolCount++,
                  name: name.replaceAll("_", " "),
                  status: String(event.data["status"] ?? ""),
                });
              }
            } else {
              continue;
            }
            if (segments.length) {
              yield { content: segmentsToParts(segments) };
            }
          }
          if (finalResponse == null) {
            throw new Error("Resposta final ausente no stream do agente.");
          }
          onAgentResponse(finalResponse);
          const streamedText = segments
            .filter((segment) => segment.kind === "text")
            .map((segment) => segment.text)
            .join("\n");
          const finalMessage = finalResponse.message.trim();
          if (finalMessage && !streamedText.includes(finalMessage)) {
            segments.push({ kind: "text", text: finalResponse.message });
          }
          if (finalResponse.citations.length) {
            segments.push({ kind: "text", text: `Citações: ${finalResponse.citations.length}` });
          }
          const finalContent = segmentsToParts(segments);
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

type StreamSegment =
  | { kind: "reasoning"; text: string }
  | { kind: "text"; text: string }
  | { kind: "tool"; id: number; name: string; status: string };

function segmentsToParts(segments: StreamSegment[]): AssistantContentPart[] {
  return segments.map((segment) => {
    if (segment.kind === "reasoning") {
      return { type: "reasoning", text: segment.text } as AssistantContentPart;
    }
    if (segment.kind === "text") {
      return { type: "text", text: segment.text } as AssistantContentPart;
    }
    return {
      type: "tool-call",
      toolCallId: `trace-${segment.id}`,
      toolName: "agent_tool_trace",
      args: { name: segment.name, status: segment.status },
      argsText: JSON.stringify({ name: segment.name, status: segment.status }),
      result: { displayed: true },
    } as AssistantContentPart;
  });
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

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isAgentChatResponse(value: unknown): value is AgentChatResponse {
  return isObject(value) && typeof value["run_id"] === "string" && typeof value["message"] === "string";
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
