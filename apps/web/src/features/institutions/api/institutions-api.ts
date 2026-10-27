import { apiClient } from "@/api/client";

export type EventType = "workshop" | "hackathon" | "exam" | "other";
export type EventStatus = "upcoming" | "ongoing" | "completed";

export interface Institution {
  id: string;
  name: string;
  location: string;
  mou_details: string | null;
  mou_filename: string | null;
  mou_size_bytes: number | null;
  faculty_name: string;
  faculty_designation: string | null;
  faculty_email: string | null;
  faculty_phone: string | null;
  notes: string | null;
  event_count: number;
  student_count: number;
  created_at: string;
}

export interface InstitutionPayload {
  name: string;
  location: string;
  mou_details?: string | null;
  faculty_name: string;
  faculty_designation?: string | null;
  faculty_email?: string | null;
  faculty_phone?: string | null;
  notes?: string | null;
}

export interface InstitutionEvent {
  id: string;
  institution_id: string;
  institution_name: string;
  name: string;
  event_type: EventType;
  start_date: string;
  end_date: string;
  description: string | null;
  max_capacity: number | null;
  status: EventStatus;
  student_count: number;
  exam_count: number;
  hackathon_count: number;
  created_at: string;
}

export interface EventPayload {
  name: string;
  event_type: EventType;
  start_date: string;
  end_date: string;
  description?: string | null;
  max_capacity?: number | null;
  status?: EventStatus;
}

export interface StudentEventRef {
  event_id: string;
  event_name: string;
  event_type: EventType;
  status: EventStatus;
}

export interface InstitutionStudent {
  id: string;
  institution_id: string;
  institution_name: string;
  name: string;
  email: string;
  phone: string | null;
  details: Record<string, string>;
  events: StudentEventRef[];
  created_at: string;
}

export interface StudentPayload {
  name: string;
  email: string;
  phone?: string | null;
  details?: Record<string, string>;
}

export interface EventStudent {
  student_id: string;
  institution_id: string;
  institution_name: string;
  event_id: string;
  event_name: string;
  name: string;
  email: string;
  phone: string | null;
  details: Record<string, string>;
  individual_score: number | null;
  remarks: string | null;
  registered_at: string;
}

export interface ImportProblem {
  row: number;
  reason: string;
  raw: string;
}

export interface ImportResult {
  dry_run: boolean;
  total_rows: number;
  new_students: number;
  existing_students: number;
  registered: number;
  already_registered: number;
  over_capacity: number;
  problems: ImportProblem[];
}

export interface LinkedExam {
  id: string;
  title: string;
  status: string;
  attendee_count: number;
  question_count: number;
  event_id: string | null;
}

export interface LinkedHackathon {
  id: string;
  code: string;
  title: string;
  status: string;
  start_date: string;
  end_date: string;
  event_id: string | null;
}

/** Where a student list comes from: an uploaded file, or text pasted into a box. */
export type ImportSource = { file: File } | { text: string };

function importForm(source: ImportSource, dryRun: boolean): FormData {
  const form = new FormData();
  if ("file" in source) form.append("file", source.file);
  else form.append("text", source.text);
  form.append("dry_run", dryRun ? "true" : "false");
  return form;
}

// apiClient defaults to a JSON Content-Type, under which axios turns a FormData body into JSON; naming multipart lets
// the browser add the boundary.
const multipart = { headers: { "Content-Type": "multipart/form-data" } };

export const institutionsKeys = {
  all: ["institutions"] as const,
  list: (q: string) => ["institutions", "list", q] as const,
  detail: (id: string) => ["institutions", "detail", id] as const,
  events: (id: string) => ["institutions", "events", id] as const,
  students: (id: string, q: string, eventId?: string) => ["institutions", "students", id, q, eventId ?? ""] as const,
  event: (id: string) => ["institutions", "event", id] as const,
  eventStudents: (id: string, q: string) => ["institutions", "event-students", id, q] as const,
  eventExams: (id: string) => ["institutions", "event-exams", id] as const,
  eventHackathons: (id: string) => ["institutions", "event-hackathons", id] as const,
};

