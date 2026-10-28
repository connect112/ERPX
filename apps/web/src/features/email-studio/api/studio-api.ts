import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

export type SourceType = "visual" | "html" | "code";
export type LibrarySource = SourceType | "markdown" | "default";

export interface LibraryItem {
  id: string;
  key: string | null;
  name: string;
  description: string;
  category: string;
  creation_method: string;
  source_type: LibrarySource;
  module: string | null;
  status: "draft" | "published" | "archived" | "active";
  updated_at: string | null;
  updated_by_name: string | null;
  is_system: boolean;
  assigned_to: string[];
  customised: boolean;
  has_attachment: boolean;
  has_draft: boolean;
}

export interface EditorDoc {
  type: string;
  content?: unknown[];
  [key: string]: unknown;
}

export interface Attachment {
  kind: "recipient" | "shared";
  name?: string;
  required?: boolean;
  asset?: string;
}

export interface DraftConfig {
  auto_signature?: boolean;
  attachments?: Attachment[];
}

export interface DraftOut {
  version_id: string;
  version_number: number;
  state: "draft" | "published" | "superseded";
  subject: string;
  preheader: string;
  editor_json: EditorDoc | null;
  html_source: string | null;
  body_html: string;
  code_template_key: string | null;
  code_props: Record<string, string> | null;
  brand_profile_id: string | null;
  signature_id: string | null;
  config: DraftConfig;
  updated_at: string;
}

export interface Assignment {
  key: string;
  name: string;
  hackathon_id: string | null;
}

export interface TemplateOut {
  id: string;
  name: string;
  description: string;
  category: string;
  source_type: SourceType;
  module: string | null;
  status: "draft" | "published" | "archived";
  published_version_id: string | null;
  published_version_number: number | null;
  has_draft: boolean;
  current: DraftOut;
  assignments: Assignment[];
  updated_at: string;
  updated_by_name: string | null;
}

export interface VersionOut {
  id: string;
  version_number: number;
  state: "draft" | "published" | "superseded";
  subject: string;
  created_by_name: string | null;
  created_at: string;
  published_by_name: string | null;
  published_at: string | null;
  brand_profile_id: string | null;
  signature_id: string | null;
  source_type: SourceType;
}

/** What the editor sends to save, preview or test. */
export interface DraftPayload {
  name?: string;
  description?: string;
  category?: string;
  module?: string | null;
  subject: string;
  preheader: string;
  editor_json?: EditorDoc | null;
  html?: string | null;
  code_template_key?: string | null;
  code_props?: Record<string, string> | null;
  brand_profile_id: string | null;
  signature_id: string | null;
  config: DraftConfig;
}

export interface PreviewContext {
  type: "sample" | "internship";
  key?: string | null;
  internship_id?: string | null;
  student_id?: string | null;
}

export interface PreviewResult {
  subject: string;
  html: string;
  text: string;
  missing: string[];
  warnings: string[];
  unsupported: string[];
  attachments: Attachment[];
}

export interface Placeholder {
  name: string;
  group: string;
  description: string;
  sample: string;
}

export interface CodeProp {
  name: string;
  label: string;
  type: "text" | "textarea" | "url" | "color";
  default: string;
  required: boolean;
  description: string;
}

export interface CodeTemplate {
  key: string;
  name: string;
  description: string;
  category: string;
  module: string | null;
  suggested_for: string | null;
  subject: string;
  placeholders: string[];
  props: CodeProp[];
}

export interface Brand {
  id: string;
  name: string;
  company_name: string;
  logo_asset_id: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  background_color: string;
  text_color: string;
  website: string;
  contact_email: string;
  phone: string;
  address: string;
  tagline: string;
  social_links: { label: string; url: string }[];
  from_name: string;
  reply_to: string;
  is_default: boolean;
  logo_url: string | null;
  updated_at: string;
}
export type BrandPayload = Omit<Brand, "id" | "logo_url" | "updated_at">;

