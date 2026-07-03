import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useAgentRuntime } from "./hooks/useAgentRuntime";
import { ChatInterface } from "./components/ChatInterface";
import { ModesAndTemplates } from "./components/ModesAndTemplates";
import { ManualInputs } from "./components/ManualInputs";

function App() {
  const runtime = useAgentRuntime();

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div style={{ display: 'flex', height: '100vh', fontFamily: 'sans-serif' }}>
        <aside style={{ width: '300px', borderRight: '1px solid #ddd', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <h2>Health Monitor</h2>
          <ModesAndTemplates />
          <ManualInputs />
        </aside>
        <main style={{ flex: 1, position: 'relative' }}>
          <ChatInterface />
        </main>
      </div>
    </AssistantRuntimeProvider>
  );
}

export default App;
