import {
  defineAgentChatElement,
  type AgentChatAttachment,
  type AgentChatElement,
  type AgentChatElementState,
  type AgentChatMessage,
  type AgentChatMode,
  type AgentChatStatus
} from "../src";
import "../src/styles.css";
import "./styles.css";

declare global {
  interface Window {
    __agentChatEvents: Array<Record<string, unknown>>;
  }
}

defineAgentChatElement();

const now = new Date().toISOString();

const modes: AgentChatMode[] = [
  {
    id: "chat",
    label: "Chat",
    description: "Open-ended help",
    placeholder: "Ask anything or describe the task..."
  },
  {
    id: "capture",
    label: "Capture",
    description: "Structured note",
    placeholder: "Paste a list, bullets, or a rough note..."
  },
  {
    id: "evidence",
    label: "Evidence",
    description: "Images and files",
    placeholder: "Describe what the attached files should prove..."
  },
  {
    id: "review",
    label: "Review",
    description: "Check a draft",
    placeholder: "Ask for review, corrections, or next steps..."
  }
];

const sampleAttachment: AgentChatAttachment = {
  id: "attachment_sample",
  kind: "image",
  name: "sample-label.jpg",
  mimeType: "image/jpeg",
  sizeBytes: 184_320,
  status: "uploaded"
};

const messages: AgentChatMessage[] = [
  {
    id: "message_user_1",
    role: "user",
    createdAt: now,
    text: "Here is a rough note:\n- first item\n- second item\n- unclear amount",
    attachments: [sampleAttachment],
    status: "queued"
  },
  {
    id: "message_assistant_1",
    role: "assistant",
    createdAt: now,
    text: "I can turn that into a reviewable draft. I found one ambiguous part.",
    toolCalls: [
      {
        id: "tool_pending",
        name: "Read context",
        status: "pending",
        summary: "Waiting for previous state."
      },
      {
        id: "tool_running",
        name: "Extract evidence",
        status: "running",
        summary: "Checking attached files."
      },
      {
        id: "tool_succeeded",
        name: "Draft proposal",
        status: "succeeded",
        summary: "Created a reviewable draft."
      },
      {
        id: "tool_failed",
        name: "External lookup",
        status: "failed",
        summary: "The source was unavailable."
      }
    ],
    draftCards: [
      {
        id: "draft_sample",
        kind: "generic",
        title: "Reviewable draft",
        summary: "A generic proposal card with confirm and reject actions.",
        details: "field: value\nconfidence: medium",
        status: "needs_review"
      }
    ]
  },
  {
    id: "message_failed_1",
    role: "assistant",
    createdAt: now,
    text: "This response could not be completed.",
    status: "failed",
    error: "Connection dropped before the answer finished."
  }
];

let state: AgentChatElementState = {
  messages,
  modes,
  activeModeId: "chat",
  status: "idle",
  composer: {
    allowAttachments: true,
    helperText: "Press Ctrl+Enter or Cmd+Enter to send. Enter inserts a new line.",
    showInspectPrompt: true
  },
  attachments: []
};

window.__agentChatEvents = [];

const element = document.querySelector<AgentChatElement>("#demo-chat");
if (!element) throw new Error("Missing demo chat element.");

function render(): void {
  element.data = state;
}

function recordEvent(name: string, detail: unknown): void {
  const normalized = normalizeDetail(detail);
  const entry = { name, detail: normalized };
  window.__agentChatEvents.push(entry);
  const target = document.querySelector<HTMLElement>("#last-event");
  if (target) {
    target.textContent = JSON.stringify(entry, null, 2);
  }
}

function normalizeDetail(detail: unknown): unknown {
  if (!detail || typeof detail !== "object") return detail;
  const candidate = detail as {
    modeId?: string;
    text?: string;
    clientRequestId?: string;
    attachments?: AgentChatAttachment[];
    draftId?: string;
    messageId?: string;
    attachmentId?: string;
  };
  return {
    ...candidate,
    attachments: candidate.attachments?.map((attachment) => ({
      id: attachment.id,
      kind: attachment.kind,
      name: attachment.name,
      mimeType: attachment.mimeType,
      sizeBytes: attachment.sizeBytes,
      status: attachment.status
    }))
  };
}

element.addEventListener("agent-chat:send", (event) => {
  const detail = (event as CustomEvent).detail;
  recordEvent("agent-chat:send", detail);
  state = {
    ...state,
    messages: [
      ...state.messages,
      {
        id: detail.clientRequestId,
        role: "user",
        createdAt: new Date().toISOString(),
        text: detail.text,
        attachments: detail.attachments,
        status: state.status === "offline" ? "queued" : "sending"
      }
    ],
    attachments: []
  };
  render();
});

[
  "agent-chat:mode-change",
  "agent-chat:retry",
  "agent-chat:cancel",
  "agent-chat:confirm-draft",
  "agent-chat:reject-draft",
  "agent-chat:inspect-prompt",
  "agent-chat:remove-attachment"
].forEach((eventName) => {
  element.addEventListener(eventName, (event) => recordEvent(eventName, (event as CustomEvent).detail));
});

document.querySelectorAll<HTMLButtonElement>("[data-demo-status]").forEach((button) => {
  button.addEventListener("click", () => {
    const status = button.dataset.demoStatus as AgentChatStatus | undefined;
    if (!status) return;
    state = { ...state, status };
    render();
  });
});

render();
