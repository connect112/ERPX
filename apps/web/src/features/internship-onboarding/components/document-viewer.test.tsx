// @vitest-environment happy-dom
import { act } from "react";
import { type Root, createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentViewer, type ViewerDocument } from "@/features/internship-onboarding/components/document-viewer";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({ documentFile: vi.fn() }));
vi.mock("@/features/internship-onboarding/api", () => ({ onboardingFlowApi: api }));

const pdf: ViewerDocument = { id: "d1", key: "college_id", version: 2, filename: "id.pdf", content_type: "application/pdf", viewable: true };
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
    const url = `blob:test/${++n}`;
    created.push(url);
    return url;
  });
  vi.spyOn(URL, "revokeObjectURL").mockImplementation((url) => void revoked.push(url));
  api.documentFile.mockReset();
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

const flush = () => act(async () => void (await Promise.resolve()));
async function open(doc: ViewerDocument, onClose = vi.fn(), onDownload = vi.fn()) {
  await act(async () =>
    root.render(
      <DocumentViewer internshipId="i1" document={doc} onClose={onClose} onDownload={onDownload}>
        <span>review controls</span>
      </DocumentViewer>,
    ),
  );
  await flush();
  return { onClose, onDownload };
}

describe("DocumentViewer", () => {
  it("shows a PDF in the page from a temporary object URL, fetched with the reviewer's own request", async () => {
    api.documentFile.mockResolvedValue(new Blob(["%PDF-1.4"], { type: "application/pdf" }));
    await open(pdf);
    expect(api.documentFile).toHaveBeenCalledExactlyOnceWith("i1", "d1");
    const frame = document.querySelector("iframe")!;
    expect(frame.getAttribute("src")).toMatch(/^blob:test\/1#toolbar=1/);
    expect(document.body.textContent).toContain("review controls"); // the reviewer can approve or reject while looking
  });

  it("shows a JPG or PNG as an image", async () => {
    api.documentFile.mockResolvedValue(new Blob([new Uint8Array([0x89, 0x50])], { type: "image/png" }));
    await open({ ...pdf, content_type: "image/png", filename: "id.png" });
    expect(document.querySelector("iframe")).toBeNull();
    expect(document.querySelector("img")?.getAttribute("src")).toBe("blob:test/1");
  });

  it("revokes the temporary URL when the viewer closes", async () => {
    api.documentFile.mockResolvedValue(new Blob(["%PDF-1.4"]));
    await open(pdf);
    expect(created).toEqual(["blob:test/1"]);
    expect(revoked).toEqual([]);
    await act(async () => root.render(<div />)); // the dialog is closed (unmounted)
    expect(revoked).toEqual(["blob:test/1"]);
  });

  it("revokes the old URL when another document replaces it, and never leaves one from a request that finished late", async () => {
    let finish: (b: Blob) => void = () => undefined;
    api.documentFile.mockReturnValueOnce(new Promise<Blob>((r) => (finish = r)));
    await open(pdf);
    await act(async () => root.render(<div />)); // closed before the file arrived
    await act(async () => finish(new Blob(["%PDF-1.4"])));
    expect(created).toEqual([]); // nothing was made, so nothing leaks
  });

  it("offers a download for a type it cannot show, without fetching anything", async () => {
    const { onDownload } = await open({ ...pdf, content_type: "application/zip", viewable: false });
    expect(api.documentFile).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain("cannot be shown here");
    await act(async () => [...document.querySelectorAll("button")].find((b) => /Download/.test(b.textContent ?? ""))!.click());
    expect(onDownload).toHaveBeenCalledExactlyOnceWith("d1");
  });

  it("says why when the document cannot be opened, and keeps Download available", async () => {
    api.documentFile.mockRejectedValue({ response: { data: { error: { message: "This file was removed after its retention period." } } } });
    const { onDownload } = await open(pdf);
    expect(document.querySelector('[role="alert"]')?.textContent).toBe("This file was removed after its retention period.");
    expect(created).toEqual([]);
    await act(async () => [...document.querySelectorAll("button")].find((b) => /Download/.test(b.textContent ?? ""))!.click());
    expect(onDownload).toHaveBeenCalled();
  });
});
