// @vitest-environment happy-dom
import { act } from "react";
import { type Root, createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PdfPane } from "@/features/internship-onboarding/components/pdf-pane";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root;
let created: string[];
let revoked: string[];

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  created = [];
  revoked = [];
  let n = 0;
  vi.spyOn(URL, "createObjectURL").mockImplementation(() => {
    const url = `blob:pdf/${++n}`;
    created.push(url);
    return url;
  });
  vi.spyOn(URL, "revokeObjectURL").mockImplementation((url) => void revoked.push(url));
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

const pdf = (text = "%PDF-1.4") => new Blob([text], { type: "application/pdf" });
const render = (props: Partial<Parameters<typeof PdfPane>[0]> = {}) => act(async () => root.render(<PdfPane title="Preview" blob={pdf()} pages={1} filename="a.pdf" {...props} />));
const button = (label: RegExp) => [...container.querySelectorAll("button")].find((b) => label.test(b.getAttribute("aria-label") ?? b.textContent ?? ""))!;

describe("PdfPane", () => {
  it("shows the PDF from a temporary URL with its page count and a sample note", async () => {
    await render({ pages: 3, note: "SAMPLE - NOT A VALID RECEIPT" });
    expect(container.querySelector("iframe")?.getAttribute("src")).toMatch(/^blob:pdf\/1#/);
    expect(container.querySelector('[data-testid="page-count"]')?.textContent).toBe("3 pages");
    expect(container.textContent).toContain("SAMPLE - NOT A VALID RECEIPT");
    await render({ pages: 1 });
    expect(container.querySelector('[data-testid="page-count"]')?.textContent).toBe("1 page");
  });

  it("zooms in and out within limits", async () => {
    await render();
    const frame = () => container.querySelector("iframe") as HTMLIFrameElement;
    expect(container.textContent).toContain("100%");
    await act(async () => button(/Zoom in/).click());
    expect(container.textContent).toContain("125%");
    expect(frame().style.width).toBe("125%");
    for (let i = 0; i < 5; i++) await act(async () => button(/Zoom out/).click());
    expect(container.textContent).toContain("60%");
    expect(button(/Zoom out/).hasAttribute("disabled")).toBe(true);
    for (let i = 0; i < 6; i++) await act(async () => button(/Zoom in/).click());
    expect(container.textContent).toContain("200%");
    expect(button(/Zoom in/).hasAttribute("disabled")).toBe(true);
  });

  it("releases the temporary URL when the PDF changes and when it closes", async () => {
    await render({ blob: pdf("one") });
    await render({ blob: pdf("two") });
    expect(created).toEqual(["blob:pdf/1", "blob:pdf/2"]);
    expect(revoked).toEqual(["blob:pdf/1"]);
    await act(async () => root.render(<div />));
    expect(revoked).toEqual(["blob:pdf/1", "blob:pdf/2"]);
  });

  it("downloads under the given name, and offers nothing to download before there is a PDF", async () => {
    await render({ blob: null, loading: true });
    expect(button(/Download/).hasAttribute("disabled")).toBe(true);
    expect(container.textContent).toContain("Drawing the preview");
    await render({ filename: "RCPT-2026-000001.pdf" });
    const clicks: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicks.push(this.download);
    });
    await act(async () => button(/Download/).click());
    expect(clicks).toEqual(["RCPT-2026-000001.pdf"]);
  });

  it("shows a problem instead of an empty frame", async () => {
    await render({ blob: null, error: "The preview could not be drawn." });
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("The preview could not be drawn.");
    expect(container.querySelector("iframe")).toBeNull();
  });
});
