import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

const base = "/pentrix-ops/marketing";

/** Who is chosen: candidates picked one by one, or everyone matching the Registrations filters (less any taken out). */
export type Selection =
  | { mode: "ids"; ids: string[] }
  | { mode: "filter"; filters: SelectionFilters; exclude_ids: string[] };

export interface SelectionFilters {
  q?: string | null;
  assessment: string[];
  qualification: string[];
  booking: string[];
  payment: string[];
  marketing: string[];
  registered_from?: string | null;
  registered_to?: string | null;
}

export interface MarketingTemplate {
  id: string;
  template_id: string;
  name: string;
  campaign_name: string;
  category: string;
  available_from: string | null;
  available_until: string | null;
  enabled: boolean;
  published: boolean;
  usable: boolean;
  problem: string | null;
  subject: string;
  source_type: string;
  last_updated: string | null;
}

export interface AssignableTemplate {
  template_id: string;
  name: string;
  category: string;
  subject: string;
  source_type: string;
}

export interface Option {
  id: string;
  name: string;
  is_default: boolean;
}

export interface Options {
  brands: Option[];
  signatures: Option[];
}

export interface Person {
  id: string;
  name: string;
  email: string;
}

export interface RecipientsPreview {
  selected: number;
  eligible: number;
  excluded: { reason: string; label: string; count: number }[];
  people: Person[];
  people_shown: number;
}

export interface EmailPreview {
  assignment_id: string;
  campaign_name: string;
  template_name: string;
  subject: string;
  html: string;
  text: string;
  brand: string | null;
  brand_profile_id: string | null;
  signature: string | null;
  signature_id: string | null;
  attachments: { name: string; size_bytes: number }[];
  missing: string[];
  warnings: string[];
  candidate: { id: string; name: string; email: string } | null;
  sample: boolean;
  recipients: RecipientsPreview | null;
}

export interface Campaign {
  id: string;
  campaign_name: string;
  subject: string;
  status: "sending" | "completed" | "cancelled";
  recipient_count: number;
  counts: Record<string, number>;
  excluded: Record<string, number>;
  confirmed_at: string;
  completed_at: string | null;
  template_id: string | null;
}

export interface CampaignPage {
  items: Campaign[];
  total: number;
  page: number;
  page_size: number;
}

export interface CampaignRecipient {
  id: string;
  name: string;
  email: string;
  status: string;
  error: string | null;
  attempts: number;
  sent_at: string | null;
}

export interface RecipientPage {
  items: CampaignRecipient[];
  total: number;
  page: number;
  page_size: number;
}

export const marketingKeys = {
  templates: (usable: boolean, on: string, category: string, q: string) => ["pentrix-ops", "marketing", "templates", usable, on, category, q] as const,
  assignable: ["pentrix-ops", "marketing", "assignable"] as const,
  options: ["pentrix-ops", "marketing", "options"] as const,
  campaigns: (page: number) => ["pentrix-ops", "marketing", "campaigns", page] as const,
  campaign: (id: string) => ["pentrix-ops", "marketing", "campaign", id] as const,
  recipients: (id: string, status: string, page: number) => ["pentrix-ops", "marketing", "recipients", id, status, page] as const,
};

