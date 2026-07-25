import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore, type UserRole } from "@/features/auth/store";

export function RequireAuth() {
  const access = useAuthStore((s) => s.access);
  const location = useLocation();
  if (!access) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

export function RequireAdmin() {
  const user = useAuthStore((s) => s.user);
  if (user?.role !== "ADMIN") {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

const SALES_ROLES: UserRole[] = [
  "ADMIN",
  "VENTAS",
  "LOGISTICA",
  "CONTABILIDAD",
  "SUPERVISOR",
  "VIEWER",
];

export function RequireSalesAccess() {
  const user = useAuthStore((s) => s.user);
  if (!user || !SALES_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

const LOGISTICS_ROLES: UserRole[] = [
  "ADMIN",
  "LOGISTICA",
  "VENTAS",
  "SUPERVISOR",
  "VIEWER",
];

export function RequireLogisticsAccess() {
  const user = useAuthStore((s) => s.user);
  if (!user || !LOGISTICS_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

const INVENTORY_ROLES: UserRole[] = [
  "ADMIN",
  "LOGISTICA",
  "CONTABILIDAD",
  "SUPERVISOR",
  "VIEWER",
];

export function RequireInventoryAccess() {
  const user = useAuthStore((s) => s.user);
  if (!user || !INVENTORY_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

const ACCOUNTING_ROLES: UserRole[] = [
  "ADMIN",
  "CONTABILIDAD",
  "SUPERVISOR",
  "VIEWER",
  "VENTAS",
];

export function RequireAccountingAccess() {
  const user = useAuthStore((s) => s.user);
  if (!user || !ACCOUNTING_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

const FINANCE_ROLES: UserRole[] = [
  "ADMIN",
  "CONTABILIDAD",
  "SUPERVISOR",
  "VIEWER",
];

export function RequireFinanceAccess() {
  const user = useAuthStore((s) => s.user);
  if (!user || !FINANCE_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

const EXPENSES_ROLES: UserRole[] = [
  "ADMIN",
  "CONTABILIDAD",
  "SUPERVISOR",
  "VIEWER",
];

export function RequireExpensesAccess() {
  const user = useAuthStore((s) => s.user);
  if (!user || !EXPENSES_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

const DASHBOARD_ROLES: UserRole[] = [
  "ADMIN",
  "CONTABILIDAD",
  "SUPERVISOR",
  "VIEWER",
  "LOGISTICA",
  "VENTAS",
];

export function RequireDashboardAccess() {
  const user = useAuthStore((s) => s.user);
  if (!user || !DASHBOARD_ROLES.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
