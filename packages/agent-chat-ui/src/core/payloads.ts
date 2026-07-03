import type { AgentChatAttachment, AgentChatSendPayload } from "./types";

export function createSendPayload(
  modeId: string,
  text: string,
  attachments: AgentChatAttachment[],
  createId: () => string = () => crypto.randomUUID()
): AgentChatSendPayload {
  return {
    modeId,
    text: text.trim(),
    attachments,
    clientRequestId: createId()
  };
}

export function removeAttachmentById(
  attachments: AgentChatAttachment[],
  attachmentId: string
): AgentChatAttachment[] {
  return attachments.filter((attachment) => attachment.id !== attachmentId);
}
