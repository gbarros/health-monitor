import type {
  AgentChatAttachment,
  AgentChatAttachmentActionPayload,
  AgentChatComposerConfig,
  AgentChatDraftActionPayload,
  AgentChatMessage,
  AgentChatMessageActionPayload,
  AgentChatMode,
  AgentChatModeChangePayload,
  AgentChatSendPayload,
  AgentChatStatus
} from "../core/types";

export interface AgentChatElementState {
  messages: AgentChatMessage[];
  modes: AgentChatMode[];
  activeModeId: string;
  status: AgentChatStatus;
  composer: AgentChatComposerConfig;
  attachments: AgentChatAttachment[];
}

const defaultModes: AgentChatMode[] = [
  {
    id: "chat",
    label: "Chat",
    description: "Ask a question or describe what should be handled.",
    placeholder: "Write a message..."
  }
];

const defaultComposer: Required<AgentChatComposerConfig> = {
  label: "Message",
  helperText: "Use multiple lines when the note has several items.",
  disabled: false,
  accept: "image/*",
  multiple: true,
  sendLabel: "Send",
  cancelLabel: "Cancel",
  inspectPromptLabel: "Inspect prompt",
  showInspectPrompt: false,
  allowAttachments: true
};

export class AgentChatElement extends HTMLElement {
  private state: AgentChatElementState = {
    messages: [],
    modes: defaultModes,
    activeModeId: "chat",
    status: "idle",
    composer: {},
    attachments: []
  };

  connectedCallback(): void {
    this.render();
  }

  set data(nextState: Partial<AgentChatElementState>) {
    this.state = {
      ...this.state,
      ...nextState,
      composer: { ...this.state.composer, ...nextState.composer },
      attachments: nextState.attachments ?? this.state.attachments
    };
    this.render();
  }

  get data(): AgentChatElementState {
    return this.state;
  }

  private get composer(): Required<AgentChatComposerConfig> {
    return { ...defaultComposer, ...this.state.composer };
  }

  private get isBusy(): boolean {
    return this.state.status === "sending" || this.state.status === "replaying";
  }

  private get isDisabled(): boolean {
    return this.composer.disabled || this.isBusy;
  }

  private render(): void {
    const activeMode = this.activeMode();
    const composer = this.composer;
    const disabled = this.isDisabled;

    this.innerHTML = `
      <section class="agent-chat" data-status="${this.escapeAttribute(this.state.status)}">
        ${this.renderStatus()}
        <div class="agent-chat__mode-list" role="tablist" aria-label="Chat modes">
          ${this.renderModes()}
        </div>
        <div class="agent-chat__thread" role="log" aria-live="polite" aria-label="Conversation">
          ${this.renderMessages()}
        </div>
        <form class="agent-chat__composer" aria-label="Message composer">
          <div class="agent-chat__composer-head">
            <label class="agent-chat__label" for="agent-chat-message">${this.escapeHtml(composer.label)}</label>
            ${
              composer.showInspectPrompt
                ? `<button class="agent-chat__ghost-button" type="button" data-agent-chat-inspect-prompt>${this.escapeHtml(composer.inspectPromptLabel)}</button>`
                : ""
            }
          </div>
          <textarea
            id="agent-chat-message"
            name="message"
            rows="5"
            placeholder="${this.escapeAttribute(activeMode.placeholder)}"
            ${disabled ? "disabled" : ""}
            aria-describedby="agent-chat-composer-help"
          ></textarea>
          <p id="agent-chat-composer-help" class="agent-chat__help">${this.escapeHtml(composer.helperText)}</p>
          ${composer.allowAttachments ? this.renderComposerAttachments() : ""}
          <div class="agent-chat__actions">
            ${
              composer.allowAttachments
                ? `<label class="agent-chat__file-label">
                    <span>Add files</span>
                    <input
                      class="agent-chat__file"
                      name="attachments"
                      type="file"
                      accept="${this.escapeAttribute(composer.accept)}"
                      ${composer.multiple ? "multiple" : ""}
                      ${disabled ? "disabled" : ""}
                    />
                  </label>`
                : "<span></span>"
            }
            <div class="agent-chat__action-group">
              ${
                this.isBusy
                  ? `<button class="agent-chat__secondary-button" type="button" data-agent-chat-cancel>${this.escapeHtml(composer.cancelLabel)}</button>`
                  : ""
              }
              <button class="agent-chat__send" type="submit" ${disabled ? "disabled" : ""}>${this.escapeHtml(composer.sendLabel)}</button>
            </div>
          </div>
        </form>
      </section>
    `;

    this.bindRenderedEvents();
  }

