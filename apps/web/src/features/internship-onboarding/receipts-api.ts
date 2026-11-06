import { apiClient } from "@/api/client";

/** The look of receipts (modules/internship_onboarding/receipt_design.py). Presentation only: the legal identity is the issuer's settings. */
export type HeaderAlign = "left" | "center" | "right";
export type ReceiptKind = "receipt" | "tax_invoice" | "credit_note";
export type AssetKind = "logo" | "signature" | "stamp";

export interface ImageSlot {
  show: boolean;
  asset_id: string | null;
  width_mm: number;
  height_mm: number;
}

export interface ReceiptSections {
  student_email: boolean;
  student_mobile: boolean;
  application_reference: boolean;
  programme: boolean;
  payment_method: boolean;
  issuer_contacts: boolean;
  thank_you: boolean;
  footer: boolean;
}

export interface ReceiptDesign {
  branding: { brand_color: string; accent_color: string; header_align: HeaderAlign };
  contacts: { website: string; email: string; phone: string };
  sections: ReceiptSections;
  texts: { thank_you: string; footer: string };
  logo: ImageSlot;
  signature: ImageSlot;
  stamp: ImageSlot;
  signatory_label: string;
}

export interface ReceiptAssetInfo {
  id: string;
  kind: AssetKind;
  filename: string;
  width_px: number;
  height_px: number;
  size_bytes: number;
  created_at: string;
}

export interface ReceiptTemplate {
  id: string;
  name: string;
  description: string | null;
  version: number;
  design: ReceiptDesign;
}

export interface DesignerView {
  effective: { design: ReceiptDesign; source: "internship" | "organization" | "default"; version: number };
  internship_design: { design: ReceiptDesign; version: number } | null;
  organization_design: { design: ReceiptDesign; version: number } | null;
  built_in: ReceiptDesign;
  templates: ReceiptTemplate[];
  assets: ReceiptAssetInfo[];
  can_edit: boolean;
  issuer: { legal_name: string; address: string; gstin: string | null; receipt_prefix: string; footer: string };
  fee: { tax_mode: string; invoices_issued: boolean };
}

export interface PreviewResult {
  blob: Blob;
  pages: number;
  watermark: string;
}

export interface ReceiptRow {
  id: string;
  number: string;
  kind: ReceiptKind;
  student: string;
  email: string | null;
  internship: string;
  application: string;
  amount: string;
  currency: string;
  paid_on: string | null;
  method: string | null;
  issued_at: string;
  email_status: "none" | "pending" | "sent" | "failed";
  emailed_at: string | null;
  transaction_id: string;
  design_source: string | null;
  design_version: number | null;
  pages: number | null;
  engine: "receipt_pdf" | "legacy";
}

export interface ReceiptFilters {
  q?: string;
  kind?: ReceiptKind | "";
  email_status?: string;
  issued_from?: string;
  issued_to?: string;
  limit?: number;
  offset?: number;
}

export interface ReceiptHistory {
  document: { id: string; number: string; kind: ReceiptKind; amount: string; currency: string; issued_at: string; sha256: string };
  transaction: { id: string; kind: string; method: string | null; amount: string; currency: string; status: string; reference: string | null; paid_on: string | null; verified_at: string | null; provider: string | null } | null;
  design: { source: string | null; version: number | null; assets: Record<string, { id: string; sha256: string }> | null; engine: string; pages: number | null };
  delivery: { status: string; attempts: number; emailed_at: string | null };
  events: { at: string; actor: string; event: string; detail: Record<string, unknown> }[];
}

const base = (id: string) => `/our-internships/${id}`;
const designer = (id: string) => `${base(id)}/receipt-designer`;

export const receiptsApi = {
  designer: (id: string) => apiClient.get<DesignerView>(designer(id)).then((r) => r.data),
  save: (id: string, scope: "internship" | "organization", design: ReceiptDesign, baseVersion?: number) =>
    apiClient.put<{ version: number; message: string }>(`${designer(id)}/design`, { scope, design, base_version: baseVersion }).then((r) => r.data),
  reset: (id: string, scope: "internship" | "organization") => apiClient.delete(`${designer(id)}/design`, { params: { scope } }).then((r) => r.data),
  /** Read-only: the PDF as the draft would draw it. Nothing is issued, numbered, stored or sent. */
  preview: (id: string, body: { design?: ReceiptDesign; kind: ReceiptKind; source: "sample" | "transaction"; transaction_id?: string }) =>
    apiClient.post<Blob>(`${designer(id)}/preview`, body, { responseType: "blob" }).then(
      (r): PreviewResult => ({ blob: r.data, pages: Number(r.headers["x-page-count"] ?? 1), watermark: String(r.headers["x-watermark"] ?? "") }),
    ),
  uploadAsset: (id: string, kind: AssetKind, file: File) => {
    const data = new FormData();
    data.append("kind", kind);
    data.append("file", file);
    return apiClient.post<ReceiptAssetInfo>(`${designer(id)}/assets`, data, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
  },
  assetImage: (id: string, assetId: string) => apiClient.get<Blob>(`${designer(id)}/assets/${assetId}/image`, { responseType: "blob" }).then((r) => r.data),
  deleteAsset: (id: string, assetId: string) => apiClient.delete(`${designer(id)}/assets/${assetId}`).then((r) => r.data),
  createTemplate: (id: string, name: string, design: ReceiptDesign, description?: string) =>
    apiClient.post<{ id: string }>(`${designer(id)}/templates`, { name, design, description }).then((r) => r.data),
  applyTemplate: (id: string, templateId: string, scope: "internship" | "organization") =>
    apiClient.post(`${designer(id)}/templates/${templateId}/apply`, { scope }).then((r) => r.data),
  archiveTemplate: (id: string, templateId: string) => apiClient.delete(`${designer(id)}/templates/${templateId}`).then((r) => r.data),

  receipts: (id: string, filters: ReceiptFilters) =>
    apiClient
      .get<{ total: number; items: ReceiptRow[] }>(`${base(id)}/receipts`, { params: Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "" && v !== undefined)) })
      .then((r) => r.data),
  /** The stored PDF exactly as issued (never drawn again), fetched with the staff member's own login: there is no public link. */
  receiptPdf: (id: string, documentId: string, download = false) =>
    apiClient.get<Blob>(`${base(id)}/receipts/${documentId}/pdf`, { params: download ? { download: true } : undefined, responseType: "blob" }).then((r) => r.data),
  history: (id: string, documentId: string) => apiClient.get<ReceiptHistory>(`${base(id)}/receipts/${documentId}/history`).then((r) => r.data),
};
