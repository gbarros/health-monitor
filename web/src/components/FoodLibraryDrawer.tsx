import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  archiveFood,
  loadAttachment,
  loadFoods,
  loadLookupCandidates,
  logCustomFood,
  logFoodVersion,
  proposeLookupCandidate,
} from "../api";
import { queryKeys } from "../queryKeys";
import type { Attachment, FoodLookupCandidate, FoodResponse, Proposal } from "../types";

const MEAL_TYPE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "breakfast", label: "Café" },
  { value: "lunch", label: "Almoço" },
  { value: "snack", label: "Lanche" },
  { value: "dinner", label: "Janta" },
  { value: "late", label: "Madrugada" },
];

type View = "list" | "detail" | "lookup" | "manual";

export function FoodLibraryDrawer({
  householdId,
  personId,
  onClose,
  onToast,
  onProposalDrafted,
  onLoggedDirectly,
}: {
  householdId: string;
  personId: string;
  onClose: () => void;
  onToast: (message: string) => void;
  onProposalDrafted: (proposal: Proposal) => void;
  onLoggedDirectly: () => void;
}) {
  const [view, setView] = useState<View>("list");
  const [search, setSearch] = useState("");
  const [selectedFoodId, setSelectedFoodId] = useState<string | null>(null);

  const foodsQuery = useQuery({
    queryKey: queryKeys.foods(householdId, personId),
    queryFn: () => loadFoods({ householdId, personId }),
  });

  const foods = foodsQuery.data ?? [];
  const filtered = useMemo(() => {
    const query = normalizeSearch(search);
    if (!query) {
      return foods;
    }
    return foods.filter((item) => matchesFoodFilter(item, query));
  }, [foods, search]);

  const selected = selectedFoodId ? foods.find((item) => item.food.id === selectedFoodId) ?? null : null;

  return (
    <div className="sheet-backdrop" role="presentation" onClick={onClose}>
      <div
        className="sheet-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Alimentos"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="section-heading">
          <span>
            {view === "detail" ? "Alimento" : view === "lookup" ? "Buscar em bases externas" : view === "manual" ? "Registrar manualmente" : "Alimentos"}
          </span>
          <button type="button" onClick={view === "list" ? onClose : () => setView("list")}>
            {view === "list" ? "Fechar" : "Voltar"}
          </button>
        </div>

        {view === "list" ? (
          <>
            <label className="field">
              <span>Buscar</span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="nome, marca, apelido ou código de barras"
              />
            </label>
            <div className="proposal-actions">
              <button type="button" onClick={() => setView("lookup")}>
                Buscar em bases externas
              </button>
              <button type="button" onClick={() => setView("manual")}>
                Registrar manualmente
              </button>
            </div>
            {foodsQuery.isLoading ? <p className="empty-copy">Carregando alimentos...</p> : null}
            {filtered.length === 0 && !foodsQuery.isLoading ? (
              <p className="empty-copy">Nenhum alimento encontrado.</p>
            ) : null}
            <div className="sheet-list">
              {filtered.map((item) => (
                <button
                  key={item.food.id}
                  type="button"
                  className="entry-row-button sheet-list-row"
                  onClick={() => {
                    setSelectedFoodId(item.food.id);
                    setView("detail");
                  }}
                >
                  <span className="proposal-inbox-row">
                    <strong>{[item.food.brand, item.food.name].filter(Boolean).join(" · ")}</strong>
                    <span>
                      {Math.round(item.version.nutrients_per_100g.calories_kcal ?? 0)} kcal ·{" "}
                      {roundOne(item.version.nutrients_per_100g.protein_g)}g prot ·{" "}
                      {roundOne(item.version.nutrients_per_100g.carbs_g)}g carb ·{" "}
                      {roundOne(item.version.nutrients_per_100g.fat_g)}g gord /100g
                    </span>
                  </span>
                  {item.is_default ? <span className="status-pill">padrão</span> : null}
                </button>
              ))}
            </div>
          </>
        ) : null}

        {view === "detail" && selected ? (
          <FoodDetail
            item={selected}
            personId={personId}
            onToast={onToast}
            onArchived={() => setView("list")}
            onLoggedDirectly={onLoggedDirectly}
          />
        ) : null}

        {view === "lookup" ? (
          <ExternalLookupView
            householdId={householdId}
            personId={personId}
            onToast={onToast}
            onProposalDrafted={onProposalDrafted}
          />
        ) : null}

        {view === "manual" ? (
          <ManualLogForm
            householdId={householdId}
            personId={personId}
            foods={foods}
            onToast={onToast}
            onLogged={onLoggedDirectly}
          />
        ) : null}
      </div>
    </div>
  );
}