  private bindRenderedEvents(): void {
    this.querySelectorAll<HTMLButtonElement>("[data-agent-chat-mode]").forEach((button) => {
      button.addEventListener("click", () => this.changeMode(button.dataset.agentChatMode ?? "chat"));
    });

    this.querySelector<HTMLInputElement>("input[name='attachments']")?.addEventListener("change", (event) => {
      this.addFiles((event.currentTarget as HTMLInputElement).files);
    });

    this.querySelector<HTMLFormElement>(".agent-chat__composer")?.addEventListener("submit", (event) => {
      event.preventDefault();
      this.submit();
    });

    this.querySelector<HTMLTextAreaElement>("textarea[name='message']")?.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        this.submit();
      }
    });

    this.querySelectorAll<HTMLButtonElement>("[data-agent-chat-remove-attachment]").forEach((button) => {
      button.addEventListener("click", () => this.removeAttachment(button.dataset.agentChatRemoveAttachment ?? ""));
    });

    this.querySelectorAll<HTMLButtonElement>("[data-agent-chat-retry]").forEach((button) => {
      button.addEventListener("click", () => this.emitMessageAction("agent-chat:retry", button.dataset.agentChatRetry));
    });

    this.querySelector<HTMLButtonElement>("[data-agent-chat-cancel]")?.addEventListener("click", () => {
      this.emitMessageAction("agent-chat:cancel");
    });

    this.querySelector<HTMLButtonElement>("[data-agent-chat-inspect-prompt]")?.addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("agent-chat:inspect-prompt", { bubbles: true, detail: {} }));
    });

    this.querySelectorAll<HTMLButtonElement>("[data-agent-chat-confirm-draft]").forEach((button) => {
      button.addEventListener("click", () => this.emitDraftAction("agent-chat:confirm-draft", button.dataset.agentChatConfirmDraft ?? ""));
    });

    this.querySelectorAll<HTMLButtonElement>("[data-agent-chat-reject-draft]").forEach((button) => {
      button.addEventListener("click", () => this.emitDraftAction("agent-chat:reject-draft", button.dataset.agentChatRejectDraft ?? ""));
    });
  }

  private renderStatus(): string {
    const labels: Record<AgentChatStatus, string> = {
      idle: "Ready",
      offline: "Offline. Messages can be captured and retried later.",
      sending: "Sending message...",
      queued: "Queued for replay.",
      replaying: "Replaying queued message...",
      failed: "Failed. Retry is available."
    };
    return `
      <div class="agent-chat__status" role="status" aria-live="polite">
        <span class="agent-chat__status-dot" aria-hidden="true"></span>
        <span>${this.escapeHtml(labels[this.state.status])}</span>
        ${this.state.status === "failed" ? `<button type="button" data-agent-chat-retry>Retry</button>` : ""}
      </div>
    `;
  }

  private renderModes(): string {
    return this.state.modes.map((mode, index) => {
      const selected = mode.id === this.state.activeModeId;
      return `
        <button
          id="agent-chat-mode-${this.escapeAttribute(mode.id)}"
          class="agent-chat__mode"
          type="button"
          role="tab"
          aria-selected="${selected ? "true" : "false"}"
          tabindex="${selected || index === 0 ? "0" : "-1"}"
          data-agent-chat-mode="${this.escapeAttribute(mode.id)}"
        >
          <span class="agent-chat__mode-label">${this.escapeHtml(mode.label)}</span>
          <span class="agent-chat__mode-description">${this.escapeHtml(mode.description)}</span>
        </button>
      `;
    }).join("");
  }

  private renderMessages(): string {
    if (this.state.messages.length === 0) {
      return `
        <article class="agent-chat__empty">
          <strong>Start a conversation</strong>
          <span>Choose a mode, write a message, and attach supporting files when useful.</span>
        </article>
      `;
    }

    return this.state.messages.map((message) => `
      <article
        class="agent-chat__message agent-chat__message--${this.escapeAttribute(message.role)}"
        data-message-id="${this.escapeAttribute(message.id)}"
      >
        <div class="agent-chat__message-meta">
          <strong>${this.escapeHtml(this.roleLabel(message.role))}</strong>
          <span>${this.escapeHtml(this.formatTime(message.createdAt))}</span>
          ${message.status ? `<span class="agent-chat__message-status">${this.escapeHtml(message.status)}</span>` : ""}
        </div>
        ${message.text ? `<div class="agent-chat__message-text">${this.escapeHtml(message.text)}</div>` : ""}
        ${message.attachments?.length ? this.renderAttachments(message.attachments, false) : ""}
        ${message.toolCalls?.length ? this.renderToolCalls(message.toolCalls) : ""}
        ${message.draftCards?.length ? this.renderDraftCards(message.draftCards) : ""}
        ${
          message.error
            ? `<div class="agent-chat__error" role="alert">
                <span>${this.escapeHtml(message.error)}</span>
                <button type="button" data-agent-chat-retry="${this.escapeAttribute(message.id)}">Retry</button>
              </div>`
            : ""
        }
      </article>
    `).join("");
  }

  private renderComposerAttachments(): string {
    if (!this.state.attachments.length) {
      return `<div class="agent-chat__attachment-empty">No files attached.</div>`;
    }
    return this.renderAttachments(this.state.attachments, true);
  }

  private renderAttachments(attachments: AgentChatAttachment[], removable: boolean): string {
    return `
      <ul class="agent-chat__attachments" aria-label="${removable ? "Pending attachments" : "Message attachments"}">
        ${attachments.map((attachment) => `
          <li class="agent-chat__attachment" data-attachment-id="${this.escapeAttribute(attachment.id)}">
            ${
              attachment.previewUrl && attachment.kind === "image"
                ? `<img src="${this.escapeAttribute(attachment.previewUrl)}" alt="" loading="lazy" />`
                : `<span class="agent-chat__attachment-icon" aria-hidden="true"></span>`
            }
            <span class="agent-chat__attachment-main">
              <strong>${this.escapeHtml(attachment.name)}</strong>
              <span>${this.escapeHtml(this.formatBytes(attachment.sizeBytes))}${attachment.status ? ` · ${this.escapeHtml(attachment.status)}` : ""}</span>
              ${attachment.error ? `<em>${this.escapeHtml(attachment.error)}</em>` : ""}
            </span>
            ${
              removable
                ? `<button type="button" aria-label="Remove ${this.escapeAttribute(attachment.name)}" data-agent-chat-remove-attachment="${this.escapeAttribute(attachment.id)}">Remove</button>`
                : ""
            }
          </li>
        `).join("")}
      </ul>
    `;
  }

  private renderToolCalls(toolCalls: NonNullable<AgentChatMessage["toolCalls"]>): string {
    return `
      <ul class="agent-chat__tool-list" aria-label="Tool activity">
        ${toolCalls.map((toolCall) => `
          <li class="agent-chat__tool-call" data-status="${this.escapeAttribute(toolCall.status)}">
            <span class="agent-chat__tool-dot" aria-hidden="true"></span>
            <strong>${this.escapeHtml(toolCall.name)}</strong>
            <span>${this.escapeHtml(toolCall.status)}</span>
            ${toolCall.summary ? `<p>${this.escapeHtml(toolCall.summary)}</p>` : ""}
          </li>
        `).join("")}
      </ul>
    `;
  }

  private renderDraftCards(draftCards: NonNullable<AgentChatMessage["draftCards"]>): string {
    return `
      <div class="agent-chat__draft-list" aria-label="Draft proposals">
        ${draftCards.map((draftCard) => `
          <section class="agent-chat__draft-card" data-draft-id="${this.escapeAttribute(draftCard.id)}">
            <div>
              <span>${this.escapeHtml(draftCard.kind.replaceAll("_", " "))}</span>
              <strong>${this.escapeHtml(draftCard.title)}</strong>
            </div>
            <p>${this.escapeHtml(draftCard.summary)}</p>
            ${draftCard.details ? `<pre>${this.escapeHtml(draftCard.details)}</pre>` : ""}
            <div class="agent-chat__draft-footer">
              <span>${this.escapeHtml(draftCard.status)}</span>
              ${
                draftCard.status === "draft" || draftCard.status === "needs_review"
                  ? `<div class="agent-chat__action-group">
                      <button type="button" data-agent-chat-reject-draft="${this.escapeAttribute(draftCard.id)}">Reject</button>
                      <button type="button" data-agent-chat-confirm-draft="${this.escapeAttribute(draftCard.id)}">Confirm</button>
                    </div>`
                  : ""
              }
            </div>
          </section>
        `).join("")}
      </div>
    `;
  }

  private activeMode(): AgentChatMode {
    return this.state.modes.find((mode) => mode.id === this.state.activeModeId)
      ?? this.state.modes[0]
      ?? defaultModes[0];
  }

  private changeMode(modeId: string): void {
    this.state = { ...this.state, activeModeId: modeId };
    this.dispatchEvent(new CustomEvent<AgentChatModeChangePayload>("agent-chat:mode-change", {
      bubbles: true,
      detail: { modeId }
    }));
    this.render();
    this.querySelector<HTMLTextAreaElement>("textarea[name='message']")?.focus();
  }

  private addFiles(files: FileList | null): void {
    if (!files?.length) return;
    const nextAttachments = Array.from(files).map((file) => this.attachmentFromFile(file));
    this.state = {
      ...this.state,
      attachments: this.composer.multiple
        ? [...this.state.attachments, ...nextAttachments]
        : nextAttachments.slice(0, 1)
    };
    this.render();
  }

  private attachmentFromFile(file: File): AgentChatAttachment {
    const kind = file.type.startsWith("image/") ? "image" : "file";
    return {
      id: `local_${Date.now()}_${Math.random().toString(16).slice(2)}`,
      kind,
      name: file.name,
      mimeType: file.type || "application/octet-stream",
      sizeBytes: file.size,
      file,
      previewUrl: kind === "image" ? URL.createObjectURL(file) : undefined,
      status: "local"
    };
  }

  private removeAttachment(attachmentId: string): void {
    const attachment = this.state.attachments.find((candidate) => candidate.id === attachmentId);
    if (!attachment) return;
    if (attachment.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
    this.state = {
      ...this.state,
      attachments: this.state.attachments.filter((candidate) => candidate.id !== attachmentId)
    };
    this.dispatchEvent(new CustomEvent<AgentChatAttachmentActionPayload>("agent-chat:remove-attachment", {
      bubbles: true,
      detail: { attachmentId }
    }));
    this.render();
  }

  private submit(): void {
    if (this.isDisabled) return;
    const textarea = this.querySelector<HTMLTextAreaElement>("textarea[name='message']");
    const text = textarea?.value.trim() ?? "";
    if (!text && this.state.attachments.length === 0) {
      return;
    }

    const payload: AgentChatSendPayload = {
      modeId: this.state.activeModeId,
      text,
      attachments: this.state.attachments,
      clientRequestId: crypto.randomUUID()
    };

    this.dispatchEvent(new CustomEvent<AgentChatSendPayload>("agent-chat:send", {
      bubbles: true,
      detail: payload
    }));

    if (textarea) textarea.value = "";
    this.state = { ...this.state, attachments: [] };
    this.render();
  }

  private emitMessageAction(eventName: "agent-chat:retry" | "agent-chat:cancel", messageId?: string): void {
    this.dispatchEvent(new CustomEvent<AgentChatMessageActionPayload>(eventName, {
      bubbles: true,
      detail: messageId ? { messageId } : {}
    }));
  }

  private emitDraftAction(eventName: "agent-chat:confirm-draft" | "agent-chat:reject-draft", draftId: string): void {
    this.dispatchEvent(new CustomEvent<AgentChatDraftActionPayload>(eventName, {
      bubbles: true,
      detail: { draftId }
    }));
  }

  private roleLabel(role: AgentChatMessage["role"]): string {
    const labels: Record<AgentChatMessage["role"], string> = {
      user: "You",
      assistant: "Assistant",
      system: "System",
      tool: "Tool"
    };
    return labels[role];
  }

  private formatTime(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit"
    }).format(date);
  }

  private formatBytes(value: number): string {
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }

  private escapeHtml(value: string): string {
    return value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  private escapeAttribute(value: string): string {
    return this.escapeHtml(value);
  }
}

export function defineAgentChatElement(tagName = "agent-chat"): void {
  if (!customElements.get(tagName)) {
    customElements.define(tagName, AgentChatElement);
  }
}
