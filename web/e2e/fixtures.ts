import { test as base } from "@playwright/test";

/** Every test starts past the welcome sequence unless it asks for it (welcome.spec.ts). */
export const test = base.extend<{ skipWelcome: boolean }>({
  skipWelcome: [true, { option: true }],
  // Playwright's fixture callback is named `use`; it is not a React hook.
  page: async ({ page, skipWelcome }, use) => {
    if (skipWelcome) {
      await page.addInitScript(() => {
        try {
          window.sessionStorage.setItem("ah:welcomed", "1");
        } catch {
          /* ignore */
        }
      });
    }
    // eslint-disable-next-line react-hooks/rules-of-hooks
    await use(page);
  },
});
export { expect } from "@playwright/test";
