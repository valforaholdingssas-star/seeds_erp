import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "@/app/layout/AppShell";
import {
  RequireAuth,
  RequireAdmin,
  RequireSalesAccess,
  RequireLogisticsAccess,
  RequireInventoryAccess,
  RequireAccountingAccess,
  RequireFinanceAccess,
  RequireExpensesAccess,
  RequireDashboardAccess,
} from "@/features/auth/guards";
import { LoginPage } from "@/features/auth/LoginPage";
import { PasswordResetPage } from "@/features/auth/PasswordResetPage";
import { HomePage } from "@/features/home/HomePage";
import { UsersPage } from "@/features/users/UsersPage";
import { RolesPage } from "@/features/users/RolesPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { GeoPage } from "@/features/geo/GeoPage";
import { SellersPage } from "@/features/sellers/SellersPage";
import { SalesPage } from "@/features/sales/SalesPage";
import { SaleDetailPage } from "@/features/sales/SaleDetailPage";
import { PaymentMethodsPage } from "@/features/sales/PaymentMethodsPage";
import { InternalSaleFormPage } from "@/features/sales/InternalSaleFormPage";
import { ShipmentsPage } from "@/features/logistics/ShipmentsPage";
import { DispatchPage } from "@/features/logistics/DispatchPage";
import { ProductsPage } from "@/features/inventory/ProductsPage";
import { MaterialsPage } from "@/features/inventory/MaterialsPage";
import { KardexPage } from "@/features/inventory/KardexPage";
import { InvoicesPage } from "@/features/accounting/InvoicesPage";
import { CustomersPage } from "@/features/accounting/CustomersPage";
import { RefundsPage } from "@/features/accounting/RefundsPage";
import { IvaPage } from "@/features/accounting/IvaPage";
import { EfePage } from "@/features/finance/EfePage";
import { MovementsPage } from "@/features/finance/MovementsPage";
import { ImportPage } from "@/features/finance/ImportPage";
import { AuditPage } from "@/features/finance/AuditPage";
import { ExpensesPage } from "@/features/expenses/ExpensesPage";
import { ControlDashboardPage } from "@/features/dashboard/ControlDashboardPage";
import { LeadsPage } from "@/features/leads/LeadsPage";
import { AiPage } from "@/features/ai/AiPage";
import { AnalyticsPage } from "@/features/analytics/AnalyticsPage";
import { SalesImportPage } from "@/features/sales/SalesImportPage";
import { SalesResyncPage } from "@/features/sales/SalesResyncPage";
import { PackRulesPage } from "@/features/sales/PackRulesPage";
import { FailedEventsPage } from "@/features/integrations/FailedEventsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/password-reset" element={<PasswordResetPage />} />
          <Route element={<RequireAuth />}>
            <Route element={<AppShell />}>
              <Route index element={<HomePage />} />
              <Route path="geo" element={<GeoPage />} />
              <Route element={<RequireSalesAccess />}>
                <Route path="sales" element={<SalesPage />} />
                <Route path="sales/ferias" element={<InternalSaleFormPage mode="ferias" />} />
                <Route path="sales/manual" element={<InternalSaleFormPage mode="manual" />} />
                <Route path="sales/import" element={<SalesImportPage />} />
                <Route path="sales/resync" element={<SalesResyncPage />} />
                <Route path="sales/:id" element={<SaleDetailPage />} />
                <Route path="leads" element={<LeadsPage />} />
                <Route path="ai" element={<AiPage />} />
                <Route path="analytics" element={<AnalyticsPage />} />
                <Route path="integrations/events" element={<FailedEventsPage />} />
              </Route>
              <Route element={<RequireLogisticsAccess />}>
                <Route path="logistics" element={<ShipmentsPage />} />
                <Route path="dispatch" element={<DispatchPage />} />
              </Route>
              <Route element={<RequireInventoryAccess />}>
                <Route path="inventory" element={<ProductsPage />} />
                <Route path="inventory/materials" element={<MaterialsPage />} />
                <Route path="inventory/kardex" element={<KardexPage />} />
              </Route>
              <Route element={<RequireAccountingAccess />}>
                <Route path="accounting" element={<InvoicesPage />} />
                <Route path="accounting/customers" element={<CustomersPage />} />
                <Route path="accounting/refunds" element={<RefundsPage />} />
                <Route path="accounting/iva" element={<IvaPage />} />
              </Route>
              <Route element={<RequireFinanceAccess />}>
                <Route path="finance" element={<EfePage />} />
                <Route path="finance/movements" element={<MovementsPage />} />
                <Route path="finance/import" element={<ImportPage />} />
                <Route path="finance/audit" element={<AuditPage />} />
              </Route>
              <Route element={<RequireExpensesAccess />}>
                <Route path="expenses" element={<ExpensesPage />} />
              </Route>
              <Route element={<RequireDashboardAccess />}>
                <Route path="dashboard" element={<ControlDashboardPage />} />
              </Route>
              <Route element={<RequireAdmin />}>
                <Route path="sellers" element={<SellersPage />} />
                <Route path="payment-methods" element={<PaymentMethodsPage />} />
                <Route path="pack-rules" element={<PackRulesPage />} />
                <Route path="users" element={<UsersPage />} />
                <Route path="roles" element={<RolesPage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
