export type AgentChatRole = "user" | "assistant" | "system" | "tool";

export type AgentChatStatus =
  | "idle"
  | "offline"
  | "sending"
  | "queued"
  | "replaying"
  | "failed";

export type AgentChatAttachmentKind = "image" | "file";
export type AgentChatAttachmentStatus = "local" | "uploading" | "uploaded" | "failed";
export type AgentChatDraftCardKind = "meal" | "label" | "recipe" | "correction" | "review_note" | "generic";
export type AgentChatDraftCardStatus = "draft" | "confirmed" | "rejected" | "needs_review";
export type AgentChatToolCallStatus = "pending" | "running" | "succeeded" | "failed";
export type AgentChatMetadata = Record<string, unknown>;

export interface AgentChatComposerAction {
  id: string;
  label: string;
  disabled?: boolean;
  title?: string;
}

export interface AgentChatComposerConfig {
  label?: string;
  helperText?: string;
  disabled?: boolean;
  accept?: string;
  multiple?: boolean;
  sendLabel?: string;
  cancelLabel?: string;
  inspectPromptLabel?: string;
  showInspectPrompt?: boolean;
  allowAttachments?: boolean;
  actions?: AgentChatComposerAction[];
}

export interface AgentChatAttachment {
  id: string;
  kind: AgentChatAttachmentKind;
  name: string;
  mimeType: string;
  sizeBytes: number;
  file?: File;
  previewUrl?: string;
  status?: AgentChatAttachmentStatus;
  error?: string;
}

export interface AgentChatToolCall {
  id: string;
  name: string;
  status: AgentChatToolCallStatus;
  summary?: string;
}

export interface AgentChatDraftCard {
  id: string;
  kind: AgentChatDraftCardKind;
  title: string;
  summary: string;
  status: AgentChatDraftCardStatus;
  details?: string;
  metadata?: AgentChatMetadata;
}

export interface AgentChatMessage {
  id: string;
  role: AgentChatRole;
  createdAt: string;
  text: string;
  status?: AgentChatStatus;
  attachments?: AgentChatAttachment[];
  toolCalls?: AgentChatToolCall[];
  draftCards?: AgentChatDraftCard[];
  error?: string;
  metadata?: AgentChatMetadata;
}

export interface AgentChatMode {
  id: string;
  label: string;
  description: string;
  placeholder: string;
  acceptsAttachments?: boolean;
  preferredAttachmentKind?: AgentChatAttachmentKind;
}

export interface AgentChatSendPayload {
  modeId: string;
  text: string;
  attachments: AgentChatAttachment[];
  clientRequestId: string;
}

export interface AgentChatModeChangePayload {
  modeId: string;
}

export interface AgentChatMessageActionPayload {
  messageId?: string;
}

export interface AgentChatDraftActionPayload {
  draftId: string;
}

export interface AgentChatAttachmentActionPayload {
  attachmentId: string;
}

export interface AgentChatComposerActionPayload {
  actionId: string;
  modeId: string;
}

export interface AgentChatRuntime {
  send(payload: AgentChatSendPayload): Promise<void>;
  retry?(messageId: string): Promise<void>;
  cancel?(): Promise<void>;
}
