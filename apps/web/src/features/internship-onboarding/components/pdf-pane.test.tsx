// @vitest-environment happy-dom
import { act } from "react";
import { type Root, createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PdfPane } from "@/features/internship-onboarding/components/pdf-pane";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const render = vi.hoisted(() => ({ renderPdf: vi.fn(), destroy: vi.fn() }));
vi.mock("@/features/internship-onboarding/lib/pdf-render", () => ({ renderPdf: render.renderPdf }));

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  render.destroy.mockReset();
  // a fake pdf.js: draws `pages` canvases into the host, like the real renderer, and reports how many
  render.renderPdf.mockReset().mockImplementation(async (blob: Blob, host: HTMLElement, opts: { zoom: number }) => {
    const pages = blob.size > 20 ? 3 : 1;
    host.replaceChildren(...Array.from({ length: pages }, (_, i) => Object.assign(document.createElement("canvas"), { title: `page ${i + 1} at ${opts.zoom}%` })));
    return { pages, destroy: render.destroy };
  });
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

const pdf = (text = "%PDF-1.4") => new Blob([text], { type: "application/pdf" });
const show = (props: Partial<Parameters<typeof PdfPane>[0]> = {}) => act(async () => root.render(<PdfPane title="Preview" blob={pdf()} pages={1} filename="a.pdf" {...props} />));
const button = (label: RegExp) => [...container.querySelectorAll("button")].find((b) => label.test(b.getAttribute("aria-label") ?? b.textContent ?? ""))!;
const canvases = () => [...container.querySelectorAll("canvas")].map((c) => c.title);

describe("PdfPane", () => {
  it("draws the pages on canvases (never an iframe), with the real page count and a sample note", async () => {
    await show({ blob: pdf("%PDF-1.4 a longer document"), pages: 1, note: "SAMPLE - NOT A VALID RECEIPT" });
    expect(container.querySelector("iframe, embed, object")).toBeNull();
    expect(canvases()).toEqual(["page 1 at 100%", "page 2 at 100%", "page 3 at 100%"]);
    expect(container.querySelector('[data-testid="page-count"]')?.textContent).toBe("3 pages"); // what was drawn, not the header's guess
    expect(container.textContent).toContain("SAMPLE - NOT A VALID RECEIPT");
  });

  it("zooms by drawing again at the new size, within limits", async () => {
    await show();
    await act(async () => button(/Zoom in/).click());
    expect(container.textContent).toContain("125%");
    expect(render.renderPdf).toHaveBeenLastCalledWith(expect.any(Blob), expect.any(HTMLElement), expect.objectContaining({ zoom: 125 }));
    for (let i = 0; i < 5; i++) await act(async () => button(/Zoom out/).click());
    expect(container.textContent).toContain("60%");
    expect(button(/Zoom out/).hasAttribute("disabled")).toBe(true);
    for (let i = 0; i < 6; i++) await act(async () => button(/Zoom in/).click());
    expect(container.textContent).toContain("200%");
    expect(button(/Zoom in/).hasAttribute("disabled")).toBe(true);
  });

  it("releases the previous document when the PDF changes and when the pane closes", async () => {
    await show({ blob: pdf("one") });
    await show({ blob: pdf("two") });
    expect(render.destroy).toHaveBeenCalledTimes(1);
    await act(async () => root.render(<div />));
    expect(render.destroy).toHaveBeenCalledTimes(2);
  });

  it("does not take focus or scroll the page while a preview is drawn or replaced", async () => {
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    const into = vi.fn();
    Element.prototype.scrollIntoView = into;
    const focus = vi.spyOn(HTMLElement.prototype, "focus");
    const before = document.activeElement;
    await show({ blob: pdf("one") });
    await show({ blob: pdf("a much longer second preview") });
    await act(async () => button(/Zoom in/).click());
    expect(scrollTo).not.toHaveBeenCalled();
    expect(into).not.toHaveBeenCalled();
    expect(focus).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(before);
  });

  it("keeps the pane's size when there is no preview yet, while it is drawn and when it fails (the page around it never moves)", async () => {
    const frame = () => container.querySelector('[data-testid="pdf-pages"]')!.parentElement!.className;
    await show({ blob: null, loading: true });
    const empty = frame();
    expect(empty).toContain("h-[72vh]");
    expect(container.textContent).toContain("Drawing the preview");
    await show({ blob: null, error: "The preview could not be drawn." });
    expect(frame()).toBe(empty);
    await show();
    expect(frame()).toBe(empty);
    expect(container.querySelector('[data-testid="pdf-pages"]')?.className).toContain("overflow-auto");
  });

  it("downloads from a temporary link that is released straight away, and offers nothing before there is a PDF", async () => {
    await show({ blob: null });
    expect(button(/Download/).hasAttribute("disabled")).toBe(true);
    const made = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:dl/1");
    const gone = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const names: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download);
    });
    await show({ filename: "RCPT-2026-000001.pdf" });
    await act(async () => button(/Download/).click());
    expect(names).toEqual(["RCPT-2026-000001.pdf"]);
    expect(made).toHaveBeenCalledTimes(1);
    expect(gone).toHaveBeenCalledWith("blob:dl/1");
  });

  it("says so when a document cannot be drawn, and when a drawing is replaced meanwhile it stays quiet", async () => {
    render.renderPdf.mockRejectedValueOnce(new Error("broken pdf"));
    await show();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("could not be shown here");
    render.renderPdf.mockRejectedValue(Object.assign(new Error("replaced"), { name: "AbortError" }));
    await show({ blob: pdf("another") });
    expect(container.querySelector('[role="alert"]')?.textContent ?? "").toContain("could not be shown here"); // (the earlier message is not repeated or doubled)
    expect(container.querySelectorAll('[role="alert"]').length).toBeLessThanOrEqual(1);
  });
});
