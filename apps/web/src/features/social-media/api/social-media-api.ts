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
  next_attempt_at: string | null;
  external_media_id: string | null;
  design: Design;
  artwork: Artwork;
  created_at: string;
  updated_at: string;
  approval_withdrawn: boolean;
}

export type Template = "editorial" | "statement" | "photo" | "screenshot";

export interface Design {
  template?: Template;
  background_asset_id?: string | null;
  kicker?: string | null;
  headline?: string | null;
  subline?: string | null;
  credit?: string | null;
  show_logo?: boolean;
  show_handle?: boolean;
}

export interface ArtworkValidation {
  ok: boolean;
  problems: string[];
  notes: string[];
  min_font_px: number | null;
  min_contrast: number | null;
  blocks: { role: string; size_px: number; contrast: number }[];
}

export interface ArtworkFile {
  key: string;
  slide: number;
  width: number;
  height: number;
  sha256: string;
  url?: string | null;
  metrics: { template: string; dominant: string; luminance: number; dhash: string; text_chars: number; headline: string; headline_px: number | null; logo: string | null };
  validation: ArtworkValidation;
}

export interface Artwork {
  template?: Template;
  rendered_at?: string;
  ok?: boolean;
  files?: ArtworkFile[];
  synthetic_background?: boolean;
  background?: { asset_id: string; kind: string; synthetic: boolean } | null;
  proofread?: { ok: boolean; issues: { text: string; suggestion: string }[]; at: string; fingerprint: string };
}

export interface Asset {
  id: string;
  kind: "logo" | "photo" | "screenshot" | "background";
  filename: string;
  content_type: string;
  width: number;
  height: number;
  bytes_size: number;
  alt_text: string;
  synthetic: boolean;
  created_at: string;
  url: string | null;
  is_logo: boolean;
}

export interface GridTile {
  post_id: string;
  title: string;
  status: PostStatus;
  format: PostFormat;
  slides: number;
  url: string | null;
  metrics: ArtworkFile["metrics"];
  synthetic_background: boolean;
  is_focus: boolean;
}

export interface GridFinding {
  severity: "info" | "warning";
  code: string;
  message: string;
  tiles: number[];
}

export interface GridResult {
  tiles: GridTile[];
  findings: GridFinding[];
  verdict: "balanced" | "review" | "not_enough";
  live_available: boolean;
  missing: number;
  note: string;
}

export interface Attempt {
  id: string;
  attempt_no: number;
  status: "started" | "retry" | "published" | "failed" | "unknown" | "paused";
  created_at: string;
  finished_at: string | null;
  publish_started_at: string | null;
  media_id: string | null;
  error_kind: string | null;
  error: string | null;
  http_status: number | null;
  caption: string;
}

export interface Readiness {
  ready: boolean;
  problems: string[];
  caption: string;
  caption_length: number;
  caption_limit: number;
  publish_mode: "manual" | "scheduled";
  timezone: string;
  account_connected: boolean;
  note: string;
}

export interface QueueItem {
  post: Post;
  last_attempt: Attempt | null;
}

export interface QueueResult {
  items: QueueItem[];
  timezone: string;
  worker_note: string;
}

export interface CalendarItem {
  id: string;
  title: string;
  status: PostStatus;
  format: PostFormat;
  pillar: string | null;
  scheduled_at: string;
  local_date: string;
  local_time: string;
  thumbnail: string | null;
  time_sensitive: boolean;
  high_risk: boolean;
}

export interface CalendarResult {
  start: string;
  end: string;
  timezone: string;
  publish_mode: "manual" | "scheduled";
  items: CalendarItem[];
  ready_to_schedule: CalendarItem[];
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
  live_check: "passed" | "needs_app_review" | "failed" | "not_run";
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
    token_days_left: number | null;
  } | null;
  connected: boolean;
  capabilities: Capability[];
  setup_steps: string[];
  app_configured: boolean;
  redirect_uri: string;
  webhook_url: string;
  webhook_verify_token_set: boolean;
  scopes_requested: string[];
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
  image_configured: boolean;
}

// ---------------- comments and direct messages ----------------

export interface Triage {
  category: "enquiry" | "complaint" | "question" | "thanks" | "spam" | "other";
  priority: "high" | "medium" | "low";
  needs_care: boolean;
  care_reason: string | null;
}

export interface AiSuggestion {
  summary: string | null;
  reply: string | null;
  note: string | null;
  at: string | null;
}

export type ReplyStatus = "pending" | "sent" | "failed" | "unknown";

