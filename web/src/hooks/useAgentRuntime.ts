import {
  CompositeAttachmentAdapter,
  SimpleImageAttachmentAdapter,
  SimpleTextAttachmentAdapter,
  useLocalRuntime,
} from "@assistant-ui/react";
import type {
  PendingAttachment,
  CompleteAttachment,
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
import { recordClientEvent, telemetryOperationId } from "../clientTelemetry";

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
        const runOperationId = telemetryOperationId("chat");
        const runStartedAt = performance.now();
        const lastMessage = options.messages.at(-1);
        if (!lastMessage || lastMessage.role !== "user") {
          yield { content: [] };
          return;
        }

        if (!personId) {
          yield assistantText(
            "Crie um perfil primeiro. Na tela inicial, escreva normalmente os dados da casa, da pessoa, do fuso e das metas.",
          );
          return;
        }

        const text = textFromContent(lastMessage.content);
        // assistant-ui keeps completed attachment payloads outside message.content.
        // Flatten both containers before validation/upload so the API receives
        // attachment ids and the agent can invoke vision/OCR tools.
        const uploadableParts = uniqueUploadableParts([
          ...lastMessage.content,
          ...lastMessage.attachments.flatMap((attachment) => attachment.content),
        ]);
        const uploadableCount = uploadableParts.filter(
          (part) => part.type === "image" || part.type === "file",
        ).length;
        recordClientEvent("client.chat.run_started", {
          operation_id: runOperationId,
          input_chars: text.length,
          attachment_count: uploadableCount,
          attachment_container_count: lastMessage.attachments.length,
          background_jobs: backgroundJobsEnabled,
          model_profile: settings.model_profile || "default",
        });
        if (!text && !messageHasUploadableAttachment(uploadableParts)) {
          yield assistantText("Escreva uma refeição, pergunta, correção ou anexe uma foto de rótulo.");
          return;
        }
        const requestText = text || "Analise estas fotos e me diga o que você identificou.";

        try {
          const segments: StreamSegment[] = [];
          let toolCount = 0;
          if (uploadableCount > 0) {
            segments.push({
              kind: "tool",
              id: toolCount++,
              key: "client:upload",
              name: `Enviando ${uploadableCount === 1 ? "a foto" : `${uploadableCount} fotos`} com segurança…`,
              status: "started",
            });
            yield { content: segmentsToParts(segments) };
          }
          recordClientEvent("client.chat.attachment_upload_phase_started", {
            operation_id: runOperationId,
            attachment_count: uploadableCount,
          });
          const attachmentIds = householdId
            ? await uploadMessageAttachments({
              householdId,
              personId,
              parts: uploadableParts,
            })
            : [];
          recordClientEvent("client.chat.attachment_upload_phase_completed", {
            operation_id: runOperationId,
            uploaded_count: attachmentIds.length,
          });
          const uploadStage = segments.find(
            (segment) => segment.kind === "tool" && segment.key === "client:upload",
          );
          if (uploadStage?.kind === "tool") {
            uploadStage.name = attachmentIds.length === 1 ? "Foto enviada" : `${attachmentIds.length} fotos enviadas`;
            uploadStage.status = "completed";
            yield { content: segmentsToParts(segments) };
          }

          if (backgroundJobsEnabled) {
            const job = await enqueueAgentChatJob({
              personId,
              message: requestText,
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
          let streamEventCount = 0;
          let deltaEventCount = 0;
          let finalResponse: AgentChatResponse | null = null;
          recordClientEvent("client.chat.stream_opening", {
            operation_id: runOperationId,
            uploaded_count: attachmentIds.length,
          });
          for await (const event of streamAgentChatEvents({
            personId,
            message: requestText,
            settings,
            today,
            attachmentIds,
            signal: options.abortSignal,
          })) {
            streamEventCount += 1;
            if (event.event === "text_delta" || event.event === "thinking_delta") {
              deltaEventCount += 1;
            } else {
              recordClientEvent("client.chat.stream_event", {
                operation_id: runOperationId,
                stream_event: event.event,
                ordinal: streamEventCount,
              });
            }
            if (event.event === "run_started") {
              segments.push({
                kind: "tool",
                id: toolCount++,
                key: "server:persisted-run",
                name: "Pedido salvo — análise em andamento",
                status: "started",
              });
              yield { content: segmentsToParts(segments) };
              continue;
            }
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
            } else if (event.event === "stage" && isObject(event.data)) {
              const stageName = String(event.data["name"] ?? "working");
              const status = String(event.data["status"] ?? "started");
              const label = String(event.data["label"] ?? "Processando…");
              const active = [...segments].reverse().find(
                (segment) => segment.kind === "tool" && segment.key === `stage:${stageName}`,
              );
              if (active?.kind === "tool") {
                active.name = label;
                active.status = status;
              } else {
                segments.push({
                  kind: "tool",
                  id: toolCount++,
                  key: `stage:${stageName}`,
                  name: label,
                  status,
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
          const persistedRunStage = segments.find(
            (segment) => segment.kind === "tool" && segment.key === "server:persisted-run",
          );
          if (persistedRunStage?.kind === "tool") {
            persistedRunStage.name = "Análise concluída e salva";
            persistedRunStage.status = "completed";
          }
          onAgentResponse(finalResponse);
          recordClientEvent("client.chat.run_completed", {
            operation_id: runOperationId,
            duration_ms: Math.round(performance.now() - runStartedAt),
            stream_event_count: streamEventCount,
            delta_event_count: deltaEventCount,
            tool_count: toolCount,
            has_proposal: finalResponse.proposal != null,
          });
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
          recordClientEvent(
            "client.chat.run_failed",
            {
              operation_id: runOperationId,
              duration_ms: Math.round(performance.now() - runStartedAt),
              error_name: error instanceof Error ? error.name : typeof error,
              error_detail: error instanceof Error ? error.message.slice(0, 300) : String(error).slice(0, 300),
            },
            "error",
          );
          if (error instanceof ApiError && error.type === "model_unavailable") {
            onSendFailed(error.replayMessage ?? requestText, "model_unavailable");
            yield completeResult(assistantText(
              "Modelo local indisponível — sua mensagem não foi processada nem registrada. " +
                "Quando o modelo voltar, toque em Reenviar.",
            ));
            return;
          }
          if (error instanceof TypeError) {
            onSendFailed(requestText, "network");
            yield completeResult(assistantText(
              "Sem conexão — sua mensagem não foi enviada. Quando a conexão voltar, toque em Reenviar.",
            ));
            return;
          }
          const safeMessage =
            error instanceof ApiError && error.type === "agent_error"
              ? "Não consegui concluir esta análise. As fotos continuam salvas; você pode tentar novamente ou descrever o item que ficou incerto."
              : "Não consegui completar esse pedido agora. Tente novamente em instantes.";
          onRuntimeError(safeMessage);
          yield completeResult(assistantText(safeMessage));
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
    () => new CompositeAttachmentAdapter([new InstrumentedImageAttachmentAdapter(), new SimpleTextAttachmentAdapter()]),
    [],
  );

  return useLocalRuntime(adapter, {
    initialMessages,
    adapters: { attachments },
  });
}

class InstrumentedImageAttachmentAdapter extends SimpleImageAttachmentAdapter {
  private readonly operations = new WeakMap<File, string>();

  override async add(state: { file: File }): Promise<PendingAttachment> {
    const operationId = telemetryOperationId("image");
    this.operations.set(state.file, operationId);
    recordClientEvent("client.attachment.adapter_add_started", {
      operation_id: operationId,
      byte_count: state.file.size,
      mime_type: state.file.type || "unknown",
    });
    const attachment = await super.add(state);
    recordClientEvent("client.attachment.adapter_add_completed", {
      operation_id: operationId,
      byte_count: state.file.size,
    });
    return attachment;
  }

  override async send(attachment: PendingAttachment): Promise<CompleteAttachment> {
    const operationId = this.operations.get(attachment.file) ?? telemetryOperationId("image");
    const startedAt = performance.now();
    recordClientEvent("client.attachment.conversion_started", {
      operation_id: operationId,
      byte_count: attachment.file.size,
      mime_type: attachment.file.type || "unknown",
    });
    try {
      const completed = await super.send(attachment);
      // SimpleImageAttachmentAdapter intentionally emits only the data URL. Keep
      // the File metadata on the message part so it survives assistant-ui's
      // completed-attachment flattening and reaches our upload API.
      const content = completed.content.map((part) => {
        if (part.type !== "image") return part;
        imageUploadMetadata.set(part.image, {
          filename: attachment.file.name || attachment.name,
          capturedAt: fileCaptureTime(attachment.file),
        });
        return { ...part, filename: attachment.file.name || attachment.name };
      });
      recordClientEvent("client.attachment.conversion_completed", {
        operation_id: operationId,
        duration_ms: Math.round(performance.now() - startedAt),
        byte_count: attachment.file.size,
      });
      return { ...completed, content };
    } catch (error) {
      recordClientEvent(
        "client.attachment.conversion_failed",
        {
          operation_id: operationId,
          duration_ms: Math.round(performance.now() - startedAt),
          error_name: error instanceof Error ? error.name : typeof error,
          error_detail: error instanceof Error ? error.message.slice(0, 300) : String(error).slice(0, 300),
        },
        "error",
      );
      throw error;
    }
  }
}

type ImageUploadMetadata = {
  filename?: string;
  capturedAt?: string;
};

const imageUploadMetadata = new Map<string, ImageUploadMetadata>();

function fileCaptureTime(file: File): string | undefined {
  if (!Number.isFinite(file.lastModified) || file.lastModified <= 0) return undefined;
  const value = new Date(file.lastModified);
  return Number.isNaN(value.getTime()) ? undefined : value.toISOString();
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
  | { kind: "tool"; id: number; key?: string; name: string; status: string };

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
      argsText: JSON.stringify({ name: segment.name, status: segment.status, stageKey: segment.key }),
      args: { name: segment.name, status: segment.status, stageKey: segment.key },
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

function uniqueUploadableParts(parts: readonly ThreadUserMessagePart[]): ThreadUserMessagePart[] {
  const seen = new Set<string>();
  return parts.filter((part) => {
    if (part.type !== "image" && part.type !== "file") return true;
    const value = part.type === "image" ? part.image : part.data;
    const key = `${part.type}:${part.filename ?? ""}:${value.length}:${value.slice(0, 64)}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
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
      const metadata = imageUploadMetadata.get(part.image);
      const operationId = telemetryOperationId("upload");
      const startedAt = performance.now();
      recordClientEvent("client.upload.started", {
        operation_id: operationId,
        attachment_kind: "image",
        encoded_chars: part.image.length,
      });
      try {
        const attachment = await uploadDataUrlAttachment({
          householdId: input.householdId,
          personId: input.personId,
          dataUrl: part.image,
          filename: part.filename ?? metadata?.filename,
          capturedAt: metadata?.capturedAt,
        });
        imageUploadMetadata.delete(part.image);
        ids.push(attachment.id);
        recordClientEvent("client.upload.completed", {
          operation_id: operationId,
          attachment_kind: "image",
          duration_ms: Math.round(performance.now() - startedAt),
          attachment_id: attachment.id,
        });
      } catch (error) {
        recordClientEvent(
          "client.upload.failed",
          {
            operation_id: operationId,
            attachment_kind: "image",
            duration_ms: Math.round(performance.now() - startedAt),
            error_name: error instanceof Error ? error.name : typeof error,
            error_detail: error instanceof Error ? error.message.slice(0, 300) : String(error).slice(0, 300),
          },
          "error",
        );
        throw error;
      }
    }
    if (part.type === "file" && part.data.startsWith("data:")) {
      const operationId = telemetryOperationId("upload");
      const startedAt = performance.now();
      recordClientEvent("client.upload.started", {
        operation_id: operationId,
        attachment_kind: "document",
        encoded_chars: part.data.length,
      });
      try {
        const attachment = await uploadDataUrlAttachment({
          householdId: input.householdId,
          personId: input.personId,
          dataUrl: part.data,
          filename: part.filename,
          objectType: "document",
        });
        ids.push(attachment.id);
        recordClientEvent("client.upload.completed", {
          operation_id: operationId,
          attachment_kind: "document",
          duration_ms: Math.round(performance.now() - startedAt),
          attachment_id: attachment.id,
        });
      } catch (error) {
        recordClientEvent(
          "client.upload.failed",
          {
            operation_id: operationId,
            attachment_kind: "document",
            duration_ms: Math.round(performance.now() - startedAt),
            error_name: error instanceof Error ? error.name : typeof error,
            error_detail: error instanceof Error ? error.message.slice(0, 300) : String(error).slice(0, 300),
          },
          "error",
        );
        throw error;
      }
    }
  }
  return ids;
}
