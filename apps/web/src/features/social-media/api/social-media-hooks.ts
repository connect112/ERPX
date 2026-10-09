import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  socialMediaApi,
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
