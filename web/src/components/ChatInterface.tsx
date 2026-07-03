import { Thread } from "@assistant-ui/react-ui";
import "@assistant-ui/react-ui/styles/index.css";

export function ChatInterface() {
  return (
    <div className="chat-thread-shell">
      <Thread
        assistantAvatar={{ fallback: "HM" }}
        welcome={{
          message: "Pode escrever como você escreveria no ChatGPT: refeição, dúvida, correção, rótulo ou ajuste de metas.",
          suggestions: [
            { text: "Registrar refeição", prompt: "Café da manhã:\n100g iogurte\n30g whey\n1 banana" },
            { text: "Revisar o dia", prompt: "Como está meu dia até agora?" },
          ],
        }}
        composer={{ allowAttachments: true }}
        userMessage={{ allowEdit: false }}
        assistantMessage={{
          allowReload: false,
          allowCopy: true,
          allowSpeak: false,
          allowFeedbackPositive: false,
          allowFeedbackNegative: false,
        }}
        branchPicker={{ allowBranchPicker: false }}
        strings={{
          welcome: { message: "Como posso ajudar com o diário hoje?" },
          thread: { scrollToBottom: { tooltip: "Ir para o final" } },
          composer: {
            input: { placeholder: "Escreva uma refeição, pergunta, correção ou cole uma tabela..." },
            send: { tooltip: "Enviar" },
            cancel: { tooltip: "Cancelar" },
            addAttachment: { tooltip: "Anexar foto ou arquivo" },
            removeAttachment: { tooltip: "Remover anexo" },
          },
          assistantMessage: {
            copy: { tooltip: "Copiar resposta" },
            reload: { tooltip: "Gerar novamente" },
            speak: { tooltip: "Ler resposta", stop: { tooltip: "Parar leitura" } },
            feedback: {
              positive: { tooltip: "Resposta útil" },
              negative: { tooltip: "Resposta ruim" },
            },
          },
          userMessage: { edit: { tooltip: "Editar mensagem" } },
          branchPicker: {
            previous: { tooltip: "Resposta anterior" },
            next: { tooltip: "Próxima resposta" },
          },
          editComposer: {
            send: { label: "Salvar" },
            cancel: { label: "Cancelar" },
          },
          code: { header: { copy: { tooltip: "Copiar código" } } },
        }}
      />
    </div>
  );
}
