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
    <div className="flex flex-wrap items-center gap-2 rounded-[16px] border border-terracotta-600/20 bg-terracotta-600/8 px-3 py-2 text-xs text-green-900">
      <AlertTriangle strokeWidth={1.5} className="h-3.5 w-3.5 shrink-0 text-terracotta-600" />
      <p className="min-w-0 flex-1">
        <span className="font-medium">Mock · {labels}</span>
        <span className="text-text-muted">
          {" "}
          — configura tokens en{" "}
          <Link to="/settings" className="underline underline-offset-2 hover:text-green-950">
            Configuración
          </Link>
          .
        </span>
      </p>
    </div>
  );
}
