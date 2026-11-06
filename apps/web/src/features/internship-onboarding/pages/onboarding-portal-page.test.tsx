// @vitest-environment happy-dom
import { act } from "react";
import { type Root, createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PortalView } from "@/features/internship-onboarding/api";
import { OnboardingPortalPage } from "@/features/internship-onboarding/pages/onboarding-portal-page";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({ view: vi.fn(), refresh: vi.fn(), mobile: vi.fn(), save: vi.fn(), decline: vi.fn() }));
vi.mock("@/features/internship-onboarding/api", () => ({ portalApi: api }));

const EXPIRED_TEXT =
  "This onboarding link has expired. Your onboarding information has been saved. Please contact the internship team if you need assistance.";

function view(over: Partial<PortalView> = {}): PortalView {
  const base = {
    organization: "GIR Technologies",
    internship: { title: "Cloud Internship", description: null },
    student_name: "Asha Rao",
    reference: "ERPX-INT-2026-000001",
    deadline: "2026-12-01T10:00:00Z",
    timezone: "Asia/Kolkata",
    open: true,
    current_step: "welcome",
    statuses: { offer: "awaiting_response", documents: "not_submitted", payment: "not_initiated", overall: "in_progress" },
    information: { current: { name: "Asha Rao", email: "asha@example.com", phone: "9876543210", institution: "City College", details: {} }, proposed: {}, review: "none", editable: false },
    mobile: { number: "9876543210", confirmed: false, valid: true, record_review_pending: false, editable: true },
    form: { fields: [], answers: {} },
    documents: [],
    identity_document_retention_days: null,
    acceptance: { declaration: "I agree to the terms.", terms_version: "1", terms_url: null, refund_policy: null, refund_policy_version: null, payment_terms_notice: null, refund_terms: null, fees: null, accepted_at: null, declined_at: null, decline_allowed: false },
    payment: { required: false, open: false, payable: "0.00", paid: "0.00", balance: "0.00", currency: "INR", methods: [], bank: null, upi: null, deadline: null },
    refund: { requests_offered: false, can_request: false, until: null, request: null },
    completion: { completed: false, next_steps: "", whatsapp_link: null, lms_status: "not_granted", link_expires_at: null },
    contact: { email: null, phone: null },
    financial_documents: [],
  } satisfies PortalView;
  return { ...base, ...over } as PortalView;
}

let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  window.history.replaceState(null, "", "/internship-onboarding#t=" + "a".repeat(32));
  sessionStorage.clear();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  Object.values(api).forEach((m) => m.mockReset());
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  document.body.innerHTML = "";
});

async function show(v: PortalView | Error) {
  if (v instanceof Error) api.view.mockRejectedValue(v);
  else api.view.mockResolvedValue(v);
  await act(async () => root.render(<OnboardingPortalPage />));
  await act(async () => void (await Promise.resolve()));
}
const completed = (link: string | null): Partial<PortalView> => ({
  statuses: { offer: "accepted", documents: "verified", payment: "not_required", overall: "completed" },
  completion: { completed: true, next_steps: "Orientation on Monday.", whatsapp_link: link, lms_status: "granted", link_expires_at: "2099-01-01T00:00:00Z" },
});