function FoodDetail({
  item,
  personId,
  onToast,
  onArchived,
  onLoggedDirectly,
}: {
  item: FoodResponse;
  personId: string;
  onToast: (message: string) => void;
  onArchived: () => void;
  onLoggedDirectly: () => void;
}) {
  const queryClient = useQueryClient();
  const [confirmingArchive, setConfirmingArchive] = useState(false);

  const archive = useMutation({
    mutationFn: () => archiveFood(item.food.id),
    onSuccess: async () => {
      onToast("Alimento arquivado.");
      await queryClient.invalidateQueries({ queryKey: ["foods"] });
      onArchived();
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível arquivar o alimento."),
  });

  const quickLog = useMutation({
    mutationFn: (quantityG: number) =>
      logFoodVersion({ personId, foodVersionId: item.version.id, quantityG }),
    onSuccess: async () => {
      onToast("Item registrado no diário.");
      onLoggedDirectly();
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível registrar o item."),
  });

  const [quantityText, setQuantityText] = useState("100");
  const parsedQuantity = Number(quantityText.replace(",", "."));

  return (
    <div className="sheet-entry-detail">
      <h3>{[item.food.brand, item.food.name].filter(Boolean).join(" · ")}</h3>
      <span>
        {item.version.label} · fonte {item.version.source} · confiança {Math.round(item.version.confidence * 100)}%
      </span>
      <span>Criada em {formatDateTime(item.version.created_at)}</span>
      <div className="macro-grid" aria-label="Nutrientes por 100g">
        <span>
          <strong>{Math.round(item.version.nutrients_per_100g.calories_kcal ?? 0)}</strong>
          <small>kcal/100g</small>
        </span>
        <span>
          <strong>{roundOne(item.version.nutrients_per_100g.protein_g)}g</strong>
          <small>Prot</small>
        </span>
        <span>
          <strong>{roundOne(item.version.nutrients_per_100g.carbs_g)}g</strong>
          <small>Carb</small>
        </span>
        <span>
          <strong>{roundOne(item.version.nutrients_per_100g.fat_g)}g</strong>
          <small>Gord</small>
        </span>
      </div>
      {item.aliases.length ? (
        <div className="clarification-candidates" aria-label="Apelidos">
          {item.aliases.map((alias) => (
            <span key={alias} className="status-pill">
              {alias}
            </span>
          ))}
        </div>
      ) : null}
      {item.barcodes.length ? <span>Códigos de barras: {item.barcodes.join(", ")}</span> : null}
      {item.attachments.length ? <AttachmentThumbnails attachments={item.attachments} /> : null}

      <label className="field">
        <span>Registrar rapidamente (g)</span>
        <input inputMode="decimal" value={quantityText} onChange={(event) => setQuantityText(event.target.value)} />
      </label>
      <div className="proposal-actions">
        <button
          type="button"
          onClick={() => (confirmingArchive ? archive.mutate() : setConfirmingArchive(true))}
          disabled={archive.isPending || item.food.archived}
        >
          {item.food.archived ? "Arquivado" : confirmingArchive ? "Confirmar arquivar" : "Arquivar"}
        </button>
        <button
          type="button"
          className="primary-action"
          disabled={!Number.isFinite(parsedQuantity) || parsedQuantity <= 0 || quickLog.isPending}
          onClick={() => quickLog.mutate(parsedQuantity)}
        >
          {quickLog.isPending ? "Registrando..." : "Registrar"}
        </button>
      </div>
    </div>
  );
}

function AttachmentThumbnails({ attachments }: { attachments: Attachment[] }) {
  const imageAttachments = attachments.filter((attachment) => attachment.mime_type.startsWith("image/"));
  if (imageAttachments.length === 0) {
    return null;
  }
  return (
    <div className="clarification-candidates" aria-label="Evidência de rótulo">
      {imageAttachments.map((attachment) => (
        <AttachmentThumbnail key={attachment.id} attachmentId={attachment.id} />
      ))}
    </div>
  );
}

function AttachmentThumbnail({ attachmentId }: { attachmentId: string }) {
  const query = useQuery({
    queryKey: ["attachment", attachmentId],
    queryFn: () => loadAttachment(attachmentId),
  });
  if (!query.data?.content_base64) {
    return <span className="status-pill">carregando evidência...</span>;
  }
  return (
    <img
      src={`data:${query.data.mime_type};base64,${query.data.content_base64}`}
      alt={query.data.filename ?? "Evidência de rótulo"}
      style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 8 }}
    />
  );
}

