import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState, type ComponentType } from "react";
import {
  LayoutDashboard,
  Users,
  Settings,
  MapPinned,
  LogOut,
  Leaf,
  Handshake,
  ShoppingBag,
  Truck,
  Package,
  Boxes,
  Receipt,
  ChartColumnBig,
  Contact,
  Sparkles,
  Menu,
  X,
  AlertTriangle,
  Percent,
  Search,
  ChevronDown,
  Wallet,
  ClipboardList,
  Shield,
  Landmark,
  ArrowLeftRight,
  Upload,
  Radar,
  Banknote,
  HandCoins,
} from "lucide-react";
import { fetchMe } from "@/features/auth/api";
import { useAuthStore, type UserRole } from "@/features/auth/store";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { BatchConsole } from "@/components/batch/BatchConsole";
import { BrandLogo } from "@/components/brand/BrandLogo";

type NavItem = {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string; strokeWidth?: number }>;
  end?: boolean;
  roles?: UserRole[];
  /** Module key for per-user permission overrides (`modules_effective`). */
  module?: string;
  keywords?: string[];
};

type NavGroup = {
  id: string;
  label: string;
  items: NavItem[];
};

const ALL_ROLES: UserRole[] = [
  "ADMIN",
  "VENTAS",
  "LOGISTICA",
  "CONTABILIDAD",
  "SUPERVISOR",
  "VIEWER",
];

