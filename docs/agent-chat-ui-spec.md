# Agent Chat UI Spec

## Purpose

Build a standalone, framework-neutral chat component for agent-assisted workflows. The health monitor app should become chat-first without migrating the Vite app to React, Next, shadcn, or another large UI stack.

The component must make agent work inspectable: users should see their message, attached evidence, model/tool activity, draft proposals, errors, retries, and offline queue state. Domain logic stays in the host app and backend.

## References Reviewed

- assistant-ui: strong model for composable chat primitives such as thread, message, composer, action bar, attachments, markdown, retries, keyboard shortcuts, accessibility, tool rendering, and custom runtimes. Source: https://github.com/assistant-ui/assistant-ui
- Vercel Chatbot: useful full-product reference for persistence, attachments, generated UI, model selection, and polished chat ergonomics, but too coupled to Next.js, AI SDK, shadcn, Tailwind, auth, and Vercel deployment. Source: https://github.com/vercel/chatbot
- NLUX: useful reference for a lightweight core, adapter model, vanilla TypeScript support, theming, accessibility, and performance-first design. Source: https://github.com/nlkitai/nlux

We should borrow interaction patterns and API concepts, not copy source code. If we later copy code or CSS from a project, we need a license review in that specific change.

## Package Shape

Initial location:

```text
packages/agent-chat-ui/
  package.json
  tsconfig.json
  README.md
  src/
    index.ts
    styles.css
    core/
      types.ts
      thread-state.ts
    components/
      agent-chat.ts
```

The first target is a custom element:

```html
<agent-chat></agent-chat>
```

The host app imports:

```ts
import { defineAgentChatElement } from "@health-monitor/agent-chat-ui";
import "@health-monitor/agent-chat-ui/styles.css";

defineAgentChatElement();
```

This is deliberately not wired into the app yet. The next pass should add workspace/build integration after the component contract is stable enough.

## Design Principles

- Chat is the default surface; specialized flows are modes inside chat.
- Modes shape the first user turn, they do not create separate UI products.
- Every model-visible prompt and uploaded evidence should be inspectable.
- The component emits events; the host app owns API calls, IndexedDB outbox, route state, and domain-specific proposal rendering.
- Offline is capture-first: preserve text and files, then replay through backend jobs when connected.
- No direct durable writes from the UI component. It can display proposal cards and emit confirm/reject events, but the host app decides what API call to make.
- Accessibility is non-negotiable: visible labels, keyboard navigation, aria-live thread updates, 44px minimum touch targets, readable contrast, and no hover-only actions.

## Core Concepts

### Thread

A thread is an ordered list of `AgentChatMessage` records. The component must render:

- user messages
- assistant messages
- system notices
- tool-call summaries
- proposal cards
- attachment evidence
- retryable failures

### Modes

Mode examples for this app:

- Chat
- Meal note
- Product label
- Recipe
- Correction
- Review note

Each mode has:

- `id`
- `label`
- `description`
- `placeholder`
- whether it accepts attachments
- optional preferred attachment kind
- optional hidden prompt template owned by the host app

The component should never hard-code nutrition-specific prompt text.

### Attachments

Attachments need first-class UI because label scans may include several photos. The component tracks display state:

- local
- uploading
- uploaded
- failed

The host app maps local files to backend attachment IDs. The component can show local file names, previews, and upload/retry status, but it should not call `/api/attachments` directly.

### Tool Activity

Tool calls should be visible but compact:

- OCR over `attachment_id`
- food lookup
- barcode lookup
- day/week summary read
- proposal drafting

Default rendering should show name, status, and a short summary. Domain cards can be slotted or supplied later through a render hook.

### Proposal Cards

Proposal cards are how agent output becomes durable app data. The generic card shape supports:

- meal
- label
- recipe
- correction
- review note

Cards display title, summary, status, and actions. The health app can later provide richer domain renderers for macros, foods, versions, evidence, and warnings.

## Public API Draft

Types exported now:

- `AgentChatMessage`
- `AgentChatAttachment`
- `AgentChatToolCall`
- `AgentChatDraftCard`
- `AgentChatMode`
- `AgentChatSendPayload`
- `AgentChatThreadState`

Custom element state:

```ts
element.data = {
  messages,
  modes,
  activeModeId,
  status
};
```

Events:

- `agent-chat:send`
- `agent-chat:mode-change`
- `agent-chat:retry`
- `agent-chat:cancel`
- `agent-chat:confirm-draft`
- `agent-chat:reject-draft`
- `agent-chat:inspect-prompt`
- `agent-chat:remove-attachment`

The implemented custom element emits the full event set above. The health-monitor app currently consumes `send`, `mode-change`, `confirm-draft`, `reject-draft`, `inspect-prompt`, and `retry` on the Log page.

## UX Requirements

- Composer is multiline by default and optimized for item lists.
- Attachments are available in every mode that benefits from evidence, including plain chat.
- Product label mode must allow multiple images, not one photo.
- Barcode can be typed or supplied by a host-level scanner action.
- Send action should support keyboard submit later, but newline must remain easy for meal lists.
- Errors stay attached to the failed message or attachment.
- Offline state should read as a queued state, not as a broken app.
- On mobile, the composer remains reachable and touch targets stay at least 44px.
- On desktop, the thread width should be readable and not sprawl edge-to-edge.

## Integration Plan

1. Keep the package private and local.
2. Use Vite aliases from the app until a root workspace is justified.
3. Maintain the static demo page without adding Storybook.
4. Keep the current Log page chat area backed by `<agent-chat>`.
5. Map host app state to `AgentChatMessage[]`.
6. Map mode sends to existing background jobs and proposal APIs:
   - Chat -> chat job
   - Meal note -> text meal proposal job
   - Product label -> attachment upload, OCR/label scan job
   - Recipe -> recipe proposal job
   - Correction/review note -> chat/proposal job
7. Surface offline outbox status through message/status state where practical.
8. Keep Playwright coverage for send, attachment, offline queue, replay, proposal confirmation, and mode switching.

## Open Decisions

- Whether to use shadow DOM. Initial skeleton uses light DOM so app-level CSS and e2e selectors remain simple.
- Whether rich cards are passed as generic data, slots, or host render callbacks.
- Whether markdown rendering belongs in this component or stays a host concern until streaming exists.
- Whether the package should become publishable before alpha. For now, it remains private.

## Non-Goals For The Bootstrap

- No React island.
- No dependency on shadcn, Tailwind, Radix, Vercel AI SDK, or assistant-ui runtime.
- No direct model/provider coupling.
- No direct health-monitor API coupling.
- No source-code copying from reference projects.