export interface Signature {
  id: string;
  name: string;
  scope: "company" | "individual";
  person_name: string;
  designation: string;
  company_name: string;
  email: string;
  phone: string;
  website: string;
  logo_asset_id: string | null;
  signature_asset_id: string | null;
  style: { color?: string; font_size?: number; align?: "left" | "center" | "right" };
  is_default: boolean;
  signature_image_url: string | null;
  logo_url: string | null;
  signature_approved: boolean;
  updated_at: string;
}
export type SignaturePayload = Omit<Signature, "id" | "signature_image_url" | "logo_url" | "signature_approved" | "updated_at">;

export type ComponentKind = "header" | "footer" | "button" | "announcement" | "info_card" | "internship_details" | "warning" | "contact";
export interface EmailComponent {
  id: string;
  name: string;
  kind: ComponentKind;
  description: string;
  html: string;
  updated_at: string;
}
export type ComponentPayload = Omit<EmailComponent, "id" | "updated_at">;

export interface Asset {
  id: string;
  token: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  url: string | null;
}

export interface HistoryItem {
  id: string;
  created_at: string;
  recipient: string;
  subject: string;
  key: string | null;
  module: string | null;
  template_id: string | null;
  template_name: string | null;
  version_number: number | null;
  source: string | null;
  status: "queued" | "sending" | "sent" | "delivered" | "failed" | "bounced";
  error: string | null;
  is_test: boolean;
  attachments: number;
}

export const studioKeys = {
  all: ["email-studio"] as const,
  library: ["email-studio", "library"] as const,
  template: (id: string) => ["email-studio", "template", id] as const,
  versions: (id: string) => ["email-studio", "versions", id] as const,
  placeholders: (key: string | null) => ["email-studio", "placeholders", key] as const,
  codeTemplates: ["email-studio", "code-templates"] as const,
  brands: ["email-studio", "brands"] as const,
  signatures: ["email-studio", "signatures"] as const,
  components: ["email-studio", "components"] as const,
  history: (params: string) => ["email-studio", "history", params] as const,
};

const base = "/email-studio";
const multipart = { headers: { "Content-Type": "multipart/form-data" } };

