import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { loadJobs, processJob } from "../api";
import { queryKeys } from "../queryKeys";
import type { BackgroundJob } from "../types";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  running: "Em execução",
  succeeded: "Concluído",
  failed: "Falhou",
};

const ACTIVE_STATUSES = new Set(["pending", "running"]);

export function JobsSheet({
  personId,
  onClose,
  onToast,
  onOpenResult,
}: {
  personId: string;
  onClose: () => void;
  onToast: (message: string) => void;
  onOpenResult: (job: BackgroundJob) => void;
}) {
  const queryClient = useQueryClient();
  const jobsQuery = useQuery({
    queryKey: queryKeys.jobs(personId),
    queryFn: () => loadJobs(personId),
    refetchInterval: (query) => {
      const jobs = query.state.data ?? [];
      return jobs.some((job) => ACTIVE_STATUSES.has(job.status)) ? 4000 : false;
    },
  });

  const process = useMutation({
    mutationFn: (jobId: string) => processJob(jobId),
    onSuccess: async (job) => {
      queryClient.setQueryData<BackgroundJob[]>(queryKeys.jobs(personId), (current = []) =>
        current.map((item) => (item.id === job.id ? job : item)),
      );
      if (job.status === "failed") {
        onToast(job.last_error ?? "O job falhou.");
      }
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível processar o job."),
  });

  const jobs = [...(jobsQuery.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at));

  return (
    <div className="sheet-backdrop" role="presentation" onClick={onClose}>
      <div
        className="sheet-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Tarefas"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="section-heading">
          <span>Tarefas</span>
          <button type="button" onClick={onClose}>
            Fechar
          </button>
        </div>
        {jobs.length === 0 ? <p className="empty-copy">Nenhuma tarefa em segundo plano ainda.</p> : null}
        <div className="sheet-list">
          {jobs.map((job) => (
            <div key={job.id} className="sheet-list-row job-row" style={{ gridTemplateColumns: "1fr" }}>
              <div className="proposal-inbox-row">
                <strong>{humanizeJobType(job.job_type)}</strong>
                <span className={`status-pill status-pill--${job.status}`}>
                  {STATUS_LABELS[job.status] ?? job.status}
                </span>
              </div>
              <span className="proposal-card__meta">Tentativas: {job.attempts}</span>
              {job.last_error ? <p className="form-error">{job.last_error}</p> : null}
              <div className="proposal-actions">
                {job.status === "pending" ? (
                  <button type="button" onClick={() => process.mutate(job.id)} disabled={process.isPending}>
                    {process.isPending ? "Processando..." : "Processar"}
                  </button>
                ) : null}
                {job.status === "succeeded" ? (
                  <button type="button" className="primary-action" onClick={() => onOpenResult(job)}>
                    Abrir resultado
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function humanizeJobType(jobType: string): string {
  return jobType.replaceAll("_", " ");
}