export interface ReplyLine {
  id: string;
  text: string;
  at: string | null;
  by: "erpx" | "instagram";
  status: string;
  sent_by: string | null;
}

export interface ReplyRecord {
  id: string;
  kind: "comment" | "dm";
  message: string;
  source: "typed" | "suggestion_edited" | "suggestion_unchanged";
  status: ReplyStatus;
  error: string | null;
  external_reply_id: string | null;
  attempted_at: string | null;
  finished_at: string | null;
  created_at: string;
  comment_id: string | null;
  conversation_id: string | null;
  acknowledged_sensitive: boolean;
  sent_by: string | null;
}

export interface MediaRef {
  external_id: string;
  caption: string | null;
  permalink: string | null;
  thumbnail_url: string | null;
  artwork_url: string | null;
  post_id: string | null;
}

export interface InboxComment {
  id: string;
  text: string;
  author_username: string | null;
  author_known: boolean;
  posted_at: string | null;
  status: "new" | "answered" | "ignored";
  triage: Triage;
  suggestion: AiSuggestion;
  media: MediaRef | null;
  replies: ReplyLine[];
}

export interface InboxMessage {
  id: string;
  direction: "in" | "out";
  text: string | null;
  sent_at: string | null;
}

export interface Conversation {
  id: string;
  participant_username: string | null;
  participant_known: boolean;
  last_message_at: string | null;
  last_user_message_at: string | null;
  window_expires_at: string | null;
  window_open: boolean;
  status: "open" | "answered" | "ignored";
  triage: Triage;
  suggestion: AiSuggestion;
  preview: string | null;
}

export interface Thread {
  conversation: Conversation;
  messages: InboxMessage[];
  replies: ReplyLine[];
}

export interface InboxSummary {
  connected: boolean;
  can_read_comments: boolean;
  can_read_messages: boolean;
  counts: Record<string, number>;
  last_sync_at: string | null;
  stages: Record<string, { ok?: boolean; error?: string | null; note?: string | null; count?: number }>;
  note: string;
}

export interface ReplyPayload {
  message: string;
  request_id: string;
  from_suggestion: boolean;
  acknowledge_sensitive: boolean;
}

