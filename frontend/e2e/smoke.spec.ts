import { expect, test } from "@playwright/test";

test.describe("Seeds ERP smoke", () => {
  test("login → home → ventas", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByTestId("login-submit")).toBeVisible();

    await page.getByTestId("login-email").fill("admin@seeds.co");
    await page.getByTestId("login-password").fill("admin1234");
    await page.getByTestId("login-submit").click();

    await expect(page.getByText(/Hola,/i)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/Entorno · sandbox/i)).toBeVisible();

    await page.getByRole("link", { name: "Ventas" }).first().click();
    await expect(page.getByRole("heading", { name: "Consolidado" })).toBeVisible({
      timeout: 15_000,
    });
  });

  test("recuperar contraseña es accesible", async ({ page }) => {
    await page.goto("/password-reset");
    await expect(page.getByRole("heading", { name: /Recuperar acceso/i })).toBeVisible();
  });
});
