// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { type Root, createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReceiptDesigner } from "@/features/internship-onboarding/components/receipt-designer";
import { brandColorProblem, contrastWithWhite } from "@/features/internship-onboarding/lib/receipt-design";
import type { DesignerView, ReceiptDesign } from "@/features/internship-onboarding/receipts-api";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({
  preview: vi.fn(),
  save: vi.fn(),
  reset: vi.fn(),
  applyTemplate: vi.fn(),
  createTemplate: vi.fn(),
  archiveTemplate: vi.fn(),
  uploadAsset: vi.fn(),
  assetImage: vi.fn(),
  payments: vi.fn(),
}));
vi.mock("@/features/internship-onboarding/receipts-api", () => ({ receiptsApi: api }));
vi.mock("@/features/internship-onboarding/api", () => ({ onboardingFlowApi: { payments: api.payments } }));

const slot = (over = {}) => ({ show: true, asset_id: null, width_mm: 40, height_mm: 18, ...over });
const design = (over: Partial<ReceiptDesign> = {}): ReceiptDesign => ({
  branding: { brand_color: "#1F3A5F", accent_color: "#E8EDF4", header_align: "left" },
  contacts: { website: "", email: "", phone: "" },
  sections: { student_email: true, student_mobile: false, application_reference: true, programme: true, payment_method: true, issuer_contacts: true, thank_you: true, footer: true },
  texts: { thank_you: "Thank you for your payment.", footer: "" },
  logo: slot(),
  signature: slot({ show: false, width_mm: 36, height_mm: 14 }),
  stamp: slot({ show: false, width_mm: 24, height_mm: 24 }),
  signatory_label: "Authorized signatory",
  ...over,
});
const view = (over: Partial<DesignerView> = {}): DesignerView => ({
  effective: { design: design(), source: "default", version: 0 },
  internship_design: null,
  organization_design: null,
  built_in: design(),
  templates: [{ id: "t1", name: "Teal", description: null, version: 1, design: design({ branding: { brand_color: "#0F766E", accent_color: "#E6F4F1", header_align: "center" } }) }],
  assets: [],
  can_edit: true,
  issuer: { legal_name: "GIR Technologies Pvt Ltd", address: "Hyderabad", gstin: "36ABCDE1234F1Z5", receipt_prefix: "RCPT", footer: "" },
  fee: { tax_mode: "exclusive", invoices_issued: true },
  ...over,
});

let container: HTMLDivElement;
let root: Root;
let created: string[];

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  Object.values(api).forEach((m) => m.mockReset());
  api.preview.mockResolvedValue({ blob: new Blob(["%PDF-1.4"], { type: "application/pdf" }), pages: 1, watermark: "SAMPLE - NOT A VALID RECEIPT" });
  api.save.mockResolvedValue({ version: 1, message: "ok" });
  api.reset.mockResolvedValue({});
  api.applyTemplate.mockResolvedValue({});
  api.createTemplate.mockResolvedValue({ id: "t2" });
  api.payments.mockResolvedValue([
    { id: "tx1", reference_number: "ERPX-INT-2026-000001", kind: "payment", status: "confirmed", amount: "5000.00", currency: "INR" },
    { id: "tx2", reference_number: "ERPX-INT-2026-000002", kind: "payment", status: "awaiting_verification", amount: "5000.00", currency: "INR" },
  ]);
  created = [];
  let n = 0;
  vi.spyOn(URL, "createObjectURL").mockImplementation(() => (created.push(`blob:x/${++n}`), `blob:x/${n}`));
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  document.body.innerHTML = "";
  vi.useRealTimers();
  vi.restoreAllMocks();
});