export type CommentView = "unanswered" | "recent" | "enquiries" | "complaints" | "spam" | "all";
export type ConversationView = "needs_reply" | "enquiries" | "complaints" | "high_priority" | "all";

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
  assets: (kind?: string) => apiClient.get<Asset[]>("/social-media/assets", { params: { kind } }).then((r) => r.data),
  uploadAsset: (file: File, kind: string, altText: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    form.append("alt_text", altText);
    // Naming multipart lets the browser add the boundary (the client's default is JSON).
    return apiClient
      .post<Asset>("/social-media/assets", form, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },
  deleteAsset: (id: string) => apiClient.delete(`/social-media/assets/${id}`).then(() => undefined),
  useAsLogo: (id: string) => apiClient.post<Asset>(`/social-media/assets/${id}/use-as-logo`).then((r) => r.data),
  setDesign: (id: string, design: Design) => apiClient.put<Post>(`/social-media/posts/${id}/design`, design).then((r) => r.data),
  render: (id: string) => apiClient.post<Post>(`/social-media/posts/${id}/render`, null, { timeout: 60000 }).then((r) => r.data),
  removeArtwork: (id: string) => apiClient.delete<Post>(`/social-media/posts/${id}/artwork`).then((r) => r.data),
  newBackground: (id: string, direction: string) =>
    apiClient.post<Post>(`/social-media/posts/${id}/background`, { direction }, { timeout: 180000 }).then((r) => r.data),
  proofread: (id: string) =>
    apiClient
      .post<{ ok: boolean; issues: { text: string; suggestion: string }[]; current: boolean }>(`/social-media/posts/${id}/proofread`, null, { timeout: 120000 })
      .then((r) => r.data),
  grid: (postId?: string) => apiClient.get<GridResult>("/social-media/grid", { params: { post_id: postId } }).then((r) => r.data),
  getPost: (id: string) => apiClient.get<Post>(`/social-media/posts/${id}`).then((r) => r.data),
  readiness: (id: string) => apiClient.get<Readiness>(`/social-media/posts/${id}/readiness`).then((r) => r.data),
  schedule: (id: string, scheduledAt: string) =>
    apiClient.post<Post>(`/social-media/posts/${id}/schedule`, { scheduled_at: scheduledAt }).then((r) => r.data),
  unschedule: (id: string) => apiClient.post<Post>(`/social-media/posts/${id}/unschedule`).then((r) => r.data),
  publishNow: (id: string) => apiClient.post<Post>(`/social-media/posts/${id}/publish-now`).then((r) => r.data),
  retry: (id: string) => apiClient.post<Post>(`/social-media/posts/${id}/retry`).then((r) => r.data),
  reconcile: (id: string) =>
    apiClient
      .post<{ outcome: "published" | "not_published" | "unknown"; note: string; post: Post }>(`/social-media/posts/${id}/reconcile`, null, { timeout: 60000 })
      .then((r) => r.data),
  resolve: (id: string, payload: { published: boolean; media_id?: string; permalink?: string }) =>
    apiClient.post<Post>(`/social-media/posts/${id}/resolve`, payload).then((r) => r.data),
  attempts: (id: string) => apiClient.get<Attempt[]>(`/social-media/posts/${id}/attempts`).then((r) => r.data),
  queue: () => apiClient.get<QueueResult>("/social-media/queue").then((r) => r.data),
  calendar: (start: string, end: string) =>
    apiClient.get<CalendarResult>("/social-media/calendar", { params: { start, end } }).then((r) => r.data),
  startConnect: () => apiClient.post<{ url: string }>("/social-media/connect/start").then((r) => r.data),
  disconnect: () => apiClient.post<{ message: string }>("/social-media/connect/disconnect").then((r) => r.data),
  recheck: () => apiClient.post<{ capabilities: Record<string, string> }>("/social-media/connect/recheck", null, { timeout: 60000 }).then((r) => r.data),
  refreshToken: () => apiClient.post<{ message: string }>("/social-media/connect/refresh-token", null, { timeout: 60000 }).then((r) => r.data),
  history: () => apiClient.get<HistoryOverview>("/social-media/history").then((r) => r.data),
  usage: () => apiClient.get<UsageOverview>("/social-media/usage").then((r) => r.data),
  inboxSummary: () => apiClient.get<InboxSummary>("/social-media/inbox/summary").then((r) => r.data),
  syncInbox: () =>
    apiClient.post<{ skipped: boolean; message: string | null; stages: InboxSummary["stages"] }>("/social-media/inbox/sync", null, { timeout: 120000 }).then((r) => r.data),
  comments: (params: { view: CommentView; q?: string; skip?: number; limit?: number }) =>
    apiClient.get<{ items: InboxComment[]; total: number }>("/social-media/comments", { params }).then((r) => r.data),
  suggestForComment: (id: string) =>
    apiClient.post<InboxComment>(`/social-media/comments/${id}/suggest`, null, { timeout: 120000 }).then((r) => r.data),
  replyToComment: (id: string, payload: ReplyPayload) =>
    apiClient.post<ReplyRecord>(`/social-media/comments/${id}/reply`, payload, { timeout: 60000 }).then((r) => r.data),
  markComment: (id: string, action: "ignore" | "reopen") => apiClient.post<InboxComment>(`/social-media/comments/${id}/handled`, { action }).then((r) => r.data),
  conversations: (params: { view: ConversationView; q?: string; skip?: number; limit?: number }) =>
    apiClient.get<{ items: Conversation[]; total: number }>("/social-media/conversations", { params }).then((r) => r.data),
  thread: (id: string) => apiClient.get<Thread>(`/social-media/conversations/${id}`).then((r) => r.data),
  suggestForConversation: (id: string) =>
    apiClient.post<Conversation>(`/social-media/conversations/${id}/suggest`, null, { timeout: 120000 }).then((r) => r.data),
  replyToConversation: (id: string, payload: ReplyPayload) =>
    apiClient.post<ReplyRecord>(`/social-media/conversations/${id}/reply`, payload, { timeout: 60000 }).then((r) => r.data),
  markConversation: (id: string, action: "ignore" | "reopen") =>
    apiClient.post<Conversation>(`/social-media/conversations/${id}/handled`, { action }).then((r) => r.data),
  replyHistory: () => apiClient.get<ReplyRecord[]>("/social-media/replies").then((r) => r.data),
  reconcileReply: (id: string) =>
    apiClient.post<{ note: string; reply: ReplyRecord }>(`/social-media/replies/${id}/reconcile`, null, { timeout: 60000 }).then((r) => r.data),
  resolveReply: (id: string, sent: boolean) => apiClient.post<ReplyRecord>(`/social-media/replies/${id}/resolve`, { sent }).then((r) => r.data),
};
