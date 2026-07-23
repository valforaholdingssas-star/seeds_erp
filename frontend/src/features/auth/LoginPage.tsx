import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate, Link } from "react-router-dom";
import { loginRequest } from "@/features/auth/api";
import { useAuthStore } from "@/features/auth/store";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { FieldLabel, Input } from "@/components/ui/Input";

export function LoginPage() {
  const access = useAuthStore((s) => s.access);
  const setSession = useAuthStore((s) => s.setSession);
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from || "/";

  const [email, setEmail] = useState("admin@seeds.co");
  const [password, setPassword] = useState("admin1234");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (access) return <Navigate to={from} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await loginRequest(email, password);
      setSession(data.access, data.refresh, data.user);
      navigate(from, { replace: true });
    } catch {
      setError("No pudimos entrar con esos datos. Revisa el email y la contraseña.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <div className="pointer-events-none absolute inset-0 bg-green-900" />
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            "radial-gradient(ellipse at 20% 20%, rgba(98,152,108,.35), transparent 45%), radial-gradient(ellipse at 80% 70%, rgba(202,150,151,.2), transparent 40%)",
        }}
      />
      <div className="relative z-10 w-full max-w-md animate-[fade-up_520ms_var(--ease-soft)]">
        <div className="mb-8 text-center text-text-on-dark">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-line-dark font-serif text-2xl">
            ee
          </div>
          <h1 className="font-serif text-5xl tracking-tight">
            Se<span className="spark">✦</span>eds
          </h1>
          <p className="mt-3 text-text-on-dark-muted">Entra para acompañar la operación del día.</p>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-[40px] border border-line bg-cream-100 p-8 shadow-[var(--shadow-2)] seeds-panel"
        >
          <div className="space-y-5">
            <div>
              <FieldLabel>Email</FieldLabel>
              <Input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="login-email"
              />
            </div>
            <div>
              <FieldLabel>Contraseña</FieldLabel>
              <Input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                data-testid="login-password"
              />
            </div>
            {error ? <Alert variant="error">{error}</Alert> : null}
            <Button type="submit" className="w-full" disabled={loading} data-testid="login-submit">
              {loading ? "Entrando…" : "Entrar"}
            </Button>
            <Link
              to="/password-reset"
              className="block text-center text-sm text-text-muted hover:text-green-900"
            >
              Recuperar contraseña
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
