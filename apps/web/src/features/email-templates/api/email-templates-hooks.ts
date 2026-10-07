import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type TemplateScope, emailTemplatesApi } from "@/features/email-templates/api/email-templates-api";

const root = (scope: TemplateScope) => ["email-templates", scope.hackathonId ?? "org"] as const;

export function useEmailTemplates(scope: TemplateScope) {
  return useQuery({
    queryKey: [...root(scope), "list"],
    queryFn: () => emailTemplatesApi.list(scope),
  });
}

export function useEmailTemplate(scope: TemplateScope, key: string | null) {
  return useQuery({
    queryKey: [...root(scope), "detail", key],
    queryFn: () => emailTemplatesApi.get(scope, key as string),
    enabled: key !== null,
  });
}

export function useSaveEmailTemplate(scope: TemplateScope, key: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { subject: string; body: string }) => emailTemplatesApi.save(scope, key, payload),
    // An organisation-wide edit changes what every event without its own wording sends.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["email-templates"] }),
  });
}

export function useResetEmailTemplate(scope: TemplateScope, key: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => emailTemplatesApi.reset(scope, key),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["email-templates"] }),
  });
}

export function usePreviewEmailTemplate(scope: TemplateScope, key: string) {
  return useMutation({
    mutationFn: (payload: { subject: string; body: string }) => emailTemplatesApi.preview(scope, key, payload),
  });
}

export function useSendTestEmail(scope: TemplateScope, key: string) {
  return useMutation({
    mutationFn: (payload: { to_email: string; subject?: string; body?: string }) =>
      emailTemplatesApi.sendTest(scope, key, payload),
  });
}
