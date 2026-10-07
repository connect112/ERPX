import { apiClient } from "@/api/client";

/** Whose wording is being edited: the whole organisation's, or one hackathon's own. */
export interface TemplateScope {
  hackathonId?: string;
}

export interface TemplateVariable {
  name: string;
  description: string;
  sample: string;
}

export interface TemplateSummary {
  key: string;
  name: string;
  category: string;
  description: string;
  when_sent: string;
  has_attachment: boolean;
  event_scoped: boolean;
  /** Edited (for an event: edited for that event). */
  customised: boolean;
  /** Event view only: no wording of its own, so the organisation's (or the default) is used. */
  inherited: boolean;
  updated_at: string | null;
  updated_by_name: string | null;
}

export interface TemplateDetail extends TemplateSummary {
  subject: string;
  body: string;
  default_subject: string;
  default_body: string;
  variables: TemplateVariable[];
  required: string[];
}

export interface TemplatePreview {
  subject: string;
  html: string;
  text: string;
  errors: string[];
}

function base(scope: TemplateScope): string {
  return scope.hackathonId ? `/hackathons/${scope.hackathonId}/email-templates` : "/email-templates";
}

export const emailTemplatesApi = {
  list: (scope: TemplateScope) => apiClient.get<TemplateSummary[]>(base(scope)).then((r) => r.data),

  get: (scope: TemplateScope, key: string) =>
    apiClient.get<TemplateDetail>(`${base(scope)}/${key}`).then((r) => r.data),

  save: (scope: TemplateScope, key: string, payload: { subject: string; body: string }) =>
    apiClient.put<TemplateDetail>(`${base(scope)}/${key}`, payload).then((r) => r.data),

  reset: (scope: TemplateScope, key: string) =>
    apiClient.delete<TemplateDetail>(`${base(scope)}/${key}`).then((r) => r.data),

  preview: (scope: TemplateScope, key: string, payload: { subject: string; body: string }) =>
    apiClient.post<TemplatePreview>(`${base(scope)}/${key}/preview`, payload).then((r) => r.data),

  sendTest: (
    scope: TemplateScope,
    key: string,
    payload: { to_email: string; subject?: string; body?: string }
  ) =>
    apiClient
      .post<{ sent: boolean; message: string }>(`${base(scope)}/${key}/test`, payload)
      .then((r) => r.data),
};
