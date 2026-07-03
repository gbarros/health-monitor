import { expect, test } from "@playwright/test";
import {
  appendMessage,
  createThreadState,
  setThreadStatus,
  updateMessage
} from "../../packages/agent-chat-ui/src/core/thread-state";
import { createSendPayload, removeAttachmentById } from "../../packages/agent-chat-ui/src/core/payloads";
import type { AgentChatAttachment, AgentChatMessage } from "../../packages/agent-chat-ui/src/core/types";

const message: AgentChatMessage = {
  id: "message_1",
  role: "user",
  createdAt: "2026-07-02T10:00:00.000Z",
  text: "hello"
};

const attachments: AgentChatAttachment[] = [
  {
    id: "attachment_1",
    kind: "file",
    name: "first.txt",
    mimeType: "text/plain",
    sizeBytes: 10
  },
  {
    id: "attachment_2",
    kind: "file",
    name: "second.txt",
    mimeType: "text/plain",
    sizeBytes: 20
  }
];

test("thread-state helpers are immutable", () => {
  const initial = createThreadState("compose");
  const withMessage = appendMessage(initial, message);
  const updated = updateMessage(withMessage, "message_1", { text: "updated" });
  const failed = setThreadStatus(updated, "failed");

  expect(initial.messages).toEqual([]);
  expect(withMessage.messages[0].text).toBe("hello");
  expect(updated.messages[0].text).toBe("updated");
  expect(failed.status).toBe("failed");
});

test("send payload and attachment helpers are deterministic with injected ids", () => {
  const payload = createSendPayload("compose", "  hello  ", attachments, () => "client_1");
  const remaining = removeAttachmentById(attachments, "attachment_1");

  expect(payload).toMatchObject({
    modeId: "compose",
    text: "hello",
    clientRequestId: "client_1"
  });
  expect(payload.attachments).toHaveLength(2);
  expect(remaining.map((attachment) => attachment.id)).toEqual(["attachment_2"]);
  expect(attachments).toHaveLength(2);
});
