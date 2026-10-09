import { apiClient } from "@/api/client";

export type PostStatus =
  | "draft"
  | "review"
  | "approved"
  | "scheduled"
  | "publishing"
  | "published"
  | "failed"
  | "cancelled"
  | "publish_unknown";
export type PostFormat = "image" | "carousel" | "reel" | "story";
export type VerificationStatus = "not_required" | "unverified" | "verified" | "conflicting" | "outdated";

export interface Slide {
  heading: string;
  body: string;
  asset_key: string | null;
  alt_text: string;
}

export interface PostContent {
  hooks: string[];
  headline: string;
  caption: string;
  cta: string;
  hashtags: string[];
  alt_text: string;
  thumbnail_text: string;
  visual_direction: string;
  asset_key: string | null;
  slides: Slide[];
}

export interface Source {
  url: string;
  title: string;
  published_at: string | null;
  retrieved_at: string | null;
}

export interface PostWarning {
  severity: "info" | "warning" | "blocking";
  message: string;
  code?: string | null;
}

export interface Generation {
  model?: string;
  research_items?: string[];
  hashtag_basis?: string;
  suggested_time?: { at: string; timezone: string; basis: string; evidence: string };
  last_check?: {
    checked_at: string;
    cves: Record<string, { checked: boolean; found?: boolean; cvss?: number | null; severity?: string | null; kev?: boolean; status?: string | null }>;
  };
  claims?: string[];
}

export interface Post {
  id: string;
  title: string;
  format: PostFormat;
  pillar: string | null;
  objective: string | null;
  campaign_id: string | null;
  status: PostStatus;
  content: PostContent;
  sources: Source[];
  warnings: PostWarning[];
  verification_status: VerificationStatus;
  high_risk: boolean;
  time_sensitive: boolean;
  scheduled_at: string | null;
  approved_by_user_id: string | null;
  approved_at: string | null;
  published_at: string | null;
  external_permalink: string | null;
  attempt_count: number;
  last_error: string | null;
  duplicate_of_id: string | null;
  generation: Generation;
  created_at: string;
  updated_at: string;
  approval_withdrawn: boolean;
}

export interface PostListResponse {
  items: Post[];
  total: number;
}

export interface PostPayload {
  title?: string;
  format?: PostFormat;
  pillar?: string | null;
  objective?: string | null;
  content?: Partial<PostContent>;
  sources?: Partial<Source>[];
  verification_status?: VerificationStatus;
  high_risk?: boolean;
  time_sensitive?: boolean;
  scheduled_at?: string | null;
  clear_schedule?: boolean;
}

export type TransitionAction = "submit" | "request_changes" | "approve" | "unapprove" | "cancel" | "reopen";

export interface Pillar {
  key: string;
  label: string;
  description: string;
  share: number;
  enabled: boolean;
}

export interface Persona {
  key: string;
  label: string;
  description: string;
}

export interface Brand {
  name: string;
  tagline: string;
  handle: string;
  website: string;
  voice: string;
  colors: { background: string; ink: string; primary: string; accent: string; muted: string };
  colors_confirmed: boolean;
  fonts: { heading: string; body: string };
  logo_key: string | null;
}

export interface DesignRules {
  max_headline_words: number;
  max_fonts: number;
  max_cover_text_chars: number;
  min_contrast_ratio: number;
  one_focal_point: boolean;
  logo_exact_only: boolean;
  forbidden_visuals: string[];
  prefer: string[];
}

export interface SocialSettings {
  timezone: string;
  publish_mode: "manual" | "scheduled";
  brand: Brand;
  pillars: Pillar[];
  personas: Persona[];
  prohibited_claims: string[];
  objectives: string[];
  design_rules: DesignRules;
  budgets: { monthly_budget_inr: number; alert_at_percent: number };
  notifications: { emails: string[]; notify_on_failure: boolean; notify_on_token_expiry: boolean };
  retention_days: number;
}

export type SettingsUpdate = Partial<SocialSettings>;

export interface Capability {
  key: string;
  label: string;
  api: "supported" | "needs_app_review" | "restricted" | "unavailable";
  implemented: string;
  verified_live: boolean;
  note: string;
}

export interface IntegrationOverview {
  account: {
    id: string;
    platform: string;
    username: string | null;
    account_type: string | null;
    status: string;
    scopes: string[];
    token_expires_at: string | null;
    connected_at: string | null;
    last_synced_at: string | null;
    last_error: string | null;
  } | null;
  connected: boolean;
  capabilities: Capability[];
  setup_steps: string[];
}

export interface BriefingItem {
  level: "action" | "warning" | "info";
  message: string;
  link: string | null;
}