const navGroups: NavGroup[] = [
  {
    id: "home",
    label: "General",
    items: [
      {
        to: "/",
        label: "Inicio",
        icon: LayoutDashboard,
        end: true,
        roles: ALL_ROLES,
        module: "home",
        keywords: ["home", "dashboard"],
      },
      {
        to: "/dashboard",
        label: "Torre de control",
        icon: Radar,
        roles: ALL_ROLES,
        module: "dashboard",
        keywords: ["alertas", "salud", "control", "indicadores"],
      },
    ],
  },
  {
    id: "comercial",
    label: "Comercial",
    items: [
      {
        to: "/sales",
        label: "Ventas",
        icon: ShoppingBag,
        roles: ALL_ROLES,
        module: "sales",
        keywords: ["consolidado", "pedidos", "woo", "kommo"],
      },
      {
        to: "/leads",
        label: "Leads",
        icon: Contact,
        roles: ["ADMIN", "VENTAS", "SUPERVISOR", "VIEWER"],
        module: "leads",
        keywords: ["pipeline", "kanban"],
      },
      {
        to: "/analytics",
        label: "Métricas",
        icon: ChartColumnBig,
        roles: ALL_ROLES,
        module: "analytics",
        keywords: ["looker", "graficos", "kpis"],
      },
      {
        to: "/ai",
        label: "Asistente",
        icon: Sparkles,
        roles: ["ADMIN", "VENTAS", "SUPERVISOR"],
        module: "ai",
        keywords: ["ia", "rag", "chat"],
      },
    ],
  },
  {
    id: "logistica",
    label: "Logística",
    items: [
      {
        to: "/logistics",
        label: "Envíos",
        icon: Truck,
        roles: ["ADMIN", "LOGISTICA", "VENTAS", "SUPERVISOR", "VIEWER"],
        module: "logistics",
        keywords: ["guias", "envia", "direccion"],
      },
      {
        to: "/dispatch",
        label: "Despachos",
        icon: Package,
        roles: ["ADMIN", "LOGISTICA", "SUPERVISOR", "VIEWER"],
        module: "dispatch",
        keywords: ["empacar", "cajas", "bodega"],
      },
    ],
  },
  {
    id: "inventario",
    label: "Inventario",
    items: [
      {
        to: "/inventory",
        label: "Productos",
        icon: Boxes,
        roles: ["ADMIN", "LOGISTICA", "SUPERVISOR", "VIEWER"],
        module: "inventory",
        keywords: ["stock", "sku"],
      },
      {
        to: "/inventory/materials",
        label: "Materiales",
        icon: Leaf,
        roles: ["ADMIN", "LOGISTICA", "SUPERVISOR", "VIEWER"],
        module: "inventory",
        keywords: ["insumos", "cajas", "bodega"],
      },
      {
        to: "/inventory/kardex",
        label: "Kardex",
        icon: ClipboardList,
        roles: ["ADMIN", "LOGISTICA", "SUPERVISOR", "VIEWER"],
        module: "inventory",
        keywords: ["movimientos", "entradas", "salidas"],
      },
    ],
  },
  {
    id: "contabilidad",
    label: "Contabilidad",
    items: [
      {
        to: "/accounting",
        label: "Facturas",
        icon: Receipt,
        roles: ["ADMIN", "CONTABILIDAD", "SUPERVISOR", "VIEWER"],
        module: "accounting",
        keywords: ["alegra", "dian"],
      },
      {
        to: "/accounting/refunds",
        label: "Reembolsos",
        icon: Receipt,
        roles: ["ADMIN", "CONTABILIDAD", "SUPERVISOR", "VIEWER"],
        module: "accounting",
        keywords: ["anulacion", "nota credito"],
      },
      {
        to: "/accounting/iva",
        label: "IVA",
        icon: Percent,
        roles: ["ADMIN", "CONTABILIDAD", "SUPERVISOR", "VIEWER"],
        module: "accounting",
        keywords: ["impuestos"],
      },
      {
        to: "/accounting/customers",
        label: "Clientes",
        icon: Users,
        roles: ["ADMIN", "CONTABILIDAD", "SUPERVISOR", "VIEWER"],
        module: "accounting",
        keywords: ["contacto", "cedula"],
      },
    ],
  },
  {
    id: "finanzas",
    label: "Finanzas",
    items: [
      {
        to: "/finance",
        label: "Modelo EFE",
        icon: Landmark,
        roles: ["ADMIN", "CONTABILIDAD", "SUPERVISOR", "VIEWER"],
        module: "finance",
        keywords: ["modelo", "presupuesto", "tesoreria"],
      },
      {
        to: "/finance/import",
        label: "Extractos",
        icon: Upload,
        roles: ["ADMIN", "CONTABILIDAD", "SUPERVISOR"],
        module: "finance",
        keywords: ["bancolombia", "csv", "importar", "nequi", "bold"],
      },
      {
        to: "/finance/movements",
        label: "Clasificación",
        icon: ArrowLeftRight,
        roles: ["ADMIN", "CONTABILIDAD", "SUPERVISOR", "VIEWER"],
        module: "finance",
        keywords: ["movimientos", "efe", "puc", "interbancario"],
      },
      {
        to: "/finance/audit",
        label: "Auditoría ingresos",
        icon: ChartColumnBig,
        roles: ["ADMIN", "CONTABILIDAD", "SUPERVISOR", "VIEWER"],
        module: "finance",
        keywords: ["validacion", "bancos", "reportes", "cuadre"],
      },
      {
        to: "/expenses/payables",
        label: "Por pagar",
        icon: HandCoins,
        roles: ["ADMIN", "CONTABILIDAD", "SUPERVISOR", "VIEWER"],
        module: "expenses",
        keywords: ["reembolsos", "cuentas por pagar", "notion", "obligaciones"],
      },
      {
        to: "/expenses",
        label: "Gastos",
        icon: Banknote,
        roles: ["ADMIN", "CONTABILIDAD", "SUPERVISOR", "VIEWER"],
        module: "expenses",
        keywords: ["reembolsos", "iva", "amortizacion", "comprobante"],
      },
    ],
  },
  {
    id: "integraciones",
    label: "Integraciones",
    items: [
      {
        to: "/integrations/events",
        label: "Eventos fallidos",
        icon: AlertTriangle,
        roles: ["ADMIN", "VENTAS", "SUPERVISOR"],
        module: "integrations",
        keywords: ["webhooks", "recovery", "errores"],
      },
    ],
  },
  {
    id: "parametros",
    label: "Parametrización",
    items: [
      {
        to: "/sellers",
        label: "Vendedores",
        icon: Handshake,
        roles: ["ADMIN"],
        module: "sellers",
        keywords: ["comerciales", "metas"],
      },
      {
        to: "/payment-methods",
        label: "Medios de pago",
        icon: Wallet,
        roles: ["ADMIN"],
        module: "payment_methods",
        keywords: ["nequi", "efectivo", "cuenta"],
      },
      {
        to: "/pack-rules",
        label: "Pack rules",
        icon: Package,
        roles: ["ADMIN"],
        module: "pack_rules",
        keywords: ["woo", "multiplicador", "kits"],
      },
      {
        to: "/users",
        label: "Usuarios",
        icon: Users,
        roles: ["ADMIN"],
        module: "users",
        keywords: ["roles", "permisos", "equipo", "contraseña"],
      },
      {
        to: "/roles",
        label: "Roles",
        icon: Shield,
        roles: ["ADMIN"],
        module: "roles",
        keywords: ["permisos", "matriz", "módulos"],
      },
      {
        to: "/geo",
        label: "Geografía",
        icon: MapPinned,
        roles: ["ADMIN", "LOGISTICA", "SUPERVISOR"],
        module: "geo",
        keywords: ["ciudades", "municipios"],
      },
      {
        to: "/settings",
        label: "Configuración",
        icon: Settings,
        roles: ["ADMIN"],
        module: "settings",
        keywords: ["api", "secrets", "woo", "alegra", "envia"],
      },
    ],
  },
];