export const studioApi = {
  library: () => apiClient.get<LibraryItem[]>(`${base}/library`).then((r) => r.data),
  categories: () => apiClient.get<string[]>(`${base}/categories`).then((r) => r.data),
  placeholders: (key: string | null) => apiClient.get<Placeholder[]>(`${base}/placeholders`, { params: key ? { key } : {} }).then((r) => r.data),
  codeTemplates: () => apiClient.get<CodeTemplate[]>(`${base}/code-templates`).then((r) => r.data),

  create: (payload: DraftPayload & { name: string; source_type: SourceType; category: string }) =>
    apiClient.post<TemplateOut>(`${base}/templates`, payload).then((r) => r.data),
  get: (id: string) => apiClient.get<TemplateOut>(`${base}/templates/${id}`).then((r) => r.data),
  saveDraft: (id: string, payload: DraftPayload) => apiClient.put<TemplateOut>(`${base}/templates/${id}/draft`, payload).then((r) => r.data),
  discardDraft: (id: string) => apiClient.delete<TemplateOut>(`${base}/templates/${id}/draft`).then((r) => r.data),
  publish: (id: string) => apiClient.post<TemplateOut>(`${base}/templates/${id}/publish`).then((r) => r.data),
  remove: (id: string) => apiClient.delete<{ message: string }>(`${base}/templates/${id}`).then((r) => r.data),
  duplicate: (id: string) => apiClient.post<TemplateOut>(`${base}/templates/${id}/duplicate`).then((r) => r.data),
  archive: (id: string) => apiClient.post<TemplateOut>(`${base}/templates/${id}/archive`).then((r) => r.data),
  unarchive: (id: string) => apiClient.post<TemplateOut>(`${base}/templates/${id}/unarchive`).then((r) => r.data),
  versions: (id: string) => apiClient.get<VersionOut[]>(`${base}/templates/${id}/versions`).then((r) => r.data),
  version: (id: string, versionId: string) => apiClient.get<DraftOut>(`${base}/templates/${id}/versions/${versionId}`).then((r) => r.data),
  restore: (id: string, versionId: string) => apiClient.post<TemplateOut>(`${base}/templates/${id}/versions/${versionId}/restore`).then((r) => r.data),

  assign: (key: string, templateId: string, hackathonId?: string | null) =>
    apiClient.put<{ message: string }>(`${base}/assignments/${key}`, { template_id: templateId, hackathon_id: hackathonId ?? null }).then((r) => r.data),
  unassign: (key: string) => apiClient.delete<{ message: string }>(`${base}/assignments/${key}`).then((r) => r.data),

  preview: (source_type: SourceType, draft: DraftPayload, context: PreviewContext) =>
    apiClient.post<PreviewResult>(`${base}/preview`, { source_type, draft, context }).then((r) => r.data),
  test: (source_type: SourceType, draft: DraftPayload, context: PreviewContext, to_email: string, templateId?: string) =>
    apiClient
      .post<{ sent: boolean; message: string }>(`${base}/test`, { source_type, draft, context, to_email }, { params: templateId ? { template_id: templateId } : {} })
      .then((r) => r.data),

  brands: () => apiClient.get<Brand[]>(`${base}/brands`).then((r) => r.data),
  saveBrand: (payload: BrandPayload, id?: string) =>
    (id ? apiClient.put<Brand>(`${base}/brands/${id}`, payload) : apiClient.post<Brand>(`${base}/brands`, payload)).then((r) => r.data),
  deleteBrand: (id: string) => apiClient.delete(`${base}/brands/${id}`).then((r) => r.data),
  signatures: () => apiClient.get<Signature[]>(`${base}/signatures`).then((r) => r.data),
  saveSignature: (payload: SignaturePayload, id?: string) =>
    (id ? apiClient.put<Signature>(`${base}/signatures/${id}`, payload) : apiClient.post<Signature>(`${base}/signatures`, payload)).then((r) => r.data),
  approveSignature: (id: string, approve: boolean) => apiClient.post<Signature>(`${base}/signatures/${id}/approve`, { approve }).then((r) => r.data),
  deleteSignature: (id: string) => apiClient.delete(`${base}/signatures/${id}`).then((r) => r.data),
  components: () => apiClient.get<EmailComponent[]>(`${base}/components`).then((r) => r.data),
  saveComponent: (payload: ComponentPayload, id?: string) =>
    (id ? apiClient.put<EmailComponent>(`${base}/components/${id}`, payload) : apiClient.post<EmailComponent>(`${base}/components`, payload)).then((r) => r.data),
  deleteComponent: (id: string) => apiClient.delete(`${base}/components/${id}`).then((r) => r.data),
  uploadAsset: (file: File, purpose: "image" | "attachment" = "image") => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<Asset>(`${base}/assets`, form, { ...multipart, params: { purpose } }).then((r) => r.data);
  },

  history: (params: { status?: string; key?: string; q?: string; template_id?: string }) =>
    apiClient.get<HistoryItem[]>(`${base}/history`, { params }).then((r) => r.data),
};

export const useLibrary = () => useQuery({ queryKey: studioKeys.library, queryFn: studioApi.library });
export const useBrands = () => useQuery({ queryKey: studioKeys.brands, queryFn: studioApi.brands });
export const useSignatures = () => useQuery({ queryKey: studioKeys.signatures, queryFn: studioApi.signatures });
export const useComponents = () => useQuery({ queryKey: studioKeys.components, queryFn: studioApi.components });
export const useCodeTemplates = () => useQuery({ queryKey: studioKeys.codeTemplates, queryFn: studioApi.codeTemplates, staleTime: 5 * 60_000 });
export const usePlaceholders = (key: string | null) => useQuery({ queryKey: studioKeys.placeholders(key), queryFn: () => studioApi.placeholders(key), staleTime: 5 * 60_000 });
export const useTemplate = (id: string) => useQuery({ queryKey: studioKeys.template(id), queryFn: () => studioApi.get(id) });
