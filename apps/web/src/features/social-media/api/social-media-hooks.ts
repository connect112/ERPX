import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  socialMediaApi,
  type CommentView,
  type Conversation,
  type ConversationView,
  type ExperimentPayload,
  type LeadPayload,
  type LinkPayload,
  type InboxComment,
  type ReplyPayload,
  type Design,
  type GeneratePayload,
  type PostPayload,
  type RewriteElement,
  type SettingsUpdate,
  type TransitionAction,
} from "@/features/social-media/api/social-media-api";

export const socialKeys = {
  all: ["social-media"] as const,
  overview: ["social-media", "overview"] as const,
  settings: ["social-media", "settings"] as const,
  integration: ["social-media", "integration"] as const,
  posts: (params: object) => ["social-media", "posts", params] as const,
};

export function useOverview() {
  return useQuery({ queryKey: socialKeys.overview, queryFn: socialMediaApi.overview });
}

export function useSocialSettings() {
  return useQuery({ queryKey: socialKeys.settings, queryFn: socialMediaApi.settings });
}

export function useUpdateSocialSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SettingsUpdate) => socialMediaApi.updateSettings(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: socialKeys.all }),
  });
}

export function useIntegration() {
  return useQuery({ queryKey: socialKeys.integration, queryFn: socialMediaApi.integration });
}

export function usePosts(params: { status?: string; pillar?: string; q?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: socialKeys.posts(params),
    queryFn: () => socialMediaApi.listPosts(params),
    placeholderData: keepPreviousData,
  });
}

function usePostMutation<TVariables, TResult>(fn: (variables: TVariables) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSettled: () => queryClient.invalidateQueries({ queryKey: socialKeys.all }),
  });
}

export function useCreatePost() {
  return usePostMutation((payload: PostPayload) => socialMediaApi.createPost(payload));
}

export function useUpdatePost() {
  return usePostMutation(({ id, payload }: { id: string; payload: PostPayload }) =>
    socialMediaApi.updatePost(id, payload),
  );
}

export function useDeletePost() {
  return usePostMutation((id: string) => socialMediaApi.deletePost(id));
}

export function useDuplicatePost() {
  return usePostMutation((id: string) => socialMediaApi.duplicatePost(id));
}

export function useTransitionPost() {
  return usePostMutation(
    (v: { id: string; action: TransitionAction; acknowledge_warnings?: boolean; acknowledge_high_risk?: boolean }) =>
      socialMediaApi.transitionPost(v.id, {
        action: v.action,
        acknowledge_warnings: v.acknowledge_warnings,
        acknowledge_high_risk: v.acknowledge_high_risk,
      }),
  );
}

export function useResearch(params: { source?: string; status?: string; q?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ["social-media", "research", params],
    queryFn: () => socialMediaApi.research(params),
    placeholderData: keepPreviousData,
  });
}

export function useRefreshResearch() {
  return usePostMutation((force: boolean) => socialMediaApi.refreshResearch(force));
}

export function useLookUpCve() {
  return usePostMutation((cve: string) => socialMediaApi.lookUpCve(cve));
}

export function useDismissResearch() {
  return usePostMutation((id: string) => socialMediaApi.dismissResearch(id));
}

export function useGenerate() {
  return usePostMutation((payload: GeneratePayload) => socialMediaApi.generate(payload));
}

export function useRewrite() {
  return usePostMutation((v: { id: string; element: RewriteElement; instruction: string }) =>
    socialMediaApi.rewrite(v.id, v.element, v.instruction),
  );
}

export function useCheckPost() {
  return usePostMutation((id: string) => socialMediaApi.checkPost(id));
}

export function useHistory() {
  return useQuery({ queryKey: ["social-media", "history"], queryFn: socialMediaApi.history });
}

export function useUsage() {
  return useQuery({ queryKey: ["social-media", "usage"], queryFn: socialMediaApi.usage });
}

export function useAssets(kind?: string) {
  return useQuery({ queryKey: ["social-media", "assets", kind ?? "all"], queryFn: () => socialMediaApi.assets(kind) });
}

export function useUploadAsset() {
  return usePostMutation((v: { file: File; kind: string; altText: string }) => socialMediaApi.uploadAsset(v.file, v.kind, v.altText));
}

export function useDeleteAsset() {
  return usePostMutation((id: string) => socialMediaApi.deleteAsset(id));
}

export function useUseAsLogo() {
  return usePostMutation((id: string) => socialMediaApi.useAsLogo(id));
}

export function useSaveAndDraw() {
  // Saves the design, then draws it: one action for the person, two steps on the server.
  return usePostMutation(async (v: { id: string; design: Design }) => {
    await socialMediaApi.setDesign(v.id, v.design);
    return socialMediaApi.render(v.id);
  });
}

export function useRemoveArtwork() {
  return usePostMutation((id: string) => socialMediaApi.removeArtwork(id));
}

