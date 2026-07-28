import { apiClient } from "@/api/client";
import type {
  EventMode,
  EventStatus,
  ReferralStatus,
  RegistrationStatus,
} from "@/features/alumni/schemas/event-schemas";

export interface AlumniProfilePublic {
  id: string;
  organization_id: string;
  student_id: string;
  graduation_year: number | null;
  current_company: string | null;
  current_designation: string | null;
  current_location: string | null;
  linkedin_url: string | null;
  bio: string | null;
  is_verified: boolean;
  created_at: string;
}

export interface AlumniProfileListResponse {
  items: AlumniProfilePublic[];
  total: number;
}

export interface AlumniEventPublic {
  id: string;
  organization_id: string;
  title: string;
  description: string | null;
  mode: EventMode;
  venue: string | null;
  meeting_link: string | null;
  event_date: string;
  registration_deadline: string | null;
  status: EventStatus;
  created_at: string;
}

export interface AlumniEventListResponse {
  items: AlumniEventPublic[];
  total: number;
}

export interface AlumniEventListParams {
  status?: EventStatus;
  skip?: number;
  limit?: number;
}

export interface AlumniEventCreatePayload {
  title: string;
  description?: string;
  mode: EventMode;
  venue?: string;
  meeting_link?: string;
  event_date: string;
  registration_deadline?: string;
}

export type AlumniEventUpdatePayload = Partial<AlumniEventCreatePayload>;

export interface EventRegistrationPublic {
  id: string;
  event_id: string;
  alumni_id: string;
  registered_at: string;
  status: RegistrationStatus;
  created_at: string;
}

export interface JobReferralPublic {
  id: string;
  organization_id: string;
  alumni_id: string;
  title: string;
  company: string;
  description: string | null;
  contact_email: string | null;
  referral_link: string | null;
  status: ReferralStatus;
  posted_at: string;
  created_at: string;
}

export interface JobReferralListResponse {
  items: JobReferralPublic[];
  total: number;
}

export const alumniApi = {
  listProfiles: (params: { skip?: number; limit?: number }) =>
    apiClient.get<AlumniProfileListResponse>("/alumni/profiles", { params }).then((r) => r.data),

  verifyProfile: (id: string, isVerified: boolean) =>
    apiClient
      .post<AlumniProfilePublic>(`/alumni/profiles/${id}/verify`, { is_verified: isVerified })
      .then((r) => r.data),

  listEvents: (params: AlumniEventListParams) =>
    apiClient.get<AlumniEventListResponse>("/alumni/events", { params }).then((r) => r.data),

  getEvent: (id: string) => apiClient.get<AlumniEventPublic>(`/alumni/events/${id}`).then((r) => r.data),

  createEvent: (payload: AlumniEventCreatePayload) =>
    apiClient.post<AlumniEventPublic>("/alumni/events", payload).then((r) => r.data),

  updateEvent: (id: string, payload: AlumniEventUpdatePayload) =>
    apiClient.patch<AlumniEventPublic>(`/alumni/events/${id}`, payload).then((r) => r.data),

  changeEventStatus: (id: string, status: EventStatus) =>
    apiClient.post<AlumniEventPublic>(`/alumni/events/${id}/status`, { status }).then((r) => r.data),

  listEventRegistrations: (id: string) =>
    apiClient.get<EventRegistrationPublic[]>(`/alumni/events/${id}/registrations`).then((r) => r.data),

  markAttendance: (registrationId: string, status: RegistrationStatus) =>
    apiClient
      .post<EventRegistrationPublic>(`/alumni/registrations/${registrationId}/attendance`, { status })
      .then((r) => r.data),

  listAllReferrals: (params: { status?: ReferralStatus; skip?: number; limit?: number }) =>
    apiClient.get<JobReferralListResponse>("/alumni/referrals/all", { params }).then((r) => r.data),
};
