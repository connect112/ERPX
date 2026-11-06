/**
 * The mobile number a student gives for payments. Mirrors modules/internship_onboarding/phone.py (the server is the judge; this only
 * lets the page say what is wrong before asking for confirmation): an Indian mobile number, ten digits starting 6-9, with an optional
 * +91, 91 or leading 0.
 */
const TYPED = /^\+?[0-9(][0-9 ()-]{6,18}$/;
const MOBILE = /^[6-9][0-9]{9}$/;

export const MOBILE_NOTICE = "Please enter your correct mobile number. This number will be used for payment gateway verification and payment-related communication.";
export const MOBILE_INVALID = "Enter a valid 10-digit Indian mobile number (for example 98765 43210). A +91 prefix is fine.";

export function normalizeMobile(raw: string | null | undefined): string | null {
  const text = (raw ?? "").trim().replace(/\s+/g, " ");
  if (!TYPED.test(text)) return null;
  let digits = text.replace(/\D/g, "");
  if (text.startsWith("+") && !digits.startsWith("91")) return null;
  if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  else if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
  return MOBILE.test(digits) ? digits : null;
}

/** "98765 43210": how the number is read back to the student in the confirmation. */
export function displayMobile(digits: string): string {
  return digits.length === 10 ? `${digits.slice(0, 5)} ${digits.slice(5)}` : digits;
}
