import { type Page, expect, test } from "@playwright/test";

import { INTERNSHIP, PNG, type Mock, mockApi } from "./support/receipts-mock";

/**
 * The Receipt Designer and Generated Receipts in a real browser, on the production build, with the real pdf.js drawing a genuine PDF
 * (made by the backend's receipt renderer). Nothing about the PDF viewer is mocked.
 */

let mock: Mock;
let problems: string[];

test.beforeEach(async ({ page }) => {
  problems = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("console", (m) => m.type() === "error" && problems.push(`console: ${m.text()}`));
  mock = await mockApi(page);
});
test.afterEach(() => {
  expect(mock.unhandled, "the page asked for an API this test does not stub").toEqual([]);
  // (the 404s are the account being none of student/employee/trainer, which the app expects and handles)
  expect(problems.filter((p) => !/favicon|Failed to load resource: the server responded with a status of 404/.test(p))).toEqual([]);
});

async function openDesigner(page: Page) {
  await page.goto(`/our-internships/${INTERNSHIP}`);
  await page.getByRole("tab", { name: "Onboarding Settings" }).click();
  await page.getByRole("tab", { name: "Receipt Designer" }).click();
  await expect(page.getByTestId("settings-panel")).toBeVisible();
}

/** The pane has really drawn the page: a canvas with ink on it, and no error message. */
async function expectPdfDrawn(page: Page, host = '[data-testid="pdf-pages"]') {
  const canvas = page.locator(`${host} canvas`).first();
  await expect(canvas).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("could not be shown here")).toHaveCount(0);
  const dark = await canvas.evaluate((c: HTMLCanvasElement) => {
    const { data } = c.getContext("2d")!.getImageData(0, 0, c.width, c.height);
    let n = 0;
    for (let i = 0; i < data.length; i += 4) if (data[i] < 120 && data[i + 1] < 120 && data[i + 2] < 120 && data[i + 3] > 0) n++;
    return n;
  });
  expect(dark, "the drawn page has text on it").toBeGreaterThan(200);
}

const positions = (page: Page) =>
  page.evaluate(() => {
    const main = document.querySelector("main")!;
    const panel = document.querySelector('[data-testid="settings-panel"]')!;
    return { win: [window.scrollX, window.scrollY], main: [main.scrollLeft, main.scrollTop], panel: panel.scrollTop };
  });

/** No horizontal overflow anywhere that scrolls: the document, the app shell's content area, and the designer itself. */
async function expectNoHorizontalOverflow(page: Page) {
  const over = await page.evaluate(() => {
    const out: string[] = [];
    const vw = document.documentElement.clientWidth;
    if (document.documentElement.scrollWidth > vw) out.push(`document ${document.documentElement.scrollWidth} > ${vw}`);
    if (document.body.scrollWidth > vw) out.push(`body ${document.body.scrollWidth} > ${vw}`);
    const main = document.querySelector("main")!;
    if (main.scrollWidth > main.clientWidth) out.push(`main ${main.scrollWidth} > ${main.clientWidth}`);
    const designer = document.querySelector('[data-testid="settings-panel"]')!.parentElement!;
    if (designer.scrollWidth > designer.clientWidth) out.push(`designer ${designer.scrollWidth} > ${designer.clientWidth}`);
    const box = main.getBoundingClientRect();
    for (const el of designer.querySelectorAll<HTMLElement>("*")) {
      if (el.closest('[data-testid="pdf-pages"]')) continue; // the pane scrolls inside itself, by design
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.right > box.right + 1) out.push(`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)} ends at ${Math.round(r.right)} (> ${Math.round(box.right)})`);
    }
    return out.slice(0, 8);
  });
  expect(over).toEqual([]);
}

for (const [name, size] of [
  ["desktop", { width: 1366, height: 768 }],
  ["mobile", { width: 390, height: 844 }],
] as const) {
  test.describe(name, () => {
    test.use({ viewport: size });

    test("draws the preview with the real pdf.js, with no error and no horizontal overflow", async ({ page }) => {
      await openDesigner(page);
      await expectPdfDrawn(page);
      await expect(page.getByTestId("page-count")).toHaveText("1 page");
      await expectNoHorizontalOverflow(page);
    });

    test("an upload selects the image and the page does not move", async ({ page }) => {
      await openDesigner(page);
      await expectPdfDrawn(page);
      await page.locator("main").evaluate((m) => (m.scrollTop = 120));
      await page.getByTestId("settings-panel").evaluate((p) => (p.scrollTop = 200));
      const before = await positions(page);
      const previews = mock.previews;
      await page.getByLabel("Upload Company logo").setInputFiles({ name: "company-logo.png", mimeType: "image/png", buffer: PNG });
      await expect(page.getByAltText("Company logo in use")).toBeVisible();
      await expect.poll(() => mock.previews, { timeout: 15_000 }).toBeGreaterThan(previews); // the preview was redrawn with the new image
      await expectPdfDrawn(page);
      expect(await positions(page)).toEqual(before);
      await expectNoHorizontalOverflow(page);
    });

    test("changing the design redraws the preview without moving the page", async ({ page }) => {
      await openDesigner(page);
      await expectPdfDrawn(page);
      await page.locator("#thank-you").fill("Thanks"); // (typing scrolls the field into view: that is the person's own action)
      await page.locator("main").evaluate((m) => (m.scrollTop += 0));
      const before = await positions(page);
      const previews = mock.previews;
      await page.locator("#thank-you").pressSequentially(" from the test");
      await expect.poll(() => mock.previews, { timeout: 15_000 }).toBeGreaterThan(previews);
      await expectPdfDrawn(page);
      expect(await positions(page)).toEqual(before);
    });
  });
}

for (const width of [1024, 1180, 1280]) {
  test(`no horizontal overflow at a laptop-sized window (${width}px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 720 });
    await openDesigner(page);
    await expectPdfDrawn(page);
    await expectNoHorizontalOverflow(page);
  });
}

test("the preview can be downloaded as a real PDF", async ({ page }) => {
  await openDesigner(page);
  await expectPdfDrawn(page);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download" }).click()]);
  expect(download.suggestedFilename()).toBe("receipt-sample.pdf");
  const file = await download.createReadStream();
  const head: Buffer[] = [];
  for await (const chunk of file) head.push(chunk as Buffer);
  expect(Buffer.concat(head).subarray(0, 5).toString()).toBe("%PDF-");
});

test("zooming draws the page again at the new size", async ({ page }) => {
  await openDesigner(page);
  await expectPdfDrawn(page);
  const width = () => page.locator('[data-testid="pdf-pages"] canvas').first().evaluate((c: HTMLCanvasElement) => c.getBoundingClientRect().width);
  const first = await width();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect.poll(width).toBeGreaterThan(first);
  await expectPdfDrawn(page);
});

test("Generated Receipts shows an issued document", async ({ page }) => {
  await page.goto(`/our-internships/${INTERNSHIP}`);
  await page.getByRole("tab", { name: "Onboarding", exact: true }).click();
  await page.getByRole("tab", { name: "Generated receipts" }).click();
  await page.getByRole("button", { name: /View RCPT-2026-000001/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expectPdfDrawn(page, '[role="dialog"] [data-testid="pdf-pages"]');
  await expect(page.getByText("exactly as it was issued")).toBeVisible();
});