function ExternalLookupView({
  householdId,
  personId,
  onToast,
  onProposalDrafted,
}: {
  householdId: string;
  personId: string;
  onToast: (message: string) => void;
  onProposalDrafted: (proposal: Proposal) => void;
}) {
  const [phrase, setPhrase] = useState("");
  const [barcode, setBarcode] = useState("");
  const [candidates, setCandidates] = useState<FoodLookupCandidate[] | null>(null);

  const search = useMutation({
    mutationFn: () => loadLookupCandidates({ householdId, personId, phrase: phrase.trim() || undefined, barcode: barcode.trim() || undefined }),
    onSuccess: (result) => setCandidates(result),
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível buscar."),
  });

  const propose = useMutation({
    mutationFn: (candidateId: string) => proposeLookupCandidate({ householdId, personId, candidateId }),
    onSuccess: (proposal) => {
      onToast("Versão rascunhada para revisão.");
      onProposalDrafted(proposal);
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível rascunhar a versão."),
  });

  return (
    <div className="sheet-entry-detail">
      <label className="field">
        <span>Frase de busca</span>
        <input value={phrase} onChange={(event) => setPhrase(event.target.value)} placeholder="iogurte grego" />
      </label>
      <label className="field">
        <span>Código de barras</span>
        <input inputMode="numeric" value={barcode} onChange={(event) => setBarcode(event.target.value)} />
      </label>
      <button
        type="button"
        className="primary-action"
        disabled={search.isPending || (!phrase.trim() && !barcode.trim())}
        onClick={() => search.mutate()}
      >
        {search.isPending ? "Buscando..." : "Buscar"}
      </button>
      {candidates ? (
        candidates.length === 0 ? (
          <p className="empty-copy">Nenhum candidato encontrado.</p>
        ) : (
          <div className="sheet-list">
            {candidates.map((candidate) => (
              <div key={candidate.id} className="sheet-list-row" style={{ gridTemplateColumns: "1fr" }}>
                <span>
                  <strong>{[candidate.brand, candidate.product_name].filter(Boolean).join(" · ")}</strong>
                  <br />
                  {candidate.source_name ?? candidate.source_type} · {Math.round(candidate.confidence * 100)}% ·{" "}
                  {Math.round(candidate.nutrients_per_100g.calories_kcal ?? 0)} kcal/100g
                </span>
                <button
                  type="button"
                  className="primary-action"
                  disabled={propose.isPending}
                  onClick={() => propose.mutate(candidate.id)}
                >
                  Rascunhar versão
                </button>
              </div>
            ))}
          </div>
        )
      ) : null}
    </div>
  );
}

function ManualLogForm({
  householdId,
  personId,
  foods,
  onToast,
  onLogged,
}: {
  householdId: string;
  personId: string;
  foods: FoodResponse[];
  onToast: (message: string) => void;
  onLogged: () => void;
}) {
  const [mode, setMode] = useState<"existing" | "custom">("existing");
  const [foodVersionId, setFoodVersionId] = useState(foods[0]?.version.id ?? "");
  const [quantityText, setQuantityText] = useState("100");
  const [mealType, setMealType] = useState("lunch");
  const [name, setName] = useState("");
  const [calories, setCalories] = useState("");
  const [protein, setProtein] = useState("");
  const [carbs, setCarbs] = useState("");
  const [fat, setFat] = useState("");

  const parsedQuantity = Number(quantityText.replace(",", "."));
  const validQuantity = Number.isFinite(parsedQuantity) && parsedQuantity > 0;

  const logExisting = useMutation({
    mutationFn: () => logFoodVersion({ personId, foodVersionId, quantityG: parsedQuantity, mealType }),
    onSuccess: () => {
      onToast("Item registrado no diário.");
      onLogged();
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível registrar o item."),
  });

  const logCustom = useMutation({
    mutationFn: () =>
      logCustomFood({
        householdId,
        personId,
        name: name.trim(),
        versionLabel: "manual",
        nutrientsPer100g: {
          calories_kcal: Number(calories.replace(",", ".")) || 0,
          protein_g: Number(protein.replace(",", ".")) || 0,
          carbs_g: Number(carbs.replace(",", ".")) || 0,
          fat_g: Number(fat.replace(",", ".")) || 0,
        },
        quantityG: parsedQuantity,
        mealType,
      }),
    onSuccess: () => {
      onToast("Alimento e item registrados.");
      onLogged();
    },
    onError: (error) => onToast(error instanceof Error ? error.message : "Não foi possível registrar."),
  });

  return (
    <div className="sheet-entry-detail">
      <div className="proposal-actions">
        <button type="button" className={mode === "existing" ? "primary-action" : ""} onClick={() => setMode("existing")}>
          Alimento existente
        </button>
        <button type="button" className={mode === "custom" ? "primary-action" : ""} onClick={() => setMode("custom")}>
          Alimento rápido novo
        </button>
      </div>

      {mode === "existing" ? (
        <label className="field">
          <span>Alimento</span>
          <select value={foodVersionId} onChange={(event) => setFoodVersionId(event.target.value)}>
            {foods.map((item) => (
              <option key={item.version.id} value={item.version.id}>
                {[item.food.brand, item.food.name].filter(Boolean).join(" · ")}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <>
          <label className="field">
            <span>Nome</span>
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <div className="macro-grid">
            <label className="field">
              <span>kcal/100g</span>
              <input inputMode="decimal" value={calories} onChange={(event) => setCalories(event.target.value)} />
            </label>
            <label className="field">
              <span>Prot g/100g</span>
              <input inputMode="decimal" value={protein} onChange={(event) => setProtein(event.target.value)} />
            </label>
            <label className="field">
              <span>Carb g/100g</span>
              <input inputMode="decimal" value={carbs} onChange={(event) => setCarbs(event.target.value)} />
            </label>
            <label className="field">
              <span>Gord g/100g</span>
              <input inputMode="decimal" value={fat} onChange={(event) => setFat(event.target.value)} />
            </label>
          </div>
        </>
      )}

      <label className="field">
        <span>Quantidade (g)</span>
        <input inputMode="decimal" value={quantityText} onChange={(event) => setQuantityText(event.target.value)} />
      </label>
      <label className="field">
        <span>Refeição</span>
        <select value={mealType} onChange={(event) => setMealType(event.target.value)}>
          {MEAL_TYPE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="primary-action"
        disabled={
          !validQuantity ||
          logExisting.isPending ||
          logCustom.isPending ||
          (mode === "existing" ? !foodVersionId : !name.trim())
        }
        onClick={() => (mode === "existing" ? logExisting.mutate() : logCustom.mutate())}
      >
        {logExisting.isPending || logCustom.isPending ? "Registrando..." : "Registrar"}
      </button>
    </div>
  );
}

function matchesFoodFilter(item: FoodResponse, normalizedQuery: string): boolean {
  const haystacks: Array<string | null | undefined> = [
    item.food.name,
    item.food.brand,
    item.version.label,
    ...item.aliases,
    ...item.barcodes,
  ];
  return haystacks.filter((value): value is string => typeof value === "string").some((value) =>
    normalizeSearch(value).includes(normalizedQuery),
  );
}

function normalizeSearch(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function roundOne(value?: number | null): number {
  return Math.round((value ?? 0) * 10) / 10;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}
