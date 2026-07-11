import { Component, type ErrorInfo, type ReactNode } from "react";
import { flushClientEvents, recordClientEvent } from "../clientTelemetry";

export class ClientErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    recordClientEvent(
      "client.error.react_boundary",
      {
        error_name: error.name,
        error_detail: (error.stack ?? error.message).slice(0, 500),
        component_stack: info.componentStack?.slice(0, 500) ?? "",
      },
      "error",
    );
    void flushClientEvents();
  }

  render() {
    if (this.state.error) {
      return (
        <main className="client-crash-screen" role="alert">
          <h1>O aplicativo encontrou um erro.</h1>
          <p>O diagnóstico foi salvo neste aparelho e será enviado quando houver conexão.</p>
          <button type="button" onClick={() => location.reload()}>Recarregar</button>
        </main>
      );
    }
    return this.props.children;
  }
}
