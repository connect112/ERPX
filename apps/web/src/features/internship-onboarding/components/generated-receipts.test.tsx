// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { type Root, createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GeneratedReceipts } from "@/features/internship-onboarding/components/generated-receipts";
import type { ReceiptRow } from "@/features/internship-onboarding/receipts-api";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({ receipts: vi.fn(), receiptPdf: vi.fn(), history: vi.fn() }));
vi.mock("@/features/internship-onboarding/receipts-api", () => ({ receiptsApi: api }));

const row = (over: Partial<ReceiptRow> = {}): ReceiptRow => ({
  id: "d1", number: "RCPT-2026-000001", kind: "receipt", student: "Asha Rao", email: "asha@example.com", internship: "Cloud Internship", application: "ERPX-INT-2026-000001",
  amount: "5000.00", currency: "INR", paid_on: "2026-11-04", method: "cashfree", issued_at: "2026-11-04T10:00:00Z", email_status: "sent", emailed_at: "2026-11-04T10:01:00Z",
  transaction_id: "tx1", design_source: "default", design_version: 0, pages: 1, engine: "receipt_pdf", ...over,
});
const history = {
  document: { id: "d1", number: "RCPT-2026-000001", kind: "receipt", amount: "5000.00", currency: "INR", issued_at: "2026-11-04T10:00:00Z", sha256: "ab".repeat(32) },
  transaction: { id: "tx1", kind: "payment", method: "cashfree", amount: "5000.00", currency: "INR", status: "confirmed", reference: "5114910123456", paid_on: "2026-11-04", verified_at: "2026-11-04T10:00:00Z", provider: "cashfree" },
  design: { source: "default", version: 0, assets: null, engine: "receipt_pdf", pages: 1 },
  delivery: { status: "sent", attempts: 1, emailed_at: "2026-11-04T10:01:00Z" },
  events: [{ at: "2026-11-04T10:00:00Z", actor: "system", event: "document_issued", detail: { number: "RCPT-2026-000001" } }],
};

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  Object.values(api).forEach((m) => m.mockReset());
  api.receipts.mockResolvedValue({ total: 2, items: [row(), row({ id: "d2", number: "RCPT-CN-2026-000001", kind: "credit_note", student: "Ravi K", engine: "legacy", pages: null, design_source: null, email_status: "failed" })] });
  api.receiptPdf.mockResolvedValue(new Blob(["%PDF-1.4"], { type: "application/pdf" }));
  api.history.mockResolvedValue(history);
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:r/1");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  document.body.innerHTML = "";
  vi.useRealTimers();
  vi.restoreAllMocks();
});

async function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await act(async () =>
    root.render(
      <QueryClientProvider client={client}>
        <GeneratedReceipts internshipId="i1" timezone="Asia/Kolkata" />
      </QueryClientProvider>,
    ),
  );
  await settle(0);
}
const settle = async (ms = 500) => {
  await act(async () => void vi.advanceTimersByTime(ms));
  await act(async () => void (await Promise.resolve()));
  await act(async () => void (await Promise.resolve()));
};
const lastFilters = () => api.receipts.mock.calls.at(-1)![1];
function setValue(el: HTMLInputElement | HTMLSelectElement, value: string) {
  act(() => {
    const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(el, value);
    el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }));
  });
}
const byLabel = (label: string) => container.querySelector<HTMLInputElement & HTMLSelectElement>(`[aria-label='${label}']`)!;
const action = (label: RegExp) => [...document.querySelectorAll("button")].find((b) => label.test(b.getAttribute("aria-label") ?? ""))!;

describe("GeneratedReceipts", () => {
  it("lists the documents with number, student, internship, amount, payment date, document type, email status and creation date", async () => {
    await show();
    const text = container.textContent ?? "";
    for (const cell of ["RCPT-2026-000001", "Payment receipt", "Asha Rao", "Cloud Internship", "₹5,000.00", "2026-11-04", "Sent", "Credit note", "Ravi K", "Failed"]) expect(text).toContain(cell);
    expect(text).toContain("1–2 of 2");
    expect(lastFilters()).toMatchObject({ limit: 25, offset: 0 });
  });

  it("searches after a short pause and filters by type, email status and issue dates, starting again from the first page", async () => {
    await show();
    setValue(byLabel("Search receipts"), "asha");
    await settle(100);
    expect(lastFilters().q).toBe(""); // not yet: the person is still typing
    await settle(400);
    expect(lastFilters().q).toBe("asha");
    setValue(byLabel("Document type"), "credit_note");
    await settle();
    expect(lastFilters()).toMatchObject({ q: "asha", kind: "credit_note", offset: 0 });
    setValue(byLabel("Email status"), "failed");
    setValue(byLabel("Issued from"), "2026-11-01");
    setValue(byLabel("Issued to"), "2026-11-30");
    await settle();
    expect(lastFilters()).toMatchObject({ email_status: "failed", issued_from: "2026-11-01", issued_to: "2026-11-30" });
  });

  it("pages through a long list", async () => {
    api.receipts.mockResolvedValue({ total: 60, items: [row()] });
    await show();
    expect(container.textContent).toContain("1–25 of 60");
    await act(async () => [...container.querySelectorAll("button")].find((b) => b.textContent === "Next")!.click());
    await settle(0);
    expect(lastFilters().offset).toBe(25);
    expect(container.textContent).toContain("26–50 of 60");
  });

  it("opens a document in the page exactly as stored, and releases the temporary file when it closes", async () => {
    await show();
    await act(async () => action(/View RCPT-2026-000001/).click());
    await settle(0);
    expect(api.receiptPdf).toHaveBeenCalledWith("i1", "d1");
    expect(document.querySelector("iframe")?.getAttribute("src")).toMatch(/^blob:r\/1/);
    expect(document.body.textContent).toContain("exactly as it was issued");
    await act(async () => (document.querySelector('[role="dialog"] button.absolute, [role="dialog"] button[class*="absolute"]') as HTMLButtonElement)?.click());
    expect(URL.revokeObjectURL).toHaveBeenCalled();
  });

  it("downloads the stored file under its document number", async () => {
    await show();
    const saved: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
    await act(async () => action(/Download RCPT-CN-2026-000001/).click());
    await settle(0);
    expect(api.receiptPdf).toHaveBeenCalledWith("i1", "d2", true);
    expect(saved).toEqual(["RCPT-CN-2026-000001.pdf"]);
  });

  it("shows the linked payment, the design used, the checksum, delivery and the timeline", async () => {
    await show();
    await act(async () => action(/History and payment of RCPT-2026-000001/).click());
    await settle(0);
    const text = document.body.textContent ?? "";
    expect(api.history).toHaveBeenCalledWith("i1", "d1");
    for (const part of ["Linked payment", "5114910123456", "confirmed", "default design, version 0, 1 page", "ab".repeat(32), "1 attempt", "document issued"]) expect(text).toContain(part);
  });

  it("says when nothing matches and when a download fails", async () => {
    api.receipts.mockResolvedValue({ total: 0, items: [] });
    await show();
    expect(container.textContent).toContain("No documents match.");
    expect(container.textContent).toContain("0 documents");
    api.receipts.mockResolvedValue({ total: 1, items: [row()] });
    setValue(byLabel("Document type"), "receipt");
    await settle();
    api.receiptPdf.mockRejectedValue({ response: { data: { error: { message: "The stored copy does not match its checksum." } } } });
    await act(async () => action(/Download RCPT-2026-000001/).click());
    await settle(0);
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("The stored copy does not match its checksum.");
  });
});
