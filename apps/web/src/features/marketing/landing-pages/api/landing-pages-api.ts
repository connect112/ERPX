import { apiClient } from "@/api/client";
import type { LandingPageStatus } from "@/features/marketing/landing-pages/schemas/landing-page-schemas";

export interface LandingPagePublic {
  id: string;
  organization_id: string;
  campaign_id: string | null;
  slug: string;
  title: string;
  meta_description: string | null;
  content: string;
  status: LandingPageStatus;
  published_at: string | null;
  created_at: string;
}

export interface LandingPageListResponse {
  items: LandingPagePublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface LandingPageListParams {
  campaign_id?: string;
  status?: LandingPageStatus;
  skip?: number;
  limit?: number;
}

export interface LandingPageCreatePayload {
  slug: string;
  title: string;
  campaign_id?: string;
  meta_description?: string;
  content: string;
}

export interface LandingPageUpdatePayload {
  title?: string;
  campaign_id?: string;
  meta_description?: string;
  content?: string;
}

export interface LandingPageStats {
  landing_page_id: string;
  total_views: number;
  total_conversions: number;
  conversion_rate_percent: number;
}

export const landingPagesApi = {
  list: (params: LandingPageListParams) =>
    apiClient.get<LandingPageListResponse>("/marketing/landing-pages", { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<LandingPagePublic>(`/marketing/landing-pages/${id}`).then((r) => r.data),

  create: (payload: LandingPageCreatePayload) =>
    apiClient.post<LandingPagePublic>("/marketing/landing-pages", payload).then((r) => r.data),

  update: (id: string, payload: LandingPageUpdatePayload) =>
    apiClient.patch<LandingPagePublic>(`/marketing/landing-pages/${id}`, payload).then((r) => r.data),

  publish: (id: string) =>
    apiClient.post<LandingPagePublic>(`/marketing/landing-pages/${id}/publish`).then((r) => r.data),

  archive: (id: string) =>
    apiClient.post<LandingPagePublic>(`/marketing/landing-pages/${id}/archive`).then((r) => r.data),

  stats: (id: string) =>
    apiClient.get<LandingPageStats>(`/marketing/landing-pages/${id}/stats`).then((r) => r.data),
};
