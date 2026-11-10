import type { InternshipFee } from "@/features/courses/api/courses-api";

const SYMBOLS: Record<string, string> = { INR: "₹" };

export function money(amount: string, currency: string): string {
  const n = Number(amount);
  const text = n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${SYMBOLS[currency] ?? `${currency} `}${text}`;
}

/** What a student pays in total under the internship's own onboarding settings, with the tax it includes when there is one. */
export function feeText(fee: InternshipFee): string {
  const tax = Number(fee.tax) > 0 ? ` (includes ${fee.tax_label} ${money(fee.tax, fee.currency)})` : "";
  return `${money(fee.total, fee.currency)}${tax}`;
}
