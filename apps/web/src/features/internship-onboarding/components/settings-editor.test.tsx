// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { type Root, createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ConfigView, OnboardingSettings } from "@/features/internship-onboarding/api";
import { SettingsEditor } from "@/features/internship-onboarding/components/settings-editor";
import { sensitiveHelp } from "@/features/internship-onboarding/lib/sensitive";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({
  saveConfig: vi.fn(),
  templates: vi.fn(),
  list: vi.fn(),
}));
vi.mock("@/features/internship-onboarding/api", () => ({
  onboardingFlowApi: { saveConfig: api.saveConfig, templates: api.templates, applyTemplate: vi.fn(), saveAsTemplate: vi.fn() },
  paymentAccountsApi: { list: api.list },
}));

function settings(over: Partial<OnboardingSettings> = {}): OnboardingSettings {
  return {
    modes: { mode: "hybrid", allow_info_edit: false, require_documents: true, require_payment: false, payment_order: "after_submission", lms_access: "manual", allow_late_onboarding: true, reminders: true, invoice_emails: true, allow_decline: false },
    fees: { currency: "INR", base_amount: "0", description: "Fee", tax_mode: "none", tax_rate_percent: "0", tax_label: "GST", discount_amount: "0", late_fee: { mode: "none", value: "0" }, methods: [] },
    deadlines: { timezone: "Asia/Kolkata", opens_at: null, closes_at: null, acceptance_deadline: null, documents_deadline: null, payment_deadline: null, payment_grace_hours: 0 },
    documents: [
      { key: "college_id", label: "College ID card", required: true, types: ["pdf"], max_mb: 5, sensitive: false },
      { key: "id_proof", label: "Government ID", required: false, types: ["pdf"], max_mb: 5, sensitive: false },
    ],
    form: [],
    declaration: { text: "I confirm that the information is accurate.", terms_version: "1", terms_url: null },
    payment_accounts: { bank: null, upi: null, bank_account_id: null, upi_account_id: null },
    communication: { contact_email: null, contact_phone: null, whatsapp_link: null, whatsapp_visibility: "after_completion", reminder_days: [7, 3, 1], next_steps: "" },
    issuer: { legal_name: "GIR Technologies", address: "", gstin: null, receipt_prefix: "RCPT", footer: "" },
    policies: { allow_refund_requests: false, refund_policy: "", refund_policy_version: "1", refund_request_days: null, identity_document_retention_days: null },
    reference_prefix: "ERPX-INT",
    ...over,
  };
}
const view = (scanning: boolean, s = settings()): ConfigView => ({
  settings: s, version: 1, template_id: null, template_version: null, can_edit_finance: false, can_view_finance: false, can_review: true,
  fee_preview: { total: "0.00", tax: "0.00" }, cashfree_available: false, virus_scanning_available: scanning,
});

let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  api.saveConfig.mockReset().mockResolvedValue({ version: 2 });
  api.templates.mockReset().mockResolvedValue([]);
  api.list.mockReset().mockResolvedValue([]);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

async function show(v: ConfigView) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await act(async () =>
    root.render(
      <QueryClientProvider client={client}>
        <SettingsEditor internshipId="i1" view={v} />
      </QueryClientProvider>,
    ),
  );
}
const checkbox = (row: Element) => [...row.querySelectorAll("label")].map((l) => l).find((l) => /Sensitive/.test(l.textContent ?? ""))!.querySelector("input")!;
const documentRows = () => [...container.querySelectorAll("input[aria-label='Document name']")].map((i) => i.closest(".grid")!);
const save = async () => {
  await act(async () => [...container.querySelectorAll("button")].find((b) => /Save settings/.test(b.textContent ?? ""))!.click());
  await act(async () => void (await Promise.resolve()));
};

