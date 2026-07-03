import { useLocalRuntime } from "@assistant-ui/react";
import type { ChatModelAdapter, ChatModelRunOptions, ChatModelRunResult } from "@assistant-ui/react";
import { useEffect, useState } from "react";

// Helper to bootstrap the person
async function getOrCreatePerson(): Promise<string> {
  const hRes = await fetch("/api/households", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "Default Household" })
  });
  const household = await hRes.json();

  const pRes = await fetch("/api/people", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      household_id: household.id,
      name: "Default Person",
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
    })
  });
  const person = await pRes.json();
  return person.id;
}

export function useAgentRuntime() {
  const [personId, setPersonId] = useState<string | null>(null);

  useEffect(() => {
    getOrCreatePerson().then(setPersonId).catch(console.error);
  }, []);

  const adapter: ChatModelAdapter = {
    async run({ messages, abortSignal }: ChatModelRunOptions): Promise<ChatModelRunResult> {
      const lastMessage = messages[messages.length - 1];
      if (!lastMessage || lastMessage.role !== "user" || !personId) {
        return { content: [] };
      }

      let text = "";
      for (const part of lastMessage.content) {
        if (part.type === "text") {
          text += part.text;
        }
      }

      try {
        const response = await fetch("/api/agent/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            person_id: personId,
            message: text,
            today: new Date().toISOString().split("T")[0],
            agent_settings: {
              agent_runtime: "pydantic-ai"
            }
          }),
          signal: abortSignal
        });
        
        if (response.ok) {
          const data = await response.json();
          // The API returns an AgentChatResponse. We can pick out the message or proposal.
          // In main.ts, it was `data.response.message` or similar. Let's just stringify for safety if it's complex.
          const replyText = typeof data.message === "string" ? data.message : JSON.stringify(data);
          
          return {
            content: [{ type: "text", text: replyText }]
          };
        } else {
          return {
            content: [{ type: "text", text: "Error communicating with agent." }]
          };
        }
      } catch (err) {
        return {
          content: [{ type: "text", text: "Network error." }]
        };
      }
    }
  };

  return useLocalRuntime(adapter);
}
