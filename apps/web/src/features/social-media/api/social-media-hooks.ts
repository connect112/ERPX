import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  socialMediaApi,
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
