import { type Page, expect, test } from "@playwright/test";

import { INTERNSHIP, mockApi } from "./support/receipts-mock";

/**
 * How tall the Receipt Designer page is and what scrolls, in a real browser on the production build.
 *
 * What went wrong before: three hidden file inputs were positioned against the whole window instead of their own box, so the *document*
 * (not just the app's content area) could be scrolled through thousands of pixels of blank space; and below 1280px the settings column
 * was unbounded (about 6,000px tall) with the preview thousands of pixels further down the page.
 *
 * Browser zoom changes the CSS size of the window, so a zoom level is tested as the window size it produces: 125% of 1366x768 is 1093x614,
 * 150% is 911x512 and 200% is 683x384.
 */

const SIZES = [
  { name: "phone", width: 390, height: 844 },
  { name: "1024", width: 1024, height: 768 },
  { name: "1180", width: 1180, height: 720 },
  { name: "1280", width: 1280, height: 720 },
  { name: "1366", width: 1366, height: 768 },
  { name: "1366 at 125% zoom", width: 1093, height: 614 },
  { name: "1366 at 150% zoom", width: 911, height: 512 },
  { name: "1366 at 200% zoom", width: 683, height: 384 },
  { name: "1280 at 150% zoom", width: 853, height: 480 },
];

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

async function openDesigner(page: Page) {
  await page.goto(`/our-internships/${INTERNSHIP}`);
  await page.getByRole("tab", { name: "Onboarding Settings" }).click();
  await page.getByRole("tab", { name: "Receipt Designer" }).click();
  await page.getByTestId("pdf-pages").locator("canvas").first().waitFor({ timeout: 20_000 });
}

const measure = (page: Page) =>
  page.evaluate(() => {
    const de = document.documentElement;
    const main = document.querySelector("main")!;
    const panel = document.querySelector<HTMLElement>('[data-testid="settings-panel"]')!;
    const grid = panel.parentElement!;
    const preview = grid.children[1] as HTMLElement;
    const host = document.querySelector<HTMLElement>('[data-testid="pdf-pages"]')!;
    const mainTop = main.getBoundingClientRect().top;
    const rel = (r: DOMRect) => ({ top: r.top - mainTop + main.scrollTop, bottom: r.bottom - mainTop + main.scrollTop, left: r.left, right: r.right });
    return {
      viewport: { w: innerWidth, h: innerHeight },
      doc: { scrollHeight: de.scrollHeight, scrollWidth: de.scrollWidth },
      main: { client: main.clientHeight, scroll: main.scrollHeight },
      grid: rel(grid.getBoundingClientRect()),
      panel: { ...rel(panel.getBoundingClientRect()), client: panel.clientHeight, scroll: panel.scrollHeight, overflowY: getComputedStyle(panel).overflowY },
      preview: rel(preview.getBoundingClientRect()),
      host: { overflowY: getComputedStyle(host).overflowY, overflowX: getComputedStyle(host).overflowX },
      aside: !!document.querySelector("aside") && getComputedStyle(document.querySelector("aside")!).display !== "none",
    };
  });

for (const size of SIZES) {
  test.describe(`${size.name} (${size.width}x${size.height})`, () => {
    test.use({ viewport: { width: size.width, height: size.height } });

    test("the page has no blank scrolling, and what scrolls is the content area and the columns", async ({ page }) => {
      await openDesigner(page);
      const m = await measure(page);

      // 1. the window itself never scrolls: the app fills the screen and nothing sticks out below it
      expect(m.doc.scrollHeight, "document height").toBeLessThanOrEqual(m.viewport.h + 1);
      expect(m.doc.scrollWidth, "document width").toBeLessThanOrEqual(m.viewport.w + 1);
      await page.evaluate(() => window.scrollTo(0, 100_000));
      expect(await page.evaluate(() => window.scrollY)).toBe(0);

      // 2. no empty region after the designer: the content area ends where the designer ends (plus the page's own bottom padding)
      expect(m.main.scroll - m.grid.bottom, "blank space under the designer").toBeLessThanOrEqual(64);

      if (size.width >= 1024) {
        // side by side, level with each other, each at most as tall as the visible area, so both can be reached by scrolling the page once
        expect(m.preview.left).toBeGreaterThanOrEqual(m.panel.right - 1);
        expect(Math.abs(m.preview.top - m.panel.top)).toBeLessThanOrEqual(2);
        const column = m.panel.bottom - m.panel.top;
        expect(column, "column height").toBeLessThanOrEqual(Math.max(m.main.client, 416) + 1);
        // the settings scroll on their own (they are far taller than the column), and so does the preview
        expect(m.panel.overflowY).toBe("auto");
        expect(m.panel.scroll).toBeGreaterThan(m.panel.client + 200);
        expect(m.host.overflowY).toBe("auto");
        // the page scrolls by no more than the header above the designer, not by the length of the settings
        expect(m.main.scroll - m.main.client, "page scroll distance").toBeLessThanOrEqual(m.grid.top + 64);
      } else {
        // stacked: ordinary page scrolling, the settings are not a scroll box of their own
        expect(m.preview.top).toBeGreaterThanOrEqual(m.panel.bottom - 1);
        expect(m.panel.scroll).toBeLessThanOrEqual(m.panel.client + 1);
        expect(m.main.scroll).toBeGreaterThan(m.main.client);
      }
    });

    test("the controls can all be reached and still work", async ({ page }) => {
      await openDesigner(page);
      if (size.width >= 1024) {
        // side by side: at the bottom of the page the preview's controls and the Save bar are on screen together
        await page.locator("main").evaluate((m) => (m.scrollTop = m.scrollHeight));
        await expect(page.getByRole("button", { name: "Save design" })).toBeInViewport();
      } else {
        // stacked: the preview's controls are reached by scrolling down the page, like everything else
        await page.getByRole("button", { name: "Download" }).scrollIntoViewIfNeeded();
      }
      await expect(page.getByRole("button", { name: "Download" })).toBeInViewport();
      await expect(page.getByRole("button", { name: "Zoom in" })).toBeInViewport();
      const canvas = page.locator('[data-testid="pdf-pages"] canvas').first();
      const before = (await canvas.boundingBox())!.width;
      await page.getByRole("button", { name: "Zoom in" }).click();
      await expect.poll(async () => (await canvas.boundingBox())?.width ?? 0).toBeGreaterThan(before); // (the page is swapped in one step, so there can be an instant with none)
      // the sidebar is there when the window is wide enough for it, and the tabs still switch
      if (size.width >= 768) expect((await measure(page)).aside).toBe(true);
      await page.getByRole("tab", { name: "Onboarding", exact: true }).click();
      await expect(page.getByRole("tab", { name: "Generated receipts" })).toBeVisible();
    });
  });
}

test("the settings column scrolls inside itself and leaves the page where it is", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openDesigner(page);
  const panel = page.getByTestId("settings-panel");
  await panel.hover(); // (moving the pointer onto it may bring it into view: measure after that)
  const before = await page.evaluate(() => ({ main: document.querySelector("main")!.scrollTop, win: window.scrollY }));
  await page.mouse.wheel(0, 600);
  await expect.poll(() => panel.evaluate((p) => p.scrollTop)).toBeGreaterThan(0);
  const after = await page.evaluate(() => ({ main: document.querySelector("main")!.scrollTop, win: window.scrollY }));
  expect(after).toEqual(before);
});
