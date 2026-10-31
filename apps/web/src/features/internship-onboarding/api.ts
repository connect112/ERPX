import { apiClient } from "@/api/client";

/** The onboarding settings document (modules/internship_onboarding/config.py). Amounts are strings with two decimals. */
export type FieldType =
  | "short_text" | "long_text" | "email" | "phone" | "number" | "date" | "dropdown" | "radio" | "checkbox" | "multi_select" | "declaration";
export type PaymentMethod = "cashfree" | "bank_transfer" | "upi";

export interface FormFieldDef {
  key: string;
  label: string;
  type: FieldType;
  description?: string;
  placeholder?: string;
  required?: boolean;
  editable?: boolean;
  options?: string[];
  visible_if?: { field: string; equals: string | boolean } | null;
}

export interface DocumentDef {
  key: string;
  label: string;
  instructions?: string;
  required?: boolean;
  types?: ("pdf" | "jpg" | "png")[];
  max_mb?: number;
  sensitive?: boolean;
}

export interface OnboardingSettings {
  modes: {
    mode: "manual" | "automated" | "hybrid";
    allow_info_edit: boolean;
    require_documents: boolean;
    require_payment: boolean;
    payment_order: "after_submission" | "after_document_approval";
    lms_access: "manual" | "automatic";
    allow_late_onboarding: boolean;
    reminders: boolean;
    invoice_emails: boolean;
  };
  fees: {
    currency: "INR";
    base_amount: string;
    description: string;
    tax_mode: "none" | "inclusive" | "exclusive";
    tax_rate_percent: string;
    tax_label: string;
    discount_amount: string;
    late_fee: { mode: "none" | "fixed" | "percent"; value: string };
    methods: PaymentMethod[];
  };
  deadlines: {
    timezone: string;
    opens_at: string | null;
    closes_at: string | null;
    acceptance_deadline: string | null;
    documents_deadline: string | null;
    payment_deadline: string | null;
    payment_grace_hours: number;
  };
  documents: DocumentDef[];
  form: FormFieldDef[];
  declaration: { text: string; terms_version: string; terms_url: string | null };
  payment_accounts: {
    bank: { holder: string; bank: string; account_number: string; ifsc: string; branch: string; instructions: string } | null;
    upi: { vpa: string; beneficiary: string; instructions: string } | null;
  };
  communication: {
    contact_email: string | null;
    contact_phone: string | null;
    whatsapp_link: string | null;
    whatsapp_visibility: "after_completion" | "after_acceptance";
    reminder_days: number[];
    next_steps: string;
  };
  issuer: { legal_name: string; address: string; gstin: string | null; receipt_prefix: string; footer: string };
  policies: { refund_policy: string; identity_document_retention_days: number | null };
  reference_prefix: string;
}

export interface FinancialDoc {
  id: string;
  kind: "receipt" | "tax_invoice" | "credit_note";
  number: string;
  amount: string;
  currency: string;
  issued_at: string;
  application?: string;
  student?: string;
  email_status?: string;
}

export interface ConfigView {
  settings: OnboardingSettings;
  version: number;
  template_id: string | null;
  template_version: number | null;
  can_edit_finance: boolean;
  fee_preview: Record<string, string>;
  cashfree_available: boolean;
}

export interface BoardRow {
  student_id: string;
  name: string;
  email: string;
  reference: string | null;
  offer_status: string;
  document_status: string;
  payment_status: string;
  overall_status: string;
  lms_status: string;
  deadline: string | null;
  payable: string;
  received: string;
  outstanding: string;
  reopened: boolean;
  last_activity_at: string | null;
  link_active: boolean;
  documents_awaiting_review: number;
}

export interface Board {
  rows: BoardRow[];
  metrics: Record<string, number>;
  money: { payable: string; received: string; outstanding: string };
  currency: string;
  mode: string;
}

export interface StudentDetail {
  student: { id: string; name: string; email: string; phone: string | null; details: Record<string, string> };
  reference: string;
  statuses: { offer: string; documents: string; payment: string; overall: string; lms: string };
  deadline: string | null;
  link_active: boolean;
  link_issued_at: string | null;
  started_at: string | null;
  current_step: string;
  info_original: Record<string, unknown>;
  info_proposed: { name?: string; phone?: string; details?: Record<string, string> };
  info_review_status: string;
  form_responses: Record<string, unknown>;
  acceptance: { accepted_at: string | null; declined_at: string | null; decline_reason: string | null; terms_version: string | null; fee_snapshot: Record<string, string> | null };
  reopened: { at: string | null; reason: string | null; until: string | null };
  documents: { id: string; key: string; version: number; status: string; filename: string; size_bytes: number; uploaded_at: string; review_note: string | null; sensitive: boolean; scan_status: "not_scanned" | "clean"; keep_until: string | null }[];
  payments: LedgerRow[] | null;
  events: { at: string; actor: string; event: string; detail: Record<string, unknown> }[];
}