function itemMatches(item: NavItem, q: string) {
  if (!q) return true;
  const hay = [item.label, item.to, ...(item.keywords || [])].join(" ").toLowerCase();
  return hay.includes(q);
}

function pathInGroup(pathname: string, group: NavGroup) {
  return group.items.some((item) => {
    if (item.end) return pathname === item.to;
    if (item.to === "/") return pathname === "/";
    return pathname === item.to || pathname.startsWith(`${item.to}/`);
  });
}

function SidebarNav({
  onNavigate,
}: {
  onNavigate?: () => void;
}) {
  const user = useAuthStore((s) => s.user);
  const location = useLocation();
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const role = user?.role;
  const modules = user?.modules_effective;
  const perms = user?.permissions_effective;

  const visibleGroups = useMemo(() => {
    const q = query.trim().toLowerCase();
    return navGroups
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => {
          if (item.module && perms) {
            if (!perms[item.module]?.r) return false;
          } else if (modules?.length && item.module) {
            if (!modules.includes(item.module)) return false;
          } else if (role && item.roles && !item.roles.includes(role)) {
            return false;
          }
          return itemMatches(item, q);
        }),
      }))
      .filter((g) => g.items.length > 0);
  }, [query, role, modules, perms]);

  function isOpen(group: NavGroup) {
    if (query.trim()) return true;
    if (collapsed[group.id] === false) return false;
    if (collapsed[group.id] === true) return true;
    // default: open if current route belongs here, else open first commercial groups
    if (pathInGroup(location.pathname, group)) return true;
    return group.id === "home" || group.id === "comercial";
  }

  function toggle(groupId: string, currentlyOpen: boolean) {
    setCollapsed((prev) => ({ ...prev, [groupId]: !currentlyOpen }));
  }

  return (
    <>
      <div className="relative z-10 border-b border-line-dark px-3 pb-4 pt-1">
        <label className="relative block">
          <Search
            strokeWidth={1.5}
            className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-on-dark-muted"
          />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar en el menú…"
            className="w-full rounded-[14px] border border-line-dark bg-green-950/40 py-2.5 pl-9 pr-3 text-sm text-text-on-dark placeholder:text-text-on-dark-muted/70 outline-none transition-colors focus:border-sage-500/40"
          />
        </label>
      </div>

      <nav className="relative z-10 flex-1 space-y-4 overflow-y-auto px-3 py-4">
        {visibleGroups.length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-text-on-dark-muted">
            Sin resultados para “{query}”
          </p>
        ) : null}

        {visibleGroups.map((group) => {
          const open = isOpen(group);
          const singleHome = group.id === "home" && group.items.length === 1 && !query;

          if (singleHome) {
            const item = group.items[0];
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-[16px] px-3 py-3 label-caps transition-all duration-[160ms] ease-soft",
                    isActive
                      ? "bg-text-on-dark/10 text-text-on-dark"
                      : "text-text-on-dark-muted hover:bg-text-on-dark/5 hover:text-text-on-dark",
                  )
                }
              >
                <item.icon strokeWidth={1.5} className="h-4 w-4" />
                {item.label}
              </NavLink>
            );
          }

          return (
            <div key={group.id} className="space-y-1">
              <button
                type="button"
                onClick={() => toggle(group.id, open)}
                className="flex w-full items-center justify-between rounded-[12px] px-3 py-2 text-left transition-colors hover:bg-text-on-dark/5"
              >
                <span className="label-caps text-[10px] tracking-[0.18em] text-text-on-dark-muted">
                  {group.label}
                </span>
                <ChevronDown
                  strokeWidth={1.5}
                  className={cn(
                    "h-3.5 w-3.5 text-text-on-dark-muted transition-transform duration-[160ms] ease-soft",
                    open ? "rotate-0" : "-rotate-90",
                  )}
                />
              </button>

              {open ? (
                <div className="space-y-0.5">
                  {group.items.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center gap-3 rounded-[16px] px-3 py-2.5 label-caps transition-all duration-[160ms] ease-soft",
                          isActive
                            ? "bg-text-on-dark/10 text-text-on-dark"
                            : "text-text-on-dark-muted hover:bg-text-on-dark/5 hover:text-text-on-dark",
                        )
                      }
                    >
                      <item.icon strokeWidth={1.5} className="h-4 w-4 shrink-0" />
                      <span className="truncate">{item.label}</span>
                    </NavLink>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </nav>
    </>
  );
}

