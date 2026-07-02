import type { AgentChatMessage, AgentChatStatus } from "./types";

export interface AgentChatThreadState {
  messages: AgentChatMessage[];
  status: AgentChatStatus;
  activeModeId: string;
}

export function createThreadState(activeModeId: string): AgentChatThreadState {
  return {
    messages: [],
    status: "idle",
    activeModeId
  };
}

export function appendMessage(
  state: AgentChatThreadState,
  message: AgentChatMessage
): AgentChatThreadState {
  return {
    ...state,
    messages: [...state.messages, message]
  };
}

export function updateMessage(
  state: AgentChatThreadState,
  messageId: string,
  update: Partial<AgentChatMessage>
): AgentChatThreadState {
  return {
    ...state,
    messages: state.messages.map((message) =>
      message.id === messageId ? { ...message, ...update } : message
    )
  };
}

export function setThreadStatus(
  state: AgentChatThreadState,
  status: AgentChatStatus
): AgentChatThreadState {
  return {
    ...state,
    status
  };
}
