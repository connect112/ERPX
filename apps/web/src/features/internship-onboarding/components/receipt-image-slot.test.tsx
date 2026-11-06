// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { type Root, createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MAX_IMAGE_BYTES, ReceiptImageSlot } from "@/features/internship-onboarding/components/receipt-image-slot";
import type { ImageSlot, ReceiptAssetInfo } from "@/features/internship-onboarding/receipts-api";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({ uploadAsset: vi.fn(), assetImage: vi.fn() }));
vi.mock("@/features/internship-onboarding/receipts-api", () => ({ receiptsApi: api }));

const slot = (over: Partial<ImageSlot> = {}): ImageSlot => ({ show: true, asset_id: null, width_mm: 40, height_mm: 18, ...over });
const asset = (id: string, name = "logo.png"): ReceiptAssetInfo => ({ id, kind: "logo", filename: name, width_px: 300, height_px: 120, size_bytes: 1000, created_at: "2026-11-01T00:00:00Z" });

let container: HTMLDivElement;
let root: Root;
let onChange: ReturnType<typeof vi.fn<(patch: Partial<ImageSlot>) => void>>;
let onUploaded: ReturnType<typeof vi.fn<() => void>>;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  api.uploadAsset.mockReset().mockResolvedValue(asset("new1"));
  api.assetImage.mockReset().mockResolvedValue(new Blob(["x"], { type: "image/png" }));
  onChange = vi.fn<(patch: Partial<ImageSlot>) => void>();
  onUploaded = vi.fn<() => void>();
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:thumb/1");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

async function show(props: Partial<Parameters<typeof ReceiptImageSlot>[0]> = {}) {
  const client = new QueryClient();
  await act(async () =>
    root.render(
      <QueryClientProvider client={client}>
        <ReceiptImageSlot internshipId="i1" kind="logo" label="Company logo" slot={slot()} assets={[]} canEdit onChange={onChange} onUploaded={onUploaded} {...props} />
      </QueryClientProvider>,
    ),
  );
  await act(async () => void (await Promise.resolve()));
}
async function pick(file: File) {
  const input = container.querySelector<HTMLInputElement>("input[type='file']")!;
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  await act(async () => void input.dispatchEvent(new Event("change", { bubbles: true })));
  await act(async () => void (await Promise.resolve()));
}

describe("ReceiptImageSlot", () => {
  it("uploads a PNG or JPG, uses it, and tells the designer an image arrived", async () => {
    await show();
    await pick(new File(["png"], "logo.png", { type: "image/png" }));
    expect(api.uploadAsset).toHaveBeenCalledWith("i1", "logo", expect.any(File));
    expect(onChange).toHaveBeenCalledWith({ asset_id: "new1", show: true });
    expect(onUploaded).toHaveBeenCalled();
  });

  it("refuses an image that is too big or not a PNG or JPG before sending anything", async () => {
    await show();
    await pick(new File([new Uint8Array(MAX_IMAGE_BYTES + 1)], "big.png", { type: "image/png" }));
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("The image is larger than 2 MB.");
    await pick(new File(["<svg/>"], "logo.svg", { type: "image/svg+xml" }));
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("Upload a PNG or JPG image.");
    expect(api.uploadAsset).not.toHaveBeenCalled();
  });

  it("shows the server's reason when an upload is refused", async () => {
    api.uploadAsset.mockRejectedValue({ response: { data: { error: { message: "That file is not a usable PNG or JPG image." } } } });
    await show();
    await pick(new File(["x"], "logo.png", { type: "image/png" }));
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("That file is not a usable PNG or JPG image.");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows the image in use, lets a saved one be chosen, and removes it from the design only", async () => {
    await show({ slot: slot({ asset_id: "a1" }), assets: [asset("a1", "one.png"), asset("a2", "two.png")] });
    expect(api.assetImage).toHaveBeenCalledWith("i1", "a1");
    expect(container.querySelector("img")?.getAttribute("src")).toBe("blob:thumb/1");
    const select = container.querySelector<HTMLSelectElement>("select")!;
    await act(async () => {
      select.value = "a2";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(onChange).toHaveBeenCalledWith({ asset_id: "a2" });
    await act(async () => (container.querySelector("button[aria-label='Remove Company logo']") as HTMLButtonElement).click());
    expect(onChange).toHaveBeenCalledWith({ asset_id: null });
  });

  it("is read-only without permission: no upload, no remove", async () => {
    await show({ canEdit: false, slot: slot({ asset_id: "a1" }) });
    expect(container.querySelector("input[type='file']")).toBeNull();
    expect(container.querySelector("button[aria-label='Remove Company logo']")).toBeNull();
    expect(container.querySelector("fieldset")?.disabled).toBe(true);
  });

  it("releases the thumbnail's temporary URL when it goes away", async () => {
    await show({ slot: slot({ asset_id: "a1" }) });
    await act(async () => root.render(<div />));
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:thumb/1");
  });
});