export const marketingApi = {
  templates: (opts: { usable?: boolean; on?: string; category?: string; q?: string } = {}) =>
    apiClient
      .get<MarketingTemplate[]>(`${base}/templates`, { params: { usable: opts.usable || undefined, on: opts.on || undefined, category: opts.category || undefined, q: opts.q || undefined } })
      .then((r) => r.data),
  assignable: () => apiClient.get<AssignableTemplate[]>(`${base}/templates/assignable`).then((r) => r.data),
  assign: (body: { template_id: string; campaign_name: string; available_from: string | null; available_until: string | null }) =>
    apiClient.post<MarketingTemplate>(`${base}/templates`, body).then((r) => r.data),
  update: (id: string, body: Partial<{ campaign_name: string; available_from: string | null; available_until: string | null; enabled: boolean }>) =>
    apiClient.patch<MarketingTemplate>(`${base}/templates/${id}`, body).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`${base}/templates/${id}`).then((r) => r.data),
  options: () => apiClient.get<Options>(`${base}/options`).then((r) => r.data),
  previewRecipients: (selection: Selection, assignmentId?: string) =>
    apiClient.post<RecipientsPreview>(`${base}/recipients/preview`, { selection, assignment_id: assignmentId ?? null }).then((r) => r.data),
  previewEmail: (body: { assignment_id: string; selection?: Selection; candidate_id?: string | null; brand_profile_id?: string | null; signature_id?: string | null }) =>
    apiClient.post<EmailPreview>(`${base}/preview`, body).then((r) => r.data),
  send: (body: { assignment_id: string; selection: Selection; brand_profile_id: string | null; signature_id: string | null; expected_count: number; idempotency_key: string }) =>
    apiClient.post<Campaign>(`${base}/campaigns`, { ...body, confirm: true }).then((r) => r.data),
  campaigns: (page: number) => apiClient.get<CampaignPage>(`${base}/campaigns`, { params: { page, page_size: 20 } }).then((r) => r.data),
  campaign: (id: string) => apiClient.get<Campaign>(`${base}/campaigns/${id}`).then((r) => r.data),
  recipients: (id: string, status: string, page: number) =>
    apiClient.get<RecipientPage>(`${base}/campaigns/${id}/recipients`, { params: { status: status || undefined, page, page_size: 50 } }).then((r) => r.data),
  cancel: (id: string) => apiClient.post<Campaign>(`${base}/campaigns/${id}/cancel`).then((r) => r.data),
};

export const useMarketingTemplates = (opts: { usable?: boolean; on?: string; category?: string; q?: string } = {}, enabled = true) =>
  useQuery({ queryKey: marketingKeys.templates(!!opts.usable, opts.on ?? "", opts.category ?? "", opts.q ?? ""), queryFn: () => marketingApi.templates(opts), enabled });
export const useAssignableTemplates = (enabled: boolean) => useQuery({ queryKey: marketingKeys.assignable, queryFn: marketingApi.assignable, enabled });
export const useMarketingOptions = (enabled: boolean) => useQuery({ queryKey: marketingKeys.options, queryFn: marketingApi.options, enabled });
export const useCampaigns = (page: number) => useQuery({ queryKey: marketingKeys.campaigns(page), queryFn: () => marketingApi.campaigns(page), refetchInterval: 15_000 });
export const useCampaign = (id: string | null) => useQuery({ queryKey: marketingKeys.campaign(id ?? ""), queryFn: () => marketingApi.campaign(id as string), enabled: !!id, refetchInterval: 10_000 });
export const useCampaignRecipients = (id: string | null, status: string, page: number) =>
  useQuery({ queryKey: marketingKeys.recipients(id ?? "", status, page), queryFn: () => marketingApi.recipients(id as string, status, page), enabled: !!id, refetchInterval: 15_000 });

/** The Registrations filters as the marketing API wants them (lists, and dates as whole days in India). */
export function selectionFilters(f: {
  q: string; assessment: string; qualification: string; booking: string; payment: string; marketing: string; registered_from: string; registered_to: string;
}): SelectionFilters {
  const list = (v: string) => (v ? [v] : []);
  return {
    q: f.q || null,
    assessment: list(f.assessment),
    qualification: list(f.qualification),
    booking: list(f.booking),
    payment: list(f.payment),
    marketing: list(f.marketing),
    registered_from: f.registered_from ? new Date(`${f.registered_from}T00:00:00+05:30`).toISOString() : null,
    registered_to: f.registered_to ? new Date(new Date(`${f.registered_to}T00:00:00+05:30`).getTime() + 86_400_000).toISOString() : null,
  };
}

/** A fresh key for one confirmation, so a double click or a retry cannot send twice. */
export function newSendKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