export const institutionsApi = {
  list: (q = "") =>
    apiClient
      .get<{ items: Institution[]; total: number }>("/institutions", { params: { q: q || undefined, limit: 500 } })
      .then((r) => r.data),
  get: (id: string) => apiClient.get<Institution>(`/institutions/${id}`).then((r) => r.data),
  create: (payload: InstitutionPayload) => apiClient.post<Institution>("/institutions", payload).then((r) => r.data),
  update: (id: string, payload: Partial<InstitutionPayload>) =>
    apiClient.patch<Institution>(`/institutions/${id}`, payload).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/institutions/${id}`).then((r) => r.data),

  uploadMou: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.put<Institution>(`/institutions/${id}/mou`, form, multipart).then((r) => r.data);
  },
  removeMou: (id: string) => apiClient.delete<Institution>(`/institutions/${id}/mou`).then((r) => r.data),
  /** Fetched with the auth header, then handed to the browser as a download. */
  downloadMou: async (id: string, filename: string) => {
    const response = await apiClient.get<Blob>(`/institutions/${id}/mou`, { responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  events: (id: string) => apiClient.get<InstitutionEvent[]>(`/institutions/${id}/events`).then((r) => r.data),
  createEvent: (id: string, payload: EventPayload) =>
    apiClient.post<InstitutionEvent>(`/institutions/${id}/events`, payload).then((r) => r.data),

  students: (id: string, q = "", eventId?: string) =>
    apiClient
      .get<{ items: InstitutionStudent[]; total: number }>(`/institutions/${id}/students`, {
        params: { q: q || undefined, event_id: eventId, limit: 500 },
      })
      .then((r) => r.data),
  addStudent: (id: string, payload: StudentPayload, eventId?: string) =>
    apiClient
      .post<InstitutionStudent>(`/institutions/${id}/students`, payload, { params: { event_id: eventId } })
      .then((r) => r.data),
  importStudents: (id: string, source: ImportSource, dryRun: boolean) =>
    apiClient
      .post<ImportResult>(`/institutions/${id}/students/import`, importForm(source, dryRun), multipart)
      .then((r) => r.data),

  // ---- one event
  event: (id: string) => apiClient.get<InstitutionEvent>(`/institution-events/${id}`).then((r) => r.data),
  updateEvent: (id: string, payload: Partial<EventPayload>) =>
    apiClient.patch<InstitutionEvent>(`/institution-events/${id}`, payload).then((r) => r.data),
  removeEvent: (id: string) => apiClient.delete(`/institution-events/${id}`).then((r) => r.data),

  eventStudents: (id: string, q = "") =>
    apiClient
      .get<{ items: EventStudent[]; total: number }>(`/institution-events/${id}/students`, {
        params: { q: q || undefined, limit: 1000 },
      })
      .then((r) => r.data),
  importEventStudents: (id: string, source: ImportSource, dryRun: boolean) =>
    apiClient
      .post<ImportResult>(`/institution-events/${id}/students/import`, importForm(source, dryRun), multipart)
      .then((r) => r.data),
  registerStudents: (id: string, studentIds: string[]) =>
    apiClient.post<{ message: string }>(`/institution-events/${id}/students`, { student_ids: studentIds }).then((r) => r.data),
  updateRegistration: (id: string, studentId: string, payload: { individual_score?: number | null; remarks?: string | null }) =>
    apiClient.patch(`/institution-events/${id}/students/${studentId}`, payload).then((r) => r.data),
  unregister: (id: string, studentId: string) =>
    apiClient.delete(`/institution-events/${id}/students/${studentId}`).then((r) => r.data),

  eventExams: (id: string) => apiClient.get<LinkedExam[]>(`/institution-events/${id}/exams`).then((r) => r.data),
  examCandidates: (id: string) =>
    apiClient.get<LinkedExam[]>(`/institution-events/${id}/exam-candidates`).then((r) => r.data),
  linkExam: (id: string, examId: string) => apiClient.put(`/institution-events/${id}/exams/${examId}`).then((r) => r.data),
  unlinkExam: (id: string, examId: string) =>
    apiClient.delete(`/institution-events/${id}/exams/${examId}`).then((r) => r.data),

  eventHackathons: (id: string) =>
    apiClient.get<LinkedHackathon[]>(`/institution-events/${id}/hackathons`).then((r) => r.data),
  hackathonCandidates: (id: string) =>
    apiClient.get<LinkedHackathon[]>(`/institution-events/${id}/hackathon-candidates`).then((r) => r.data),
  linkHackathon: (id: string, hackathonId: string) =>
    apiClient.put(`/institution-events/${id}/hackathons/${hackathonId}`).then((r) => r.data),
  unlinkHackathon: (id: string, hackathonId: string) =>
    apiClient.delete(`/institution-events/${id}/hackathons/${hackathonId}`).then((r) => r.data),

  // ---- one student
  student: (id: string) => apiClient.get<InstitutionStudent>(`/institution-students/${id}`).then((r) => r.data),
  updateStudent: (id: string, payload: Partial<StudentPayload>) =>
    apiClient.patch<InstitutionStudent>(`/institution-students/${id}`, payload).then((r) => r.data),
  removeStudent: (id: string) => apiClient.delete(`/institution-students/${id}`).then((r) => r.data),
};
