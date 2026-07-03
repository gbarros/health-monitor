import { Thread } from "@assistant-ui/react-ui";
import "@assistant-ui/react-ui/styles/index.css";

export function ChatInterface() {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Thread />
    </div>
  );
}