export function AppShell() {
  const user = useAuthStore((s) => s.user);
  const access = useAuthStore((s) => s.access);
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!access) return;
    let cancelled = false;
    void (async () => {
      try {
        const me = await fetchMe();
        if (!cancelled) setUser(me);
      } catch {
        // keep cached session; 401 interceptor handles logout
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [access, setUser]);

  const aside = (
    <aside className="seeds-panel-dark flex h-full w-[260px] shrink-0 flex-col text-text-on-dark">
      <div className="relative z-10 border-b border-line-dark px-6 py-6">
        <NavLink to="/" className="block" end onClick={() => setOpen(false)}>
          <BrandLogo size="sidebar" />
          <p className="label-caps mt-2 text-text-on-dark-muted">ERP</p>
        </NavLink>
      </div>

      <SidebarNav onNavigate={() => setOpen(false)} />

      <div className="relative z-10 border-t border-line-dark px-4 py-5">
        <div className="mb-4 rounded-[20px] bg-green-950/50 px-3 py-3">
          <p className="text-sm text-text-on-dark">{user?.full_name}</p>
          <p className="mt-1 text-xs text-text-on-dark-muted">{user?.email}</p>
          <div className="mt-3">
            <Badge variant="sage">{user?.role}</Badge>
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            logout();
            navigate("/login");
          }}
          className="flex w-full items-center gap-2 rounded-[16px] px-3 py-2.5 text-left label-caps text-text-on-dark-muted transition-colors duration-[160ms] hover:bg-text-on-dark/5 hover:text-text-on-dark"
        >
          <LogOut strokeWidth={1.5} className="h-4 w-4" />
          Cerrar sesión
        </button>
      </div>
    </aside>
  );

  return (
    <div className="flex min-h-screen">
      <div className="sticky top-0 hidden h-screen lg:flex">{aside}</div>

      {open && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-green-950/50"
            aria-label="Cerrar menú"
            onClick={() => setOpen(false)}
          />
          <div className="relative z-10 h-full shadow-[var(--shadow-3)]">{aside}</div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-cream-100/85 px-4 py-2.5 backdrop-blur-md lg:hidden">
          <button
            type="button"
            className="rounded-[12px] border border-line p-2 text-green-900"
            onClick={() => setOpen(true)}
            aria-label="Abrir menú"
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
          <BrandLogo size="sm" className="opacity-90 brightness-0" />
        </div>
        <main className="animate-[fade-up_520ms_var(--ease-soft)] flex-1 px-4 py-4 sm:px-8 sm:py-5">
          <Outlet />
        </main>
        <BatchConsole />
      </div>
    </div>
  );
}