describe("the Sensitive document toggle", () => {
  it("is disabled with a clear explanation while virus scanning is not set up", async () => {
    await show(view(false));
    expect(container.textContent).toContain(sensitiveHelp.unavailable);
    const [first] = documentRows();
    expect(checkbox(first).disabled).toBe(true);
    expect(checkbox(first).getAttribute("aria-describedby")).toBe("sensitive-help-0");
    expect(first.querySelector("#sensitive-help-0")?.textContent).toBe(sensitiveHelp.disabledHere);
  });

  it("still lets an administrator switch an already-sensitive document off when scanning is unavailable", async () => {
    const s = settings();
    s.documents[1].sensitive = true;
    await show(view(false, s));
    const row = documentRows()[1];
    expect(checkbox(row).disabled).toBe(false);
    await act(async () => checkbox(row).click());
    await save();
    expect(api.saveConfig.mock.calls[0][1].documents[1].sensitive).toBe(false);
  });

  it("works when scanning is available: it toggles, asks for the retention period, and is saved", async () => {
    await show(view(true));
    expect(container.textContent).not.toContain(sensitiveHelp.unavailable);
    const row = documentRows()[1];
    expect(checkbox(row).disabled).toBe(false);
    await act(async () => checkbox(row).click());
    expect(checkbox(row).checked).toBe(true);
    expect(row.querySelector("#sensitive-help-1")?.textContent).toBe(sensitiveHelp.needsRetention);
    await save();
    expect(api.saveConfig).toHaveBeenCalledTimes(1);
    expect(api.saveConfig.mock.calls[0][1].documents.map((d: { sensitive: boolean }) => d.sensitive)).toEqual([false, true]);
  });

  it("shows the stored value after a refresh (a new view from the server)", async () => {
    const s = settings();
    s.documents[1].sensitive = true;
    s.policies.identity_document_retention_days = 365;
    await show(view(true, s));
    expect(checkbox(documentRows()[1]).checked).toBe(true);
    expect(documentRows()[1].querySelector("#sensitive-help-1")?.textContent).toBe(sensitiveHelp.on);
  });

  it("tells the administrator an Aadhaar document must be marked sensitive", async () => {
    const s = settings();
    s.documents[0] = { ...s.documents[0], key: "aadhaar", label: "Aadhaar card" };
    await show(view(true, s));
    expect(documentRows()[0].querySelector("#sensitive-help-0")?.textContent).toBe(sensitiveHelp.aadhaar);
  });
});

describe("the decline switch and the WhatsApp group link", () => {
  it("offers 'Allow students to decline the offer', off by default, and saves it", async () => {
    await show(view(false));
    const box = [...container.querySelectorAll("label")].find((l) => /Allow students to decline the offer/.test(l.textContent ?? ""))!.querySelector("input")!;
    expect(box.checked).toBe(false);
    await act(async () => box.click());
    await save();
    expect(api.saveConfig.mock.calls[0][1].modes.allow_decline).toBe(true);
  });

  it("treats a settings document from before the switch existed as off", async () => {
    const s = settings();
    delete (s.modes as { allow_decline?: boolean }).allow_decline;
    await show(view(false, s));
    const box = [...container.querySelectorAll("label")].find((l) => /Allow students to decline the offer/.test(l.textContent ?? ""))!.querySelector("input")!;
    expect(box.checked).toBe(false);
  });

  it("leaves the WhatsApp link optional: empty is saved as null and its visibility choice is off", async () => {
    const s = settings();
    s.communication.whatsapp_link = "https://chat.whatsapp.com/abc";
    await show(view(false, s));
    const input = container.querySelector<HTMLInputElement>("input[aria-label='WhatsApp group link (optional)']")!;
    const select = container.querySelector<HTMLSelectElement>("select[aria-label='When to show the WhatsApp link']")!;
    expect(select.disabled).toBe(false);
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    act(() => {
      setter.call(input, "   ");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(container.querySelector<HTMLSelectElement>("select[aria-label='When to show the WhatsApp link']")!.disabled).toBe(true);
    await save();
    expect(api.saveConfig.mock.calls[0][1].communication.whatsapp_link).toBeNull();
  });
});
