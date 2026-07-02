# Agent Chat UI

Framework-neutral chat UI primitives for the health monitor app.

This package is intentionally isolated from nutrition, diary, model-provider, and
database concepts. It owns the chat surface only: messages, attachments, modes,
draft/proposal cards, status feedback, and events emitted to the host app.

The first implementation target is a custom element that the Vite app can mount
without introducing React. If the component matures, the same package can expose
additional adapters later.

See [docs/agent-chat-ui-spec.md](../../docs/agent-chat-ui-spec.md) for the
design and rollout plan.
