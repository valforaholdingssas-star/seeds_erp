import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/lib/apiClient";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { FieldLabel, Input } from "@/components/ui/Input";
import { BrandLogo } from "@/components/brand/BrandLogo";

export function PasswordResetPage() {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [step, setStep] = useState<"request" | "confirm">("request");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onRequest(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.post<{ detail: string; debug_token?: string }>(
        "/auth/password-reset/",
        { email },
      );
      setMsg(data.detail || "Si el email existe, enviamos instrucciones.");
      if (data.debug_token) {
        setToken(data.debug_token);
        setStep("confirm");
        setMsg("Sandbox: usa el token de depuración para confirmar.");
      } else {
        setStep("confirm");
      }
    } catch {
      setError("No se pudo iniciar el restablecimiento.");
    } finally {
      setLoading(false);
    }
  }

  async function onConfirm(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiClient.post("/auth/password-reset/confirm/", { token, password });
      setMsg("Contraseña actualizada. Ya puedes entrar.");
    } catch {
      setError("Token inválido o expirado.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <div className="pointer-events-none absolute inset-0 bg-green-900" />
      <div
        className="pointer-events-none absolute inset-0 opacity-50"
        style={{
          background:
            "radial-gradient(ellipse at 20% 20%, rgba(98,152,108,.35), transparent 45%), radial-gradient(ellipse at 80% 70%, rgba(94,6,4,.18), transparent 40%)",
        }}
      />
      <div className="relative z-10 w-full max-w-md animate-[fade-up_520ms_var(--ease-soft)]">
        <div className="mb-8 text-center text-text-on-dark">
          <BrandLogo size="login" className="mb-5" />
          <h1 className="font-serif text-4xl tracking-tight">Recuperar acceso</h1>
          <p className="mt-3 text-text-on-dark-muted">
            Un gesto pequeño para volver a entrar.
          </p>
        </div>
        <form
          onSubmit={step === "request" ? onRequest : onConfirm}
          className="rounded-[40px] border border-line bg-cream-100 p-8 shadow-[var(--shadow-2)]"
        >
          <div className="space-y-5">
            {step === "request" ? (
              <div>
                <FieldLabel>Email</FieldLabel>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            ) : (
              <>
                <div>
                  <FieldLabel>Token</FieldLabel>
                  <Input value={token} onChange={(e) => setToken(e.target.value)} required />
                </div>
                <div>
                  <FieldLabel>Nueva contraseña</FieldLabel>
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                </div>
              </>
            )}
            {error && <Alert variant="error">{error}</Alert>}
            {msg && <Alert variant="success">{msg}</Alert>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading
                ? "…"
                : step === "request"
                  ? "Enviar enlace"
                  : "Guardar contraseña"}
            </Button>
            <Link to="/login" className="block text-center text-sm text-text-muted">
              Volver al login
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
