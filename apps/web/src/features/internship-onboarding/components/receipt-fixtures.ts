// Shared test data for the Receipt Designer components (used by tests only).
import type { DesignerView, ImageSlot, ReceiptAssetInfo, ReceiptDesign, ReceiptLabels } from "@/features/internship-onboarding/receipts-api";

export const slot = (over: Partial<ImageSlot> = {}): ImageSlot => ({ show: true, asset_id: null, align: "auto", width_mm: 40, height_mm: 18, ...over });

export const LABELS: ReceiptLabels = {
  title_receipt: "PAYMENT RECEIPT", title_tax_invoice: "TAX INVOICE", title_credit_note: "CREDIT NOTE",
  subtitle_receipt: "", subtitle_tax_invoice: "", subtitle_credit_note: "",
  number: "No.", issue_date: "Date:", gstin: "GSTIN:", mobile: "Mobile:", billed_to: "BILLED TO", payment_details: "PAYMENT DETAILS",
  application: "Application", programme: "Programme", payment_method: "Payment method", transaction_ref: "Transaction ref.", payment_date: "Payment date",
  against: "Against", payment_status: "Payment status", col_description: "DESCRIPTION", col_amount: "AMOUNT", total_received: "Total received",
  total_refunded: "Total refunded", status_paid: "PAID", status_refunded: "REFUNDED", status_paid_word: "Paid", status_refunded_word: "Refunded",
  system_line: "This document was issued electronically and needs no signature.", page: "Page",
};  // prettier-ignore

export const design = (over: Partial<ReceiptDesign> = {}): ReceiptDesign => ({
  branding: { brand_color: "#1F3A5F", accent_color: "#E8EDF4", header_align: "left" },
  contacts: { website: "", email: "", phone: "" },
  sections: { student_email: true, student_mobile: false, application_reference: true, programme: true, payment_method: true, issuer_contacts: true, issuer_address: true, thank_you: true, footer: true },
  texts: { thank_you: "Thank you for your payment.", footer: "", header_text: "", description_note: "", terms: "" },
  labels: { ...LABELS },
  style: { body_size: 9, title_size: 17, issuer_size: 14, section_gap_mm: 7, margin_x_mm: 18, table_borders: "lines", header_rule: true },
  logo: slot(),
  signature: slot({ show: false, width_mm: 36, height_mm: 14 }),
  stamp: slot({ show: false, width_mm: 24, height_mm: 24 }),
  signature_align: "right",
  signatory_label: "Authorized signatory",
  body_order: ["details", "items", "thank_you", "signature"],
  ...over,
});

export const asset = (id: string, name = "logo.png", kind: ReceiptAssetInfo["kind"] = "logo"): ReceiptAssetInfo => ({
  id, kind, filename: name, width_px: 300, height_px: 120, size_bytes: 1000, created_at: "2026-11-01T00:00:00Z",
});

export const view = (over: Partial<DesignerView> = {}): DesignerView => ({
  effective: { design: design(), source: "default", version: 0, layout: "legacy" },
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