export interface LedgerRow {
  id: string;
  kind: string;
  method: string | null;
  amount: string;
  currency: string;
  status: string;
  reference?: string | null;
  transaction_reference?: string | null;
  reference_number?: string;
  paid_on: string | null;
  has_proof: boolean;
  remarks: string | null;
  note: string | null;
  rejection_reason: string | null;
  created_at: string;
  same_proof_used_elsewhere?: boolean;
}

export interface TemplateRow {
  id: string;
  name: string;
  description: string | null;
  version: number;
  archived: boolean;
  settings: OnboardingSettings;
  updated_at: string;
}

const flow = (id: string) => `/our-internships/${id}/onboarding-flow`;

export const onboardingFlowApi = {
  config: (id: string) => apiClient.get<ConfigView>(`${flow(id)}/config`).then((r) => r.data),
  saveConfig: (id: string, settings: OnboardingSettings) => apiClient.put<ConfigView>(`${flow(id)}/config`, { settings }).then((r) => r.data),
  applyTemplate: (id: string, templateId: string) =>
    apiClient.post<ConfigView>(`${flow(id)}/apply-template`, { template_id: templateId }).then((r) => r.data),
  board: (id: string) => apiClient.get<Board>(`${flow(id)}/dashboard`).then((r) => r.data),
  student: (id: string, studentId: string) => apiClient.get<StudentDetail>(`${flow(id)}/students/${studentId}`).then((r) => r.data),
  newLink: (id: string, studentId: string) =>
    apiClient.post<{ reference: string; link: string; note: string }>(`${flow(id)}/students/${studentId}/link`).then((r) => r.data),
  revokeLink: (id: string, studentId: string) => apiClient.post(`${flow(id)}/students/${studentId}/link/revoke`).then((r) => r.data),
  invite: (id: string, studentIds: string[]) =>
    apiClient.post<{ queued: number; skipped: { name: string; reason: string }[] }>(`${flow(id)}/invitations`, { student_ids: studentIds }).then((r) => r.data),
  reopen: (id: string, body: { student_ids: string[]; until: string; reason: string; late_fee: string; late_fee_amount?: string | null }) =>
    apiClient.post<{ reopened: number; skipped: { name: string; reason: string }[] }>(`${flow(id)}/reopen`, body).then((r) => r.data),
  reviewInfo: (id: string, studentId: string, approve: boolean) =>
    apiClient.post(`${flow(id)}/students/${studentId}/info-review`, { approve }).then((r) => r.data),
  previewDocument: (id: string, documentId: string) =>
    apiClient.get<{ url: string }>(`${flow(id)}/documents/${documentId}/preview`).then((r) => r.data.url),
  reviewDocument: (id: string, documentId: string, approve: boolean, note?: string) =>
    apiClient.post(`${flow(id)}/documents/${documentId}/review`, { approve, note }).then((r) => r.data),
  payments: (id: string, status?: string) =>
    apiClient.get<LedgerRow[]>(`${flow(id)}/payments`, { params: { status_filter: status || undefined } }).then((r) => r.data),
  proof: (id: string, txId: string) => apiClient.get<{ url: string }>(`${flow(id)}/payments/${txId}/proof`).then((r) => r.data.url),
  verifyPayment: (id: string, txId: string, body: { approve: boolean; amount_received?: string; note?: string }) =>
    apiClient.post(`${flow(id)}/payments/${txId}/verify`, body).then((r) => r.data),
  financialDocuments: (id: string) => apiClient.get<FinancialDoc[]>(`${flow(id)}/financial-documents`).then((r) => r.data),
  financialUrl: (id: string, docId: string) =>
    apiClient.get<{ url: string }>(`${flow(id)}/financial-documents/${docId}/download`).then((r) => r.data.url),
  resendFinancial: (id: string, docId: string) => apiClient.post(`${flow(id)}/financial-documents/${docId}/resend`).then((r) => r.data),
  refund: (id: string, txId: string, amount: string, reason: string) =>
    apiClient.post<{ id: string; status: string }>(`${flow(id)}/payments/${txId}/refund`, { amount, reason }).then((r) => r.data),
  decideRefund: (id: string, txId: string, body: { approve: boolean; reference?: string; note?: string }) =>
    apiClient.post(`${flow(id)}/refunds/${txId}/decide`, body).then((r) => r.data),
  cancel: (id: string, studentId: string, reason: string) =>
    apiClient.post(`${flow(id)}/students/${studentId}/cancel`, { reason }).then((r) => r.data),
  exportCsv: (id: string, which: "export" | "payments") =>
    apiClient.get<Blob>(`${flow(id)}/${which}.csv`, { responseType: "blob" }).then((r) => r.data),
  templates: () => apiClient.get<TemplateRow[]>("/internship-onboarding-templates").then((r) => r.data),
  saveAsTemplate: (name: string, fromInternshipId: string) =>
    apiClient.post<TemplateRow>("/internship-onboarding-templates", { name, from_internship_id: fromInternshipId }).then((r) => r.data),
};

