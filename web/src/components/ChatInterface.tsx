import { Thread } from "@assistant-ui/react-ui";
import "@assistant-ui/react-ui/styles/index.css";

export function ChatInterface() {
  return (
    <div className="chat-thread-shell">
      <Thread />
    </div>
  );
}
