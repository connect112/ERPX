// @vitest-environment happy-dom
import { act } from "react";
import { type Root, createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PortalView } from "@/features/internship-onboarding/api";
import { MobileField } from "@/features/internship-onboarding/components/mobile-field";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const base: PortalView["mobile"] = { number: "9876543210", confirmed: false, valid: true, record_review_pending: false, editable: true };
let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  document.body.innerHTML = "";
});

async function show(mobile: PortalView["mobile"], onSave = vi.fn().mockResolvedValue(undefined)) {
  await act(async () => root.render(<MobileField mobile={mobile} onSave={onSave} busy={false} />));
  return onSave;
}
function type(value: string) {
  const input = container.querySelector<HTMLInputElement>("#info-mobile")!;
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  act(() => {
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
const button = (label: RegExp) => [...document.querySelectorAll("button")].find((b) => label.test(b.textContent ?? ""))!;

describe("MobileField", () => {
  it("shows the payment notice beside the field", async () => {
    await show(base);
    expect(container.textContent).toContain(
      "Please enter your correct mobile number. This number will be used for payment gateway verification and payment-related communication.",
    );
    expect(container.textContent).toContain("Please check it and confirm it is correct");
  });

  it("asks for confirmation with the exact wording before anything is saved", async () => {
    const onSave = await show(base);
    type("+91 81234 56789");
    await act(async () => button(/Save mobile number/).click());
    const dialog = document.querySelector('[role="dialog"]')!;
    expect(dialog.textContent).toContain("Confirm your mobile number");
    expect(dialog.textContent).toContain("Mobile number: 81234 56789");
    expect(dialog.textContent).toContain("This number may be shared with Cashfree for payment processing. Please verify that it is correct before continuing.");
    expect([...dialog.querySelectorAll("button")].map((b) => b.textContent)).toEqual(expect.arrayContaining(["Edit Number", "Confirm & Save"]));
    expect(onSave).not.toHaveBeenCalled();
  });

  it("Edit Number closes the dialog without saving; Confirm & Save saves the ten digits", async () => {
    const onSave = await show(base);
    type("81234 56789");
    await act(async () => button(/Save mobile number/).click());
    await act(async () => button(/Edit Number/).click());
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(onSave).not.toHaveBeenCalled();
    await act(async () => button(/Save mobile number/).click());
    await act(async () => button(/Confirm & Save/).click());
    expect(onSave).toHaveBeenCalledExactlyOnceWith("8123456789");
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  });

  it("refuses a number that is not an Indian mobile number without opening the dialog", async () => {
    const onSave = await show(base);
    type("12345");
    await act(async () => button(/Save mobile number/).click());
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(container.querySelector('[role="alert"]')?.textContent).toMatch(/valid 10-digit Indian mobile number/);
    expect(onSave).not.toHaveBeenCalled();
  });

  it("shows the server's reason when saving fails, and the saved / pending-review state accurately", async () => {
    const fail = vi.fn().mockRejectedValue(new Error("Onboarding is closed for you."));
    await show(base, fail);
    type("81234 56789");
    await act(async () => button(/Save mobile number/).click());
    await act(async () => button(/Confirm & Save/).click());
    expect(container.querySelector('[role="alert"]')?.textContent).toBe("Onboarding is closed for you.");
    await act(async () => root.render(<MobileField mobile={{ ...base, number: "8123456789", confirmed: true, record_review_pending: true }} onSave={fail} busy={false} />));
    expect(container.textContent).toContain("Saved. This number will be used for your payment. The internship team will review the change to your student record.");
    await act(async () => root.render(<MobileField mobile={{ ...base, number: null, valid: false }} onSave={fail} busy={false} />));
    expect(container.textContent).toContain("We do not have a valid mobile number for you yet");
  });

  it("does not offer to save a number that is already saved, and is read-only when the student can no longer change it", async () => {
    await show({ ...base, number: "9876543210", confirmed: true });
    expect(button(/Update mobile number/).hasAttribute("disabled")).toBe(true);
    await show({ ...base, editable: false });
    expect(container.querySelector("#info-mobile")).toBeNull();
    expect(container.textContent).toContain("Mobile number: 9876543210");
  });
});