export interface Overview {
  briefing: BriefingItem[];
  post_counts: Record<string, number>;
  awaiting_approval: Post[];
  leads: { last_30_days: number; by_status: Record<string, number>; note: string };
  connected: boolean;
  roadmap: { phase: number; title: string; status: "done" | "next" | "planned" }[];
}

export interface ResearchItem {
  id: string;
  source: "cisa_kev" | "cisa_advisory" | "nvd";
  external_id: string;
  url: string;
  title: string;
  summary: string | null;
  published_at: string | null;
  retrieved_at: string;
  severity: string | null;
  cve_ids: string[];
  facts: Record<string, unknown>;
  flags: string[];
  status: "new" | "used" | "dismissed";
}

export interface ResearchList {
  items: ResearchItem[];
  total: number;
  sources: Record<string, { label: string; last_fetch_at?: string; ok?: boolean; error?: string | null; count?: number }>;
}

export interface RefreshResult {
  source: string;
  label: string;
  skipped: boolean;
  ok: boolean;
  new: number;
  count: number;
  error: string | null;
}

export interface GeneratePayload {
  topic: string;
  format: PostFormat;
  pillar?: string | null;
  persona_key?: string | null;
  research_item_ids: string[];
  notes?: string;
  time_sensitive?: boolean;
}

export type RewriteElement = "hooks" | "headline" | "caption" | "cta" | "hashtags" | "thumbnail_text" | "visual_direction" | "alt_text";

export interface HistoryOverview {
  pillars: { key: string; label: string; target: number; actual: number; recent: number }[];
  posts_considered: number;
  suggestions: string[];
}

export interface UsageOverview {
  month_start: string;
  spent_inr: number;
  budget_inr: number;
  alert_at_percent: number;
  over_budget: boolean;
  over_alert: boolean;
  calls: number;
  by_kind: Record<string, { calls: number; est_cost_inr: number }>;
  is_estimate: boolean;
  note: string;
  ai_configured: boolean;
}

export const socialMediaApi = {
  overview: () => apiClient.get<Overview>("/social-media/overview").then((r) => r.data),
  settings: () => apiClient.get<SocialSettings>("/social-media/settings").then((r) => r.data),
  updateSettings: (payload: SettingsUpdate) =>
    apiClient.put<SocialSettings>("/social-media/settings", payload).then((r) => r.data),
  integration: () => apiClient.get<IntegrationOverview>("/social-media/integration").then((r) => r.data),
  listPosts: (params: { status?: string; pillar?: string; q?: string; skip?: number; limit?: number }) =>
    apiClient.get<PostListResponse>("/social-media/posts", { params }).then((r) => r.data),
  createPost: (payload: PostPayload) => apiClient.post<Post>("/social-media/posts", payload).then((r) => r.data),
  updatePost: (id: string, payload: PostPayload) =>
    apiClient.patch<Post>(`/social-media/posts/${id}`, payload).then((r) => r.data),
  deletePost: (id: string) => apiClient.delete(`/social-media/posts/${id}`).then(() => undefined),
  duplicatePost: (id: string) => apiClient.post<Post>(`/social-media/posts/${id}/duplicate`).then((r) => r.data),
  transitionPost: (
    id: string,
    payload: { action: TransitionAction; acknowledge_warnings?: boolean; acknowledge_high_risk?: boolean },
  ) => apiClient.post<Post>(`/social-media/posts/${id}/transition`, payload).then((r) => r.data),
  research: (params: { source?: string; status?: string; q?: string; skip?: number; limit?: number }) =>
    apiClient.get<ResearchList>("/social-media/research", { params }).then((r) => r.data),
  refreshResearch: (force: boolean) =>
    apiClient.post<RefreshResult[]>("/social-media/research/refresh", null, { params: { force } }).then((r) => r.data),
  lookUpCve: (cve: string) => apiClient.post<ResearchItem>("/social-media/research/cve", { cve }).then((r) => r.data),
  dismissResearch: (id: string) => apiClient.post(`/social-media/research/${id}/dismiss`).then(() => undefined),
  generate: (payload: GeneratePayload) =>
    apiClient.post<Post>("/social-media/studio/generate", payload, { timeout: 120000 }).then((r) => r.data),
  rewrite: (id: string, element: RewriteElement, instruction: string) =>
    apiClient.post<Post>(`/social-media/posts/${id}/regenerate`, { element, instruction }, { timeout: 120000 }).then((r) => r.data),
  checkPost: (id: string) => apiClient.post<Post>(`/social-media/posts/${id}/check`, null, { timeout: 60000 }).then((r) => r.data),
  history: () => apiClient.get<HistoryOverview>("/social-media/history").then((r) => r.data),
  usage: () => apiClient.get<UsageOverview>("/social-media/usage").then((r) => r.data),
};
