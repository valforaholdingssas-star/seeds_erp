import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { apiClient } from "@/lib/apiClient";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { MockModeBanner } from "@/components/ui/MockModeBanner";
import { PageHeader } from "@/components/ui/PageHeader";

type SettingItem = {
  key: string;
  label: string;
  group: string;
  type: string;
  help: string;
  is_secret: boolean;
  is_set: boolean;
  masked: string | null;
  value: string | null;
  source: string;
};

type TestResult = { ok: boolean; message: string; mode?: string };

type WebhookUrl = {
  provider: string;
  topic: string;
  url: string;
  where: string;
};

type SyncResult = {
  ok: boolean;
  message: string;
  public_base_url: string;
  shopify?: { message?: string; created?: string[]; existing?: string[]; errors?: string[] };
  woocommerce?: { message?: string; updated?: unknown[]; errors?: string[] };
  manual?: Array<{ provider: string; action: string; url: string }>;
  webhook_urls?: WebhookUrl[];
};

const GROUP_ORDER = ["ENVIA", "ALEGRA", "WOOCOMMERCE", "SHOPIFY", "KOMMO", "AI", "BIGQUERY", "FINANZAS", "BUSINESS"];

export function SettingsPage() {
  const qc = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [testModes, setTestModes] = useState<Record<string, TestResult>>({});
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);

  const config = useQuery({
    queryKey: ["config"],
    queryFn: async () => {
      const { data } = await apiClient.get<{
        groups: string[];
        settings: SettingItem[];
        public_base_url?: string;
        webhook_urls?: WebhookUrl[];
      }>("/config/");
      return data;
    },
  });

  const save = useMutation({
    mutationFn: async (group: string) => {
      const items = (config.data?.settings || [])
        .filter((s) => s.group === group)
        .map((s) => ({
          key: s.key,
          value: drafts[s.key] ?? (s.is_secret ? "" : s.value ?? ""),
        }))
        .filter(
          (s) =>
            s.value !== "" ||
            !config.data?.settings.find((x) => x.key === s.key)?.is_secret,
        );
      await apiClient.patch("/config/", { settings: items });
    },
    onSuccess: () => {
      setMessage("Configuración guardada.");
      setDrafts({});
      qc.invalidateQueries({ queryKey: ["config"] });
      qc.invalidateQueries({ queryKey: ["integration-status"] });
    },
    onError: () => setMessage("No se pudo guardar. Revisa los valores."),
  });

  const test = useMutation({
    mutationFn: async (group: string) => {
      const { data } = await apiClient.post<TestResult>(`/config/${group}/test/`);
      return { group, data };
    },
    onSuccess: ({ group, data }) => {
      setTestModes((m) => ({ ...m, [group]: data }));
      setMessage(
        data.mode === "mock"
          ? `${group}: modo MOCK — ${data.message}`
          : `${group}: ${data.ok ? "OK" : "Error"} — ${data.message}`,
      );
      qc.invalidateQueries({ queryKey: ["integration-status"] });
    },
    onError: (err: unknown, group: string) => {
      const ax = err as {
        response?: { data?: { message?: string; ok?: boolean; mode?: string } };
        message?: string;
      };
      const data = ax.response?.data;
      const msg =
        data?.message || ax.message || "No se pudo probar la conexión.";
      setTestModes((m) => ({
        ...m,
        [group]: { ok: false, message: msg, mode: data?.mode || "live" },
      }));
      setMessage(`${group}: Error — ${msg}`);
    },
  });

  const syncInbound = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<SyncResult>("/config/sync-inbound-urls/");
      return data;
    },
    onSuccess: (data) => {
      setSyncResult(data);
      setMessage(data.message);
      qc.invalidateQueries({ queryKey: ["config"] });
    },
    onError: () => setMessage("No se pudo sincronizar webhooks al dominio público."),
  });

  const byGroup = useMemo(() => {
    const map: Record<string, SettingItem[]> = {};
    for (const s of config.data?.settings || []) {
      map[s.group] = map[s.group] || [];
      map[s.group].push(s);
    }
    return map;
  }, [config.data]);

  const webhookUrls = syncResult?.webhook_urls || config.data?.webhook_urls || [];
  const publicBase = syncResult?.public_base_url || config.data?.public_base_url || "";

  return (
    <div className="space-y-3">
      <PageHeader eyebrow="Configuración" title="Integraciones y parámetros" />

      <MockModeBanner />

      {message ? <Alert variant="info">{message}</Alert> : null}

      <Card>
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-serif text-2xl text-green-900">URL pública y webhooks</h2>
            <p className="mt-1 text-sm text-text-muted">
              Dominio HTTPS del ERP. Migra Woo/Shopify desde la IP antigua; Kommo y el
              plugin WP se actualizan a mano.
            </p>
            {publicBase ? (
              <p className="mt-2 text-sm text-green-900">
                Base actual: <span className="font-medium">{publicBase}</span>
              </p>
            ) : null}
          </div>
          <Button
            type="button"
            size="sm"
            disabled={syncInbound.isPending}
            onClick={() => syncInbound.mutate()}
          >
            {syncInbound.isPending ? "Sincronizando…" : "Sincronizar webhooks"}
          </Button>
        </div>

        {webhookUrls.length ? (
          <div className="space-y-2">
            {webhookUrls.map((w) => (
              <div
                key={`${w.provider}-${w.topic}`}
                className="rounded-[16px] border border-line bg-warm-white px-4 py-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="dark">{w.provider}</Badge>
                  <span className="text-xs label-caps text-text-soft">{w.topic}</span>
                </div>
                <p className="mt-1 break-all text-sm text-green-900">{w.url}</p>
                <p className="mt-1 text-xs text-text-soft">{w.where}</p>
              </div>
            ))}
          </div>
        ) : null}

        {syncResult?.manual?.length ? (
          <div className="mt-4 space-y-2">
            <p className="text-sm font-medium text-green-900">Pasos manuales</p>
            {syncResult.manual.map((m) => (
              <div key={m.provider} className="text-sm text-text-muted">
                <span className="text-green-900">{m.provider}:</span> {m.action}
                {m.url ? (
                  <>
                    {" "}
                    → <span className="break-all text-green-900">{m.url}</span>
                  </>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </Card>

      <div className="space-y-6">
        {GROUP_ORDER.filter((g) => byGroup[g]).map((group) => {
          const result = testModes[group];
          return (
            <Card key={group}>
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-serif text-2xl text-green-900">{group}</h2>
                    {result?.mode === "mock" ? (
                      <Badge variant="terracotta">MOCK</Badge>
                    ) : null}
                    {result?.ok && result?.mode === "live" ? (
                      <Badge variant="sage">LIVE</Badge>
                    ) : null}
                    {result && !result.ok && result.mode !== "mock" ? (
                      <Badge variant="wine">ERROR</Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 text-sm text-text-muted">
                    Valores efectivos desde panel, entorno o default.
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={test.isPending && test.variables === group}
                    onClick={() => test.mutate(group)}
                  >
                    {test.isPending && test.variables === group
                      ? "Probando…"
                      : "Probar conexión"}
                  </Button>
                  <Button type="button" size="sm" onClick={() => save.mutate(group)}>
                    Guardar
                  </Button>
                </div>
              </div>

              {result ? (
                <Alert variant={result.ok ? "info" : "error"} className="mb-4">
                  {result.ok ? "Conexión OK" : "Falló la prueba"}: {result.message}
                </Alert>
              ) : null}

              <div className="grid gap-4 md:grid-cols-2">
                {byGroup[group].map((setting) => (
                  <div key={setting.key}>
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <FieldLabel>{setting.label}</FieldLabel>
                      <Badge variant={setting.is_set ? "sage" : "terracotta"}>
                        {setting.is_set ? setting.source : "sin valor"}
                      </Badge>
                    </div>
                    <Input
                      type={setting.is_secret ? "password" : "text"}
                      placeholder={
                        setting.is_secret
                          ? setting.masked || "••••"
                          : setting.value || String(setting.value ?? "")
                      }
                      value={
                        drafts[setting.key] ??
                        (setting.is_secret ? "" : setting.value ?? "")
                      }
                      onChange={(e) =>
                        setDrafts((d) => ({ ...d, [setting.key]: e.target.value }))
                      }
                    />
                    {setting.help ? (
                      <p className="mt-1.5 text-xs text-text-soft">{setting.help}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