describe("the student onboarding page", () => {
  it("shows no Decline offer option unless the internship allows declining", async () => {
    await show(view());
    expect(container.textContent).toContain("Accept your offer");
    expect(container.textContent).not.toContain("Decline the offer");
    expect(container.querySelector("details")).toBeNull();
  });

  it("shows the existing decline action with its confirmation when declining is allowed", async () => {
    await show(view({ acceptance: { ...view().acceptance, decline_allowed: true } }));
    expect(container.textContent).toContain("Decline the offer");
    const confirm = vi.fn(() => false);
    window.confirm = confirm;
    api.decline.mockResolvedValue(view());
    await act(async () => [...container.querySelectorAll("button")].find((b) => b.textContent === "Decline")!.click());
    expect(confirm).toHaveBeenCalledWith("Decline this internship offer? This cannot be undone here.");
    expect(api.decline).not.toHaveBeenCalled();
  });

  it("still shows a decline that was recorded earlier, even when declining is now switched off", async () => {
    await show(view({ statuses: { offer: "declined", documents: "not_submitted", payment: "not_initiated", overall: "cancelled" } }));
    expect(container.textContent).toContain("You declined this offer.");
  });

  it("shows no WhatsApp button, placeholder or empty section when no group link is configured", async () => {
    await show(view(completed(null)));
    expect(container.textContent).toContain("Congratulations, Asha Rao!");
    expect(container.textContent?.toLowerCase()).not.toContain("whatsapp");
    expect(container.querySelector("a[href*='whatsapp']")).toBeNull();
  });

  it("shows the group button when a link is configured and visible", async () => {
    await show(view(completed("https://chat.whatsapp.com/abc")));
    const a = container.querySelector<HTMLAnchorElement>("a[href='https://chat.whatsapp.com/abc']")!;
    expect(a.textContent).toBe("Join the WhatsApp group");
    expect(a.rel).toContain("noopener");
  });

  it("puts the mobile number with its notice in 'Your details', and saves only after confirmation", async () => {
    await show(view());
    expect(container.textContent).toContain("Please enter your correct mobile number. This number will be used for payment gateway verification and payment-related communication.");
    const input = container.querySelector<HTMLInputElement>("#info-mobile")!;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    act(() => {
      setter.call(input, "81234 56789");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    api.mobile.mockResolvedValue(view({ mobile: { number: "8123456789", confirmed: true, valid: true, record_review_pending: true, editable: true } }));
    await act(async () => [...container.querySelectorAll("button")].find((b) => /Save mobile number/.test(b.textContent ?? ""))!.click());
    expect(api.mobile).not.toHaveBeenCalled(); // the dialog comes first
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Confirm your mobile number");
    await act(async () => [...document.querySelectorAll("button")].find((b) => b.textContent === "Confirm & Save")!.click());
    expect(api.mobile).toHaveBeenCalledExactlyOnceWith("a".repeat(32), "8123456789", true);
    expect(container.textContent).toContain("Saved. This number will be used for your payment.");
  });

  it("never sends the phone in a draft save (the number has its own confirmed step)", async () => {
    await show(view({ information: { ...view().information, editable: true } }));
    api.save.mockResolvedValue({ errors: {} });
    api.view.mockResolvedValue(view({ information: { ...view().information, editable: true } }));
    await act(async () => [...container.querySelectorAll("button")].find((b) => /Save and continue later/.test(b.textContent ?? ""))!.click());
    expect(api.save).toHaveBeenCalledTimes(1);
    expect(api.save.mock.calls[0][1].info).toEqual({ name: "Asha Rao" });
  });

  it("warns, without blocking, when payment is open and there is no usable mobile number", async () => {
    await show(
      view({
        statuses: { offer: "accepted", documents: "submitted", payment: "not_initiated", overall: "awaiting_payment" },
        payment: { ...view().payment, required: true, open: true, payable: "5000.00", balance: "5000.00", methods: ["cashfree"] },
        mobile: { number: null, confirmed: false, valid: false, record_review_pending: false, editable: true },
      }),
    );
    expect(container.textContent).toContain("Enter and save a valid mobile number");
    expect([...container.querySelectorAll("button")].find((b) => /online/.test(b.textContent ?? ""))?.hasAttribute("disabled")).toBe(false);
  });
});

describe("an expired personal link", () => {
  const envelope = { response: { status: 410, data: { error: { code: "onboarding_link_expired", message: EXPIRED_TEXT } } } };

  it("shows the expiry message, not the generic 'link not valid' page", async () => {
    await show(Object.assign(new Error("gone"), envelope));
    expect(container.textContent).toContain("This onboarding link has expired");
    expect(container.textContent).toContain(EXPIRED_TEXT);
    expect(container.textContent).not.toContain("Onboarding link not valid");
    expect(container.querySelector("button")).toBeNull(); // nothing to do here
  });

  it("replaces the page when the server refuses a later action because the hour ended", async () => {
    await show(view({ information: { ...view().information, editable: true } }));
    api.save.mockRejectedValue(Object.assign(new Error("gone"), envelope));
    await act(async () => [...container.querySelectorAll("button")].find((b) => /Save and continue later/.test(b.textContent ?? ""))!.click());
    expect(container.textContent).toContain(EXPIRED_TEXT);
    expect(container.textContent).not.toContain("Accept your offer");
  });

  it("tells a completed student when the link stops working, and checks again at that moment", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    try {
      const soon = new Date(Date.now() + 5000).toISOString();
      await show(view({ ...completed(null), completion: { ...completed(null).completion!, link_expires_at: soon } }));
      expect(container.textContent).toContain("this personal link stops working at");
      api.view.mockRejectedValue(Object.assign(new Error("gone"), envelope));
      await act(async () => void vi.advanceTimersByTime(7000));
      await act(async () => void (await Promise.resolve()));
      expect(container.textContent).toContain(EXPIRED_TEXT);
    } finally {
      vi.useRealTimers();
    }
  });
});
