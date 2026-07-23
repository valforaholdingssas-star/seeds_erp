import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";

type IntegrationStatus = {
  envia: { mode: string; ok: boolean; message: string };
  alegra: { mode: string; ok: boolean; message: string };
};

type Props = {
  /** Which providers to warn about */
  providers?: Array<"envia" | "alegra">;
};

export function MockModeBanner({ providers = ["envia", "alegra"] }: Props) {
  const status = useQuery({
    queryKey: ["integration-status"],
    queryFn: async () => {
      const { data } = await apiClient.get<IntegrationStatus>("/config/integration-status/");
      return data;
    },
    staleTime: 60_000,
    retry: 1,
  });

  if (!status.data) return null;

  const mocks = providers.filter((p) => status.data?.[p]?.mode === "mock");
  if (!mocks.length) return null;

  const labels = mocks.map((p) => (p === "envia" ? "Envia" : "Alegra")).join(" y ");

  return (
    <div className="flex flex-wrap items-start gap-3 rounded-[24px] border border-terracotta-600/25 bg-terracotta-600/10 px-5 py-4 text-sm text-green-900">
      <AlertTriangle strokeWidth={1.5} className="mt-0.5 h-5 w-5 shrink-0 text-terracotta-600" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">Modo mock activo · {labels}</p>
        <p className="mt-1 text-text-muted">
          Sin credenciales reales las guías/facturas se simulan. No se envían a DIAN ni a
          Envia. Configura tokens en{" "}
          <Link to="/settings" className="underline underline-offset-2 hover:text-green-950">
            Configuración
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
