import { apiClient } from "@/api/client";

export type CertificateKind = "participation" | "completion";
export type Delivery = "not_selected" | "not_created" | "held_for_review" | "queued" | "sent";

export interface CertificateInfo {
  kind: CertificateKind;
  label: string;
  exam_id: string;
  has_design: boolean;
  review_required: boolean;
  eligible_count: number;
  sent_count: number;
}

export interface EligibilityRow {
  selection_id: string;
  student_name: string;
  student_email: string;
  kind: CertificateKind | null;
  delivery: Delivery;
  certificate_number: string | null;
  sent_at: string | null;
  locked: boolean;
}

export interface CertificatesOverview {
  certificates: CertificateInfo[];
  rows: EligibilityRow[];
}

export interface PlanRecipient {
  name: string;
  email: string | null;
  status: "new" | "resend" | "already_sent" | "on_exam" | "no_email";
}

export interface CertificatePlan {
  kind: CertificateKind;
  label: string;
  exam_id: string;
  recipients: PlanRecipient[];
  will_send: number;
  already_sent: number;
  no_email: number;
  review_required: boolean;
}

export interface IssueResult {
  plans: CertificatePlan[];
  done: boolean;
  held_for_review: string[];
  message: string;
}

export const certificateKeys = {
  overview: (id: string) => ["our-internships", "certificates", id] as const,
  preview: (id: string, kinds: string) => ["our-internships", "certificates", id, "preview", kinds] as const,
};

const base = (id: string) => `/our-internships/${id}/certificates`;

export const certificatesApi = {
  /** The two certificates and who is eligible; creates the certificates the first time. */
  open: (id: string) => apiClient.post<CertificatesOverview>(`${base(id)}/open`).then((r) => r.data),
  setEligibility: (id: string, selectionIds: string[], kind: CertificateKind | null) =>
    apiClient.put<CertificatesOverview>(`${base(id)}/eligibility`, { selection_ids: selectionIds, kind }).then((r) => r.data),
  issue: (id: string, kinds: CertificateKind[], confirm: boolean) =>
    apiClient.post<IssueResult>(`${base(id)}/issue`, { kinds, confirm }).then((r) => r.data),
};
