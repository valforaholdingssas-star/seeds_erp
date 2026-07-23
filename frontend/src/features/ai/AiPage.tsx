import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { apiClient } from "@/lib/apiClient";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";

type AskResult = {
  answer: string;
  tool: string | null;
  mode: string;
  sources?: Array<{ title: string; kind: string; score: number; chunk: string }>;
};

type Document = {
  id: string;
  kind: string;
  title: string;
  content: string;
};

type Paginated<T> = { count: number; results: T[] };

export function AiPage() {
  const qc = useQueryClient();
  const [question, setQuestion] = useState("¿Cuánto vendimos esta semana?");
  const [answer, setAnswer] = useState<AskResult | null>(null);
  const [doc, setDoc] = useState({
    kind: "POLICY",
    title: "",
    content: "",
  });
  const [error, setError] = useState<string | null>(null);

  const docs = useQuery({
    queryKey: ["ai-docs"],
    queryFn: async () => {
      const { data } = await apiClient.get<Paginated<Document> | Document[]>("/ai/documents/");
      return Array.isArray(data) ? data : data.results;
    },
  });

  const ask = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<AskResult>("/ai/ask/", { question });
      return data;
    },
    onSuccess: (data) => {
      setAnswer(data);
      setError(null);
    },
    onError: () => setError("No se pudo consultar el agente."),
  });

  const ingest = useMutation({
    mutationFn: async () => {
      await apiClient.post("/ai/documents/", doc);
    },
    onSuccess: () => {
      setDoc({ kind: "POLICY", title: "", content: "" });
      setError(null);
      qc.invalidateQueries({ queryKey: ["ai-docs"] });
    },
    onError: () => setError("Solo ADMIN puede ingerir documentos."),
  });

  function onAsk(e: FormEvent) {
    e.preventDefault();
    ask.mutate();
  }

  function onIngest(e: FormEvent) {
    e.preventDefault();
    if (!doc.content.trim()) {
      setError("El contenido del documento es obligatorio.");
      return;
    }
    ingest.mutate();
  }

  return (
    <div className="space-y-3">
      <PageHeader eyebrow="Inteligencia" title="Asistente ERP" />

      {error && <Alert variant="error">{error}</Alert>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card tone="cream">
          <form onSubmit={onAsk} className="space-y-4">
            <FieldLabel htmlFor="q">Pregunta</FieldLabel>
            <Input
              id="q"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ej. ventas por vendedor este mes"
            />
            <Button type="submit" disabled={ask.isPending}>
              {ask.isPending ? "Consultando…" : "Preguntar"}
            </Button>
          </form>

          {answer && (
            <div className="mt-6 space-y-3 border-t border-line pt-6">
              <div className="flex flex-wrap gap-2">
                {answer.tool && <Badge variant="sage">tool · {answer.tool}</Badge>}
                <Badge variant="rose">{answer.mode}</Badge>
              </div>
              <p className="whitespace-pre-wrap text-green-900">{answer.answer}</p>
              {!!answer.sources?.length && (
                <ul className="space-y-2 text-sm text-text-muted">
                  {answer.sources.map((s, i) => (
                    <li key={`${s.title}-${i}`}>
                      [{s.kind}] {s.title || "doc"} · {s.score} — {s.chunk.slice(0, 120)}…
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </Card>

        <Card tone="warm-white">
          <h2 className="font-serif text-2xl text-green-900">Conocimiento</h2>
          <p className="mt-1 text-sm text-text-muted">Ingesta (ADMIN) y listado reciente.</p>
          <form onSubmit={onIngest} className="mt-4 space-y-3">
            <Input
              value={doc.title}
              onChange={(e) => setDoc((d) => ({ ...d, title: e.target.value }))}
              placeholder="Título"
            />
            <Input
              value={doc.kind}
              onChange={(e) => setDoc((d) => ({ ...d, kind: e.target.value }))}
              placeholder="POLICY | PRODUCT | CASE…"
            />
            <textarea
              className="min-h-28 w-full rounded-[16px] border border-line bg-cream-100 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-sage-500/30"
              value={doc.content}
              onChange={(e) => setDoc((d) => ({ ...d, content: e.target.value }))}
              placeholder="Contenido a indexar…"
            />
            <Button type="submit" variant="outline" disabled={ingest.isPending}>
              Indexar documento
            </Button>
          </form>

          <ul className="mt-6 space-y-3">
            {(docs.data || []).slice(0, 8).map((d) => (
              <li key={d.id} className="rounded-[16px] border border-line px-4 py-3">
                <div className="flex items-center gap-2">
                  <Badge variant="dark">{d.kind}</Badge>
                  <span className="text-sm text-green-900">{d.title || "Sin título"}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-text-muted">{d.content}</p>
              </li>
            ))}
            {!docs.data?.length && (
              <p className="text-sm text-text-soft">Aún no hay documentos indexados.</p>
            )}
          </ul>
        </Card>
      </div>
    </div>
  );
}