async function show(v: DesignerView) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await act(async () =>
    root.render(
      <QueryClientProvider client={client}>
        <ReceiptDesigner internshipId="i1" view={v} />
      </QueryClientProvider>,
    ),
  );
  await settle();
}
const settle = async (ms = 800) => {
  await act(async () => void vi.advanceTimersByTime(ms));
  await act(async () => void (await Promise.resolve()));
};
function type(selector: string, value: string) {
  const el = container.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!;
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  act(() => {
    Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
const button = (label: RegExp) => [...container.querySelectorAll("button")].find((b) => label.test(b.textContent ?? ""))!;
const lastBody = () => api.preview.mock.calls.at(-1)![1];

describe("colours", () => {
  it("measures contrast like the server and refuses a brand colour that is too light", () => {
    expect(contrastWithWhite("#000000")).toBeGreaterThan(20);
    expect(contrastWithWhite("#FFFFFF")).toBeCloseTo(1, 1);
    expect(brandColorProblem("#1F3A5F")).toBeNull();
    expect(brandColorProblem("#FFFF99")).toMatch(/too light/);
    expect(brandColorProblem("navy")).toMatch(/Use a colour/);
  });
});

describe("the Receipt Designer", () => {
  it("draws a sample preview on open, with its page count and the sample marking, and says which design is in force", async () => {
    await show(view());
    expect(api.preview).toHaveBeenCalledTimes(1);
    expect(api.preview.mock.calls[0][0]).toBe("i1");
    expect(lastBody()).toMatchObject({ kind: "tax_invoice", source: "sample", transaction_id: undefined });
    expect(container.querySelector('[data-testid="page-count"]')?.textContent).toBe("1 page");
    expect(container.textContent).toContain("SAMPLE - NOT A VALID RECEIPT");
    expect(container.querySelector("iframe")?.getAttribute("src")).toMatch(/^blob:x\/1/);
    expect(container.textContent).toContain("the built-in design");
    expect(container.textContent).toContain("issued documents never change");
  });

  it("redraws shortly after a change, with the draft design, and ignores an older answer that arrives late", async () => {
    let finishOld: (v: unknown) => void = () => undefined;
    api.preview.mockReset();
    api.preview.mockReturnValueOnce(new Promise((r) => (finishOld = r)));
    api.preview.mockResolvedValue({ blob: new Blob(["new"]), pages: 2, watermark: "SAMPLE - NOT A VALID RECEIPT" });
    await show(view());
    type("#thank-you", "Thanks from GIR");
    await settle();
    expect(lastBody().design.texts.thank_you).toBe("Thanks from GIR");
    await act(async () => finishOld({ blob: new Blob(["old"]), pages: 9, watermark: "OLD" }));
    expect(container.querySelector('[data-testid="page-count"]')?.textContent).toBe("2 pages");
    expect(container.textContent).not.toContain("OLD");
  });

  it("shows the issuer's legal identity read-only and says the mandatory parts cannot be hidden", async () => {
    await show(view());
    expect(container.textContent).toContain("GIR Technologies Pvt Ltd");
    expect(container.textContent).toContain("36ABCDE1234F1Z5");
    expect(container.querySelector("input[value='GIR Technologies Pvt Ltd']")).toBeNull(); // not an input: it is edited in the finance settings
    expect(container.textContent).toContain("Document title, number and issue date");
    expect(container.textContent).toContain("Description, amount, tax lines and total");
    const labels = [...container.querySelectorAll("label")].map((l) => l.textContent);
    expect(labels).toEqual(expect.arrayContaining(["Student's email address", "Student's mobile number", "Footer text"]));
    expect(labels.join("|")).not.toMatch(/Total|Amount|GSTIN|Document number/); // no switch for a mandatory part
  });

  it("saves for this internship, or for the organization's default, with the version it was based on", async () => {
    await show(view({ internship_design: { design: design(), version: 3 } }));
    type("#thank-you", "Hello");
    await settle();
    await act(async () => button(/Save design/).click());
    expect(api.save).toHaveBeenCalledWith("i1", "internship", expect.objectContaining({ texts: expect.objectContaining({ thank_you: "Hello" }) }), 3);
    expect(container.textContent).toContain("documents already issued are unchanged");
    const select = container.querySelector<HTMLSelectElement>("#design-scope")!;
    await act(async () => {
      select.value = "organization";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    type("#footer-text", "Registered office");
    await settle();
    await act(async () => button(/Save design/).click());
    expect(api.save.mock.calls[1].slice(0, 2)).toEqual(["i1", "organization"]);
    expect(api.save.mock.calls[1][3]).toBeUndefined(); // no organization design yet
  });

  it("will not save a brand colour that cannot be read on white", async () => {
    await show(view());
    type("#brand-color", "#FFFF99");
    await settle();
    expect(container.querySelector('[role="alert"]')?.textContent).toMatch(/too light/);
    expect(button(/Save design/).hasAttribute("disabled")).toBe(true);
  });

  it("resets to the default only after confirmation", async () => {
    await show(view({ internship_design: { design: design(), version: 1 } }));
    const confirm = vi.fn(() => false);
    window.confirm = confirm;
    await act(async () => button(/Reset to default/).click());
    expect(confirm).toHaveBeenCalled();
    expect(api.reset).not.toHaveBeenCalled();
    window.confirm = vi.fn(() => true);
    await act(async () => button(/Reset to default/).click());
    expect(api.reset).toHaveBeenCalledWith("i1", "internship");
  });

  it("applies and saves templates", async () => {
    await show(view());
    const select = container.querySelector<HTMLSelectElement>("select[aria-label='Choose a template']")!;
    await act(async () => {
      select.value = "t1";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await act(async () => button(/^Apply$/).click());
    expect(api.applyTemplate).toHaveBeenCalledWith("i1", "t1", "internship");
    type("input[aria-label='New template name']", "Mine");
    await act(async () => button(/Save as template/).click());
    expect(api.createTemplate).toHaveBeenCalledWith("i1", "Mine", expect.objectContaining({ signatory_label: "Authorized signatory" }));
  });

  it("previews with a real confirmed payment, and only confirmed ones are offered", async () => {
    await show(view());
    const source = container.querySelector<HTMLSelectElement>("#preview-source")!;
    await act(async () => {
      source.value = "transaction";
      source.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await settle();
    const options = [...container.querySelectorAll("#preview-payment option")].map((o) => o.textContent);
    expect(options.join("|")).toContain("ERPX-INT-2026-000001");
    expect(options.join("|")).not.toContain("ERPX-INT-2026-000002"); // awaiting verification: no document to preview
    const calls = api.preview.mock.calls.length;
    const payment = container.querySelector<HTMLSelectElement>("#preview-payment")!;
    await act(async () => {
      payment.value = "tx1";
      payment.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await settle();
    expect(api.preview.mock.calls.length).toBeGreaterThan(calls);
    expect(lastBody()).toMatchObject({ source: "transaction", transaction_id: "tx1" });
  });

  it("is read-only without the finance management permission", async () => {
    await show(view({ can_edit: false }));
    expect(button(/Save design/)).toBeUndefined();
    expect(container.textContent).toContain("needs the finance management permission");
    expect(container.querySelector<HTMLInputElement>("#brand-color")!.disabled).toBe(true);
    expect(container.querySelector<HTMLTextAreaElement>("#thank-you")!.disabled).toBe(true);
    expect(api.preview).toHaveBeenCalled(); // looking at the preview is still allowed
  });

  it("shows why a preview failed instead of an empty pane", async () => {
    api.preview.mockReset();
    api.preview.mockRejectedValue({ response: { data: { error: { message: "The logo image is not available. Upload it again." } } } });
    await show(view());
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("The logo image is not available. Upload it again.");
  });
});