export function useNewBackground() {
  // Saves the design first (the template must be Photo on the server), then makes the new picture and redraws.
  return usePostMutation(async (v: { id: string; design: Design; direction: string }) => {
    await socialMediaApi.setDesign(v.id, v.design);
    return socialMediaApi.newBackground(v.id, v.direction);
  });
}

export function useProofread() {
  return usePostMutation((id: string) => socialMediaApi.proofread(id));
}

export function useGrid(postId?: string, enabled = true) {
  return useQuery({ queryKey: ["social-media", "grid", postId ?? "all"], queryFn: () => socialMediaApi.grid(postId), enabled });
}

export function usePost(id: string | null) {
  return useQuery({ queryKey: ["social-media", "post", id], queryFn: () => socialMediaApi.getPost(id as string), enabled: id !== null });
}

export function useReadiness(id: string | null) {
  return useQuery({ queryKey: ["social-media", "readiness", id], queryFn: () => socialMediaApi.readiness(id as string), enabled: id !== null });
}

export function useSchedule() {
  return usePostMutation((v: { id: string; scheduledAt: string }) => socialMediaApi.schedule(v.id, v.scheduledAt));
}

export function useUnschedule() {
  return usePostMutation((id: string) => socialMediaApi.unschedule(id));
}

export function usePublishNow() {
  return usePostMutation((id: string) => socialMediaApi.publishNow(id));
}

export function useRetry() {
  return usePostMutation((id: string) => socialMediaApi.retry(id));
}

export function useReconcile() {
  return usePostMutation((id: string) => socialMediaApi.reconcile(id));
}

export function useResolve() {
  return usePostMutation((v: { id: string; published: boolean; mediaId?: string; permalink?: string }) =>
    socialMediaApi.resolve(v.id, { published: v.published, media_id: v.mediaId || undefined, permalink: v.permalink || undefined }),
  );
}

export function useAttempts(id: string | null) {
  return useQuery({ queryKey: ["social-media", "attempts", id], queryFn: () => socialMediaApi.attempts(id as string), enabled: id !== null });
}

export function useQueue() {
  // A post can change state while the page is open (the worker runs every minute), so look again now and then.
  return useQuery({ queryKey: ["social-media", "queue"], queryFn: socialMediaApi.queue, refetchInterval: 30000 });
}

export function useCalendar(start: string, end: string) {
  return useQuery({
    queryKey: ["social-media", "calendar", start, end],
    queryFn: () => socialMediaApi.calendar(start, end),
    placeholderData: keepPreviousData,
  });
}

export function useStartConnect() {
  return usePostMutation(() => socialMediaApi.startConnect());
}

export function useDisconnect() {
  return usePostMutation(() => socialMediaApi.disconnect());
}

export function useRecheck() {
  return usePostMutation(() => socialMediaApi.recheck());
}

export function useRefreshToken() {
  return usePostMutation(() => socialMediaApi.refreshToken());
}


// ---------------- comments and direct messages ----------------

export function useInboxSummary() {
  // New comments arrive through the background reader, so look again now and then.
  return useQuery({ queryKey: ["social-media", "inbox", "summary"], queryFn: socialMediaApi.inboxSummary, refetchInterval: 60000 });
}

export function useSyncInbox() {
  return usePostMutation(() => socialMediaApi.syncInbox());
}

export function useComments(params: { view: CommentView; q?: string; skip?: number; limit?: number }) {
  return useQuery({ queryKey: ["social-media", "inbox", "comments", params], queryFn: () => socialMediaApi.comments(params), placeholderData: keepPreviousData });
}

export function useConversations(params: { view: ConversationView; q?: string; skip?: number; limit?: number }) {
  return useQuery({ queryKey: ["social-media", "inbox", "conversations", params], queryFn: () => socialMediaApi.conversations(params), placeholderData: keepPreviousData });
}

export function useThread(id: string | null) {
  return useQuery({ queryKey: ["social-media", "inbox", "thread", id], queryFn: () => socialMediaApi.thread(id as string), enabled: id !== null });
}

export function useSuggest(kind: "comment" | "dm") {
  return usePostMutation((id: string): Promise<InboxComment | Conversation> => (kind === "comment" ? socialMediaApi.suggestForComment(id) : socialMediaApi.suggestForConversation(id)));
}

export function useSendReply(kind: "comment" | "dm") {
  return usePostMutation((v: { id: string; payload: ReplyPayload }) =>
    kind === "comment" ? socialMediaApi.replyToComment(v.id, v.payload) : socialMediaApi.replyToConversation(v.id, v.payload),
  );
}

export function useMarkHandled(kind: "comment" | "dm") {
  return usePostMutation((v: { id: string; action: "ignore" | "reopen" }): Promise<InboxComment | Conversation> =>
    kind === "comment" ? socialMediaApi.markComment(v.id, v.action) : socialMediaApi.markConversation(v.id, v.action),
  );
}

export function useReplyHistory() {
  return useQuery({ queryKey: ["social-media", "inbox", "replies"], queryFn: socialMediaApi.replyHistory });
}

