import { createContext, useContext } from "react";
import { useComposerRuntime } from "@assistant-ui/react";
import { Thread, ThreadUIConfigContext } from "@/components/assistant-ui/thread";

type ChatSuggestion = { text: string; prompt: string };

type ChatInterfaceProps = {
  welcomeMessage?: string;
  suggestions?: ChatSuggestion[];
  placeholder?: string;
  allowAttachments?: boolean;
};

const DEFAULT_SUGGESTIONS: ChatSuggestion[] = [
  { text: "Registrar refeição", prompt: "Café da manhã:\n100g iogurte\n30g whey\n1 banana" },
  { text: "Revisar o dia", prompt: "Como está meu dia até agora?" },
];

const WelcomeContext = createContext<{ message: string; suggestions: ChatSuggestion[] }>({
  message: "",
  suggestions: [],
});

export function ChatInterface({
  welcomeMessage = "Pode escrever como você escreveria no ChatGPT: refeição, dúvida, correção, rótulo ou ajuste de metas.",
  suggestions = DEFAULT_SUGGESTIONS,
  placeholder = "Escreva uma refeição, pergunta, correção ou cole uma tabela...",
  allowAttachments = true,
}: ChatInterfaceProps) {
  return (
    <div className="chat-thread-shell">
      <ThreadUIConfigContext.Provider value={{ placeholder, allowAttachments }}>
        <WelcomeContext.Provider value={{ message: welcomeMessage, suggestions }}>
          <Thread components={{ Welcome: ChatWelcome }} />
        </WelcomeContext.Provider>
      </ThreadUIConfigContext.Provider>
    </div>
  );
}

function ChatWelcome() {
  const { message, suggestions } = useContext(WelcomeContext);
  return (
    <div className="mb-6 flex flex-col items-center gap-4 px-4 text-center">
      <h1 className="fade-in slide-in-from-bottom-1 animate-in fill-mode-both text-xl font-semibold duration-200">
        Como posso ajudar com o diário hoje?
      </h1>
      <p className="text-muted-foreground max-w-md text-sm">{message}</p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {suggestions.map((suggestion) => (
          <WelcomeSuggestion key={suggestion.text} suggestion={suggestion} />
        ))}
      </div>
    </div>
  );
}

function WelcomeSuggestion({ suggestion }: { suggestion: ChatSuggestion }) {
  const composer = useComposerRuntime();
  return (
    <button
      type="button"
      className="text-foreground hover:bg-muted border-border/60 cursor-pointer rounded-full border px-3.5 py-1.5 text-sm whitespace-nowrap transition-colors"
      onClick={() => composer.setText(suggestion.prompt)}
    >
      {suggestion.text}
    </button>
  );
}