/** The student's side: the token goes in a header, never in a URL the server sees. */
export interface PortalView {
  organization: string;
  internship: { title: string; description: string | null };
  student_name: string;
  reference: string;
  deadline: string | null;
  timezone: string;
  open: boolean;
  current_step: string;
  statuses: { offer: string; documents: string; payment: string; overall: string };
  information: {
    current: { name: string; email: string; phone: string | null; institution: string | null; details: Record<string, string> };
    proposed: { name?: string; phone?: string; details?: Record<string, string> };
    review: string;
    editable: boolean;
  };
  form: { fields: FormFieldDef[]; answers: Record<string, unknown> };
  documents: (DocumentDef & { status: string; filename: string | null; note: string | null })[];
  identity_document_retention_days: number | null;
  acceptance: { declaration: string; terms_version: string; terms_url: string | null; refund_policy: string | null; fees: Record<string, string> | null; accepted_at: string | null; declined_at: string | null };
  payment: {
    required: boolean;
    open: boolean;
    payable: string;
    paid: string;
    balance: string;
    currency: string;
    methods: PaymentMethod[];
    bank: { holder: string; bank: string; account_number: string; ifsc: string; branch: string; instructions: string } | null;
    upi: { vpa: string; beneficiary: string; instructions: string } | null;
    deadline: string | null;
  };
  completion: { completed: boolean; next_steps: string; whatsapp_link: string | null; lms_status: string };
  contact: { email: string | null; phone: string | null };
  financial_documents: FinancialDoc[];
}

const P = "/public/internship-onboarding";
const h = (token: string) => ({ headers: { "X-Onboarding-Token": token } });

export const portalApi = {
  view: (t: string) => apiClient.get<PortalView>(P, h(t)).then((r) => r.data),
  save: (t: string, body: { step?: string; info?: Record<string, unknown>; answers?: Record<string, unknown> }) =>
    apiClient.put<{ errors: Record<string, string> }>(`${P}/draft`, body, h(t)).then((r) => r.data),
  upload: (t: string, key: string, file: File, onProgress?: (pct: number) => void) => {
    const data = new FormData();
    data.append("file", file);
    return apiClient
      .post(`${P}/documents/${key}`, data, {
        ...h(t),
        headers: { "X-Onboarding-Token": t, "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
      })
      .then((r) => r.data);
  },
  accept: (t: string, terms_version: string) =>
    apiClient.post<PortalView>(`${P}/accept`, { confirmed: true, terms_version }, h(t)).then((r) => r.data),
  decline: (t: string, reason: string) => apiClient.post<PortalView>(`${P}/decline`, { reason }, h(t)).then((r) => r.data),
  manualPayment: (t: string, body: { method: string; reference: string; paid_on: string; amount: string; remarks?: string }, proof: File) => {
    const data = new FormData();
    Object.entries(body).forEach(([k, v]) => v !== undefined && data.append(k, v));
    data.append("proof", proof);
    return apiClient
      .post<PortalView>(`${P}/payments/manual`, data, { headers: { "X-Onboarding-Token": t, "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },
  checkout: (t: string) =>
    apiClient.post<{ payment_session_id: string; environment: "sandbox" | "production"; order_id: string }>(`${P}/payments/checkout`, {}, h(t)).then((r) => r.data),
  financialUrl: (t: string, docId: string) =>
    apiClient.get<{ url: string }>(`${P}/financial-documents/${docId}`, h(t)).then((r) => r.data.url),
  refresh: (t: string) => apiClient.post<PortalView & { outcome: string }>(`${P}/payments/refresh`, {}, h(t)).then((r) => r.data),
};
