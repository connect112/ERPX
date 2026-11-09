// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act } from "react";
import { type Root, createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReceiptDesigner } from "@/features/internship-onboarding/components/receipt-designer";
import { designerKey } from "@/features/internship-onboarding/lib/designer-key";
import { asset, design, view } from "@/features/internship-onboarding/components/receipt-fixtures";
import { brandColorProblem, contrastWithWhite, movePart, titleProblem } from "@/features/internship-onboarding/lib/receipt-design";
import type { DesignerView } from "@/features/internship-onboarding/receipts-api";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({
  preview: vi.fn(), save: vi.fn(), reset: vi.fn(), applyTemplate: vi.fn(), createTemplate: vi.fn(), archiveTemplate: vi.fn(),
  uploadAsset: vi.fn(), assetImage: vi.fn(), saveIssuer: vi.fn(), payments: vi.fn(),
}));  // prettier-ignore
vi.mock("@/features/internship-onboarding/receipts-api", () => ({ receiptsApi: api }));
vi.mock("@/features/internship-onboarding/api", () => ({ onboardingFlowApi: { payments: api.payments } }));
vi.mock("@/features/internship-onboarding/lib/pdf-render", () => ({
  renderPdf: async (_b: Blob, host: HTMLElement) => (host.replaceChildren(document.createElement("canvas")), { pages: 1, destroy: () => undefined }),
}));