export function useReconcileReply() {
  return usePostMutation((id: string) => socialMediaApi.reconcileReply(id));
}

export function useResolveReply() {
  return usePostMutation((v: { id: string; sent: boolean }) => socialMediaApi.resolveReply(v.id, v.sent));
}


// ---------------- analytics, experiments and reports ----------------

export function useAnalyticsStatus() {
  return useQuery({ queryKey: ["social-media", "analytics", "status"], queryFn: socialMediaApi.analyticsStatus });
}

export function useSyncAnalytics() {
  return usePostMutation(() => socialMediaApi.syncAnalytics());
}

export function useAnalyticsOverview(days: number) {
  return useQuery({ queryKey: ["social-media", "analytics", "overview", days], queryFn: () => socialMediaApi.analyticsOverview(days), placeholderData: keepPreviousData });
}

export function useAnalyticsPosts() {
  return useQuery({ queryKey: ["social-media", "analytics", "posts"], queryFn: socialMediaApi.analyticsPosts });
}

export function useMetricDefinitions(enabled: boolean) {
  return useQuery({ queryKey: ["social-media", "analytics", "metrics"], queryFn: socialMediaApi.metricDefinitions, enabled, staleTime: Infinity });
}

export function useExperiments() {
  return useQuery({ queryKey: ["social-media", "experiments"], queryFn: socialMediaApi.experiments });
}

export function useExperiment(id: string | null) {
  return useQuery({ queryKey: ["social-media", "experiments", id], queryFn: () => socialMediaApi.experiment(id as string), enabled: id !== null });
}

export function useCreateExperiment() {
  return usePostMutation((payload: ExperimentPayload) => socialMediaApi.createExperiment(payload));
}

export function useUpdateExperiment() {
  return usePostMutation((v: { id: string; payload: Parameters<typeof socialMediaApi.updateExperiment>[1] }) => socialMediaApi.updateExperiment(v.id, v.payload));
}

export function useDeleteExperiment() {
  return usePostMutation((id: string) => socialMediaApi.deleteExperiment(id));
}

export function useReports() {
  return useQuery({ queryKey: ["social-media", "reports"], queryFn: () => socialMediaApi.reports() });
}

export function useGenerateReport() {
  return usePostMutation((v: { kind: "weekly" | "monthly"; periodStart?: string }) => socialMediaApi.generateReport(v.kind, v.periodStart));
}


// ---------------- tracked links, leads and hashtags ----------------

export function useLinks() {
  return useQuery({ queryKey: ["social-media", "links"], queryFn: socialMediaApi.links });
}

export function useCreateLink() {
  return usePostMutation((payload: LinkPayload) => socialMediaApi.createLink(payload));
}

export function useUpdateLink() {
  return usePostMutation((v: { id: string; payload: { name?: string; is_active?: boolean; course_label?: string } }) => socialMediaApi.updateLink(v.id, v.payload));
}

export function useLeadOptions(enabled: boolean) {
  return useQuery({ queryKey: ["social-media", "lead-options"], queryFn: socialMediaApi.leadOptions, enabled });
}

export function useLeadHint(kind: "comment" | "dm", id: string | null) {
  return useQuery({
    queryKey: ["social-media", "lead-hint", kind, id],
    queryFn: () => (kind === "comment" ? socialMediaApi.commentLeadHint(id as string) : socialMediaApi.conversationLeadHint(id as string)),
    enabled: id !== null,
  });
}

export function useCreateLead(kind: "comment" | "dm") {
  return usePostMutation((v: { id: string; payload: LeadPayload }) => (kind === "comment" ? socialMediaApi.leadFromComment(v.id, v.payload) : socialMediaApi.leadFromConversation(v.id, v.payload)));
}

export function useFunnel(days: number) {
  return useQuery({ queryKey: ["social-media", "funnel", days], queryFn: () => socialMediaApi.funnel(days), placeholderData: keepPreviousData });
}

export function useSocialLeads(enabled: boolean) {
  return useQuery({ queryKey: ["social-media", "social-leads"], queryFn: socialMediaApi.socialLeads, enabled });
}

export function useHashtags() {
  return useQuery({ queryKey: ["social-media", "hashtags"], queryFn: socialMediaApi.hashtags });
}


// ---------------- background jobs, retention and erasure ----------------

export function useJobHealth() {
  return useQuery({ queryKey: ["social-media", "health"], queryFn: socialMediaApi.jobHealth, refetchInterval: 60000 });
}

export function useRetentionStatus(enabled: boolean) {
  return useQuery({ queryKey: ["social-media", "retention"], queryFn: socialMediaApi.retentionStatus, enabled });
}

export function useRunRetention() {
  return usePostMutation((confirm: boolean) => socialMediaApi.runRetention(confirm));
}

export function useErasePerson() {
  return usePostMutation((v: { handle: string; confirm: boolean }) => socialMediaApi.erasePerson(v.handle, v.confirm));
}