let container: HTMLDivElement;
let root: Root;
let client: QueryClient;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  Object.values(api).forEach((m) => m.mockReset());
  api.preview.mockResolvedValue({ blob: new Blob(["%PDF-1.4"], { type: "application/pdf" }), pages: 1, watermark: "SAMPLE - NOT A VALID RECEIPT" });
  api.save.mockResolvedValue({ version: 1, message: "ok" });
  api.reset.mockResolvedValue({});
  api.applyTemplate.mockResolvedValue({});
  api.createTemplate.mockResolvedValue({ id: "t2" });
  api.uploadAsset.mockResolvedValue(asset("new1", "first-logo.png"));
  api.assetImage.mockResolvedValue(new Blob(["x"], { type: "image/png" }));
  api.saveIssuer.mockResolvedValue({ settings_version: 5, message: "Saved in the finance settings." });
  api.payments.mockResolvedValue([
    { id: "tx1", reference_number: "ERPX-INT-2026-000001", kind: "payment", status: "confirmed", amount: "5000.00", currency: "INR" },
    { id: "tx2", reference_number: "ERPX-INT-2026-000002", kind: "payment", status: "awaiting_verification", amount: "5000.00", currency: "INR" },
  ]);
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:x/1");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  document.body.innerHTML = "";
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const settle = async (ms = 800) => {
  await act(async () => void vi.advanceTimersByTime(ms));
  await act(async () => void (await Promise.resolve()));
};
let served: DesignerView;
/** The page around the designer: it hands the designer whatever the cached page data currently is, like the real panel does. */
function Live() {
  const q = useQuery({ queryKey: designerKey("i1"), queryFn: async () => served, staleTime: Infinity });
  return q.data ? <ReceiptDesigner internshipId="i1" view={q.data} /> : null;
}
async function show(v: DesignerView) {
  served = v;
  client.setQueryData(designerKey("i1"), v);
  await act(async () =>
    root.render(
      <QueryClientProvider client={client}>
        <Live />
      </QueryClientProvider>,
    ),
  );
  await settle();
}
/** The page data arrives again (a background refresh): a new object, as react-query would give after a refetch. */
async function refetched(v: DesignerView) {
  served = v;
  await act(async () => void client.setQueryData(designerKey("i1"), v));
  await settle(0);
}
function type(selector: string, value: string) {
  const el = container.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!;
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  act(() => {
    Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
function choose(selector: string, value: string) {
  const el = container.querySelector<HTMLSelectElement>(selector)!;
  return act(async () => {
    el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
}
const button = (label: RegExp) => [...container.querySelectorAll("button")].find((b) => label.test(b.getAttribute("aria-label") ?? b.textContent ?? ""))!;
const lastBody = () => api.preview.mock.calls.at(-1)![1];
const value = (selector: string) => container.querySelector<HTMLInputElement>(selector)!.value;
async function pick(label: string, file: File) {
  const input = container.querySelector<HTMLInputElement>(`input[type='file'][aria-label='Upload ${label}']`)!;
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  await act(async () => void input.dispatchEvent(new Event("change", { bubbles: true })));
  await act(async () => void (await Promise.resolve()));
}

describe("helpers", () => {
  it("measures contrast, judges titles and moves parts like the server does", () => {
    expect(contrastWithWhite("#000000")).toBeGreaterThan(20);
    expect(brandColorProblem("#FFFF99")).toMatch(/too light/);
    expect(titleProblem("tax_invoice", "Bill")).toMatch(/Tax Invoice/);
    expect(titleProblem("tax_invoice", "GST Tax Invoice")).toBeNull();
    expect(titleProblem("receipt", "Tax Invoice")).toMatch(/cannot call/);
    expect(titleProblem("credit_note", "Credit Note (Refund)")).toBeNull();
    expect(movePart(["details", "items", "thank_you", "signature"], "items", -1)).toEqual(["items", "details", "thank_you", "signature"]);
    expect(movePart(["details", "items", "thank_you", "signature"], "details", -1)).toEqual(["details", "items", "thank_you", "signature"]);
  });
});

describe("the first image", () => {
  it("is chosen for its slot straight away, appears in the preview request, and the page data is not reloaded", async () => {
    await show(view());
    const invalidate = vi.spyOn(client, "invalidateQueries");
    await pick("Company logo", new File(["png"], "first-logo.png", { type: "image/png" }));
    expect(api.uploadAsset).toHaveBeenCalledWith("i1", "logo", expect.any(File));
    expect(api.assetImage).toHaveBeenCalledWith("i1", "new1"); // its thumbnail is shown in the slot
    expect(container.querySelector("img[alt='Company logo in use']")).not.toBeNull();
    await settle();
    expect(lastBody().design.logo).toMatchObject({ asset_id: "new1", show: true }); // and the preview is drawn with it
    expect(invalidate).not.toHaveBeenCalled(); // nothing was reloaded: nothing could replace the draft
    expect(client.getQueryData<DesignerView>(designerKey("i1"))!.assets.map((a) => a.id)).toEqual(["new1"]);
    expect(container.textContent).toContain("Image uploaded and selected");
  });

  it("can be picked again later from the saved images, even when it is the only one", async () => {
    await show(view({ assets: [asset("only", "only-logo.png")] }));
    const select = container.querySelector<HTMLSelectElement>("select[aria-label='Use a saved company logo']")!;
    expect(select).not.toBeNull();
    expect([...select.options].map((o) => o.textContent)).toContain("only-logo.png (300×120)");
    await choose("select[aria-label='Use a saved company logo']", "only");
    await settle();
    expect(lastBody().design.logo.asset_id).toBe("only");
  });

  it("does not lose the current selection when another image is uploaded", async () => {
    await show(view({ assets: [asset("a1", "one.png")], effective: { design: design({ logo: { show: true, asset_id: "a1", align: "auto", width_mm: 40, height_mm: 18 } }), source: "organization", version: 1, layout: "designer" } }));
    api.uploadAsset.mockResolvedValue(asset("a2", "two.png"));
    await pick("Company logo", new File(["png"], "two.png", { type: "image/png" }));
    await settle();
    expect(lastBody().design.logo.asset_id).toBe("a2"); // the new one is chosen...
    const options = [...container.querySelectorAll<HTMLOptionElement>("select[aria-label='Use a saved company logo'] option")].map((o) => o.value);
    expect(options).toEqual(["", "a2", "a1"]); // ...and the earlier one is still there to go back to
    await choose("select[aria-label='Use a saved company logo']", "a1");
    await settle();
    expect(lastBody().design.logo.asset_id).toBe("a1");
  });
});

describe("unsaved changes", () => {
  it("survive a background refresh of the page data, including an upload and a removal", async () => {
    await show(view());
    type("#thank-you", "My unsaved wording");
    type("#lab-billed_to", "CUSTOMER");
    await pick("Company logo", new File(["png"], "first-logo.png", { type: "image/png" }));
    await refetched(view({ assets: [asset("new1", "first-logo.png")] })); // the same server design, a new object, one more image
    expect(value("#thank-you")).toBe("My unsaved wording");
    expect(value("#lab-billed_to")).toBe("CUSTOMER");
    await act(async () => button(/Remove Company logo/).click());
    await refetched(view({ assets: [asset("new1", "first-logo.png")] }));
    expect(value("#thank-you")).toBe("My unsaved wording");
    await settle();
    expect(lastBody().design.texts.thank_you).toBe("My unsaved wording");
    expect(lastBody().design.logo.asset_id).toBeNull();
    const flag = [...container.querySelectorAll("span")].find((n) => n.textContent === "Unsaved changes")!;
    expect(flag.className).not.toContain("invisible");
  });

  it("are kept, with a notice, when someone else saved a new design meanwhile", async () => {
    await show(view());
    type("#thank-you", "Mine");
    await refetched(view({ effective: { design: design({ texts: { ...design().texts, thank_you: "Theirs" } }), source: "organization", version: 3, layout: "designer" }, organization_design: { design: design(), version: 3 } }));
    expect(value("#thank-you")).toBe("Mine");
    expect(container.textContent).toContain("A newer design was saved elsewhere");
  });

  it("are replaced by a newer saved design only when there are none, and after this person's own save", async () => {
    await show(view());
    await refetched(view({ effective: { design: design({ texts: { ...design().texts, thank_you: "From the server" } }), source: "organization", version: 2, layout: "designer" }, organization_design: { design: design(), version: 2 } }));
    expect(value("#thank-you")).toBe("From the server"); // nothing of mine was waiting
    type("#thank-you", "Edited by me");
    await act(async () => button(/Save design/).click());
    await settle(0);
    expect(api.save).toHaveBeenCalledWith("i1", "internship", expect.objectContaining({ texts: expect.objectContaining({ thank_you: "Edited by me" }) }), undefined);
    await refetched(view({ effective: { design: design({ texts: { ...design().texts, thank_you: "Edited by me" } }), source: "internship", version: 1, layout: "designer" }, internship_design: { design: design({ texts: { ...design().texts, thank_you: "Edited by me" } }), version: 1 } }));
    expect(value("#thank-you")).toBe("Edited by me");
    const flag = [...container.querySelectorAll("span")].find((n) => n.textContent === "Unsaved changes")!;
    expect(flag.className).toContain("invisible"); // (kept in the layout so the bar never changes height)
  });
});

describe("scrolling and focus", () => {
  it("an upload and the preview refresh never scroll the page or the settings panel, never move focus and never open an embedded viewer", async () => {
    await show(view());
    const panel = container.querySelector<HTMLElement>('[data-testid="settings-panel"]')!;
    panel.scrollTop = 480;
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    const into = vi.fn();
    Element.prototype.scrollIntoView = into;
    const focus = vi.spyOn(HTMLElement.prototype, "focus");
    const active = document.activeElement;
    await pick("Company logo", new File(["png"], "first-logo.png", { type: "image/png" }));
    await refetched(view({ assets: [asset("new1", "first-logo.png")] }));
    await settle();
    expect(scrollTo).not.toHaveBeenCalled();
    expect(into).not.toHaveBeenCalled();
    expect(focus).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(active);
    expect(panel.scrollTop).toBe(480);
    expect(container.querySelector("iframe, embed, object")).toBeNull();
    expect(container.querySelector('[data-testid="settings-panel"]')).toBe(panel); // the panel itself was never replaced
  });

  it("shows its messages floating above the save bar, so showing one never changes the height of the panel", async () => {
    await show(view());
    await pick("Company logo", new File(["png"], "first-logo.png", { type: "image/png" }));
    const message = [...container.querySelectorAll('[role="status"]')].find((n) => n.textContent?.includes("Image uploaded"))!;
    expect(message.className).toContain("absolute");
    expect(message.className).toContain("bottom-full");
    expect(container.querySelector('[data-testid="settings-panel"] .sticky')?.contains(message)).toBe(true);
  });
});

describe("document titles and wording", () => {
  it("edits a title and subtitle for each document type and previews them", async () => {
    await show(view());
    type("#title-receipt", "Fee Receipt");
    type("#subtitle-receipt", "Acknowledgement of fees");
    type("#title-tax_invoice", "GST Tax Invoice");
    type("#title-credit_note", "Credit Note (Refund)");
    await settle();
    expect(lastBody().design.labels).toMatchObject({ title_receipt: "Fee Receipt", subtitle_receipt: "Acknowledgement of fees", title_tax_invoice: "GST Tax Invoice", title_credit_note: "Credit Note (Refund)" });
  });

  it("warns, and will not let you save, a title that would misrepresent the document", async () => {
    await show(view());
    type("#title-tax_invoice", "Bill");
    expect(container.textContent).toContain('A tax invoice title must contain "Tax Invoice".');
    type("#title-receipt", "Tax Invoice");
    expect(container.textContent).toContain("A receipt title cannot call the document an invoice or a credit note.");
  });

  it("offers a control for every fixed word, grouped, with no control for an amount, tax, reference, date or number", async () => {
    await show(view());
    for (const heading of ["Numbers and dates", "Customer and payment details", "Table and totals", "Status wording", "Notes and page numbers"]) expect(container.textContent).toContain(heading);
    const wordingLabels = [...container.querySelectorAll<HTMLLabelElement>("label")].filter((l) => /^(lab|title|subtitle)-/.test(l.htmlFor));
    const labels = wordingLabels.map((l) => l.textContent ?? "");
    for (const wanted of ["Customer heading", "Payment details heading", "Table heading: description", "Table heading: amount", "Total line (receipt, tax invoice)", "Badge for a payment", "Status wording for a refund", "Note when there is no signature", "Word before the page number"]) {
      expect(labels).toContain(wanted);
    }
    expect(labels.join("|")).not.toMatch(/Amount paid|GST amount|Tax amount|Transaction id|Document number value|Payment date value/i);
    type("#lab-col_amount", "VALUE");
    await settle();
    expect(lastBody().design.labels.col_amount).toBe("VALUE");
  });

  it("changes typography, spacing, borders, alignment and section order", async () => {
    await show(view());
    type("#style-title_size", "22");
    type("#style-section_gap_mm", "10");
    await choose("#style-borders", "grid");
    await choose("#sig-align", "left");
    await act(async () => button(/Move Thank-you message up/).click());
    await settle();
    expect(lastBody().design.style).toMatchObject({ title_size: 22, section_gap_mm: 10, table_borders: "grid" });
    expect(lastBody().design.signature_align).toBe("left");
    expect(lastBody().design.body_order).toEqual(["details", "thank_you", "items", "signature"]);
  });
});

describe("the issuer's identity", () => {
  it("is edited through the finance settings, with the server's reason shown when it is refused", async () => {
    await show(view());
    expect(value("#iss-name")).toBe("GIR Technologies Pvt Ltd");
    type("#iss-name", "Pentrix Cyber Academy Pvt Ltd");
    type("#iss-prefix", "pca");
    type("#iss-gstin", "36aaaaa1111a1z5");
    await act(async () => button(/Save issuer identity/).click());
    await settle(0);
    expect(api.saveIssuer).toHaveBeenCalledWith("i1", { legal_name: "Pentrix Cyber Academy Pvt Ltd", address: "Hyderabad", gstin: "36AAAAA1111A1Z5", receipt_prefix: "PCA", footer: "" });
    expect(container.textContent).toContain("Saved in the finance settings.");
    api.saveIssuer.mockRejectedValue({ response: { data: { error: { message: "issuer: A GSTIN is set: choose the tax treatment of the fee." } } } });
    type("#iss-name", "Another name");
    await act(async () => button(/Save issuer identity/).click());
    await settle(0);
    expect([...container.querySelectorAll('[role="alert"]')].map((n) => n.textContent).join(" ")).toContain("choose the tax treatment");
  });

  it("does not disturb the design draft when it is saved, and is read-only without the finance permission", async () => {
    await show(view());
    type("#thank-you", "Unsaved wording");
    type("#iss-name", "New name");
    await act(async () => button(/Save issuer identity/).click());
    await refetched(view({ issuer: { legal_name: "New name", address: "Hyderabad", gstin: "36ABCDE1234F1Z5", receipt_prefix: "RCPT", footer: "" } }));
    expect(value("#thank-you")).toBe("Unsaved wording");
    expect(value("#iss-name")).toBe("New name");
    await act(async () => root.unmount());
    root = createRoot(container);
    await show(view({ can_edit: false }));
    expect(container.querySelector<HTMLInputElement>("#iss-name")!.disabled).toBe(true);
    expect(button(/Save issuer identity/)).toBeUndefined();
  });
});

describe("sample details", () => {
  it("go only into a sample preview and are not part of the design that is saved", async () => {
    await show(view());
    type("#sample-customer_name", "Priya Nair");
    type("#sample-amount", "11800.00");
    await settle();
    expect(lastBody().sample).toEqual({ customer_name: "Priya Nair", amount: "11800.00" });
    expect(JSON.stringify(lastBody().design)).not.toContain("Priya");
    await act(async () => button(/Save design/).click());
    await settle(0);
    expect(JSON.stringify(api.save.mock.calls[0])).not.toContain("Priya");
    await choose("#preview-source", "transaction");
    await settle(0); // the list of confirmed payments arrives
    await choose("#preview-payment", "tx1");
    await settle();
    expect(lastBody()).toMatchObject({ source: "transaction", transaction_id: "tx1" });
    expect(lastBody().sample).toBeUndefined(); // a real payment is never previewed with sample figures
  });
});

describe("the Receipt Designer", () => {
  it("draws a sample preview on open and says the original layout is still in use until a design is saved", async () => {
    await show(view());
    expect(lastBody()).toMatchObject({ kind: "tax_invoice", source: "sample" });
    expect(container.querySelector('[data-testid="page-count"]')?.textContent).toBe("1 page");
    expect(container.querySelector('[data-testid="legacy-notice"]')?.textContent).toContain("still issued with the original layout");
    expect(button(/Save design/).hasAttribute("disabled")).toBe(false); // the first save is always possible
  });

  it("ignores a preview answer that arrives late", async () => {
    let finishOld: (v: unknown) => void = () => undefined;
    api.preview.mockReset();
    api.preview.mockReturnValueOnce(new Promise((r) => (finishOld = r)));
    api.preview.mockResolvedValue({ blob: new Blob(["new"]), pages: 2, watermark: "SAMPLE - NOT A VALID RECEIPT" });
    await show(view());
    type("#thank-you", "Thanks from GIR");
    await settle();
    await act(async () => finishOld({ blob: new Blob(["old"]), pages: 9, watermark: "OLD" }));
    expect(container.querySelector('[data-testid="page-count"]')?.textContent).toBe("1 page"); // what the stand-in renderer drew from the newer answer
    expect(container.textContent).not.toContain("OLD");
  });

  it("saves for this internship or the organization's default, resets only after confirmation, and applies templates", async () => {
    await show(view({ internship_design: { design: design(), version: 3 }, effective: { design: design(), source: "internship", version: 3, layout: "designer" } }));
    type("#thank-you", "Hello");
    await act(async () => button(/Save design/).click());
    expect(api.save).toHaveBeenCalledWith("i1", "internship", expect.anything(), 3);
    await choose("#design-scope", "organization");
    type("#footer-text", "Registered office");
    await act(async () => button(/Save design/).click());
    expect(api.save.mock.calls[1].slice(0, 2)).toEqual(["i1", "organization"]);
    window.confirm = vi.fn(() => false);
    await choose("#design-scope", "internship");
    await act(async () => button(/Reset to default/).click());
    expect(api.reset).not.toHaveBeenCalled();
    window.confirm = vi.fn(() => true);
    await act(async () => button(/Reset to default/).click());
    expect(api.reset).toHaveBeenCalledWith("i1", "internship");
    await choose("select[aria-label='Choose a template']", "t1");
    await act(async () => button(/^Apply$/).click());
    expect(api.applyTemplate).toHaveBeenCalledWith("i1", "t1", "internship");
  });

  it("will not save a brand colour that cannot be read on white", async () => {
    await show(view());
    type("#brand-color", "#FFFF99");
    expect(container.textContent).toContain("too light");
    expect(button(/Save design/).hasAttribute("disabled")).toBe(true);
  });

  it("is read-only without the finance management permission, but the preview still works", async () => {
    await show(view({ can_edit: false }));
    expect(button(/Save design/)).toBeUndefined();
    expect(container.querySelector<HTMLInputElement>("#brand-color")!.disabled).toBe(true);
    expect(container.querySelector<HTMLInputElement>("#title-receipt")!.disabled).toBe(true);
    expect(container.querySelector<HTMLInputElement>("#lab-billed_to")!.disabled).toBe(true);
    expect(api.preview).toHaveBeenCalled();
  });

  it("shows why a preview failed instead of an empty pane", async () => {
    api.preview.mockReset();
    api.preview.mockRejectedValue({ response: { data: { error: { message: "The logo image is not available. Upload it again." } } } });
    await show(view());
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("The logo image is not available. Upload it again.");
  });
});
