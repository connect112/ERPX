import { apiClient } from "@/api/client";
import type {
  IncidentSeverity,
  IncidentStatus,
  SOCServiceStatus,
  SOCServiceType,
} from "@/features/corporate/soc/schemas/soc-schemas";

export interface SOCServicePublic {
  id: string;
  organization_id: string;
  client_id: string;
  project_id: string | null;
  service_type: SOCServiceType;
  sla_response_time_minutes: number | null;
  status: SOCServiceStatus;
  start_date: string;
  end_date: string | null;
  notes: string | null;
  created_at: string;
}

export interface SOCServiceCreatePayload {
  client_id: string;
  project_id?: string;
  service_type: SOCServiceType;
  sla_response_time_minutes?: number;
  start_date: string;
  end_date?: string;
  notes?: string;
}

export interface SOCServiceUpdatePayload {
  sla_response_time_minutes?: number;
  status?: SOCServiceStatus;
  end_date?: string;
  notes?: string;
}

export interface SOCIncidentPublic {
  id: string;
  soc_service_id: string;
  assigned_to_employee_id: string | null;
  title: string;
  severity: IncidentSeverity;
  description: string;
  status: IncidentStatus;
  detected_at: string;
  resolved_at: string | null;
  created_at: string;
}

export interface SOCIncidentCreatePayload {
  title: string;
  severity: IncidentSeverity;
  description: string;
  detected_at: string;
  assigned_to_employee_id?: string;
}

export interface SOCIncidentUpdatePayload {
  status?: IncidentStatus;
  assigned_to_employee_id?: string;
  resolved_at?: string;
}

export const socApi = {
  listByClient: (clientId: string, status?: SOCServiceStatus) =>
    apiClient
      .get<SOCServicePublic[]>(`/corporate/soc/services/clients/${clientId}`, { params: { status } })
      .then((r) => r.data),

  create: (payload: SOCServiceCreatePayload) =>
    apiClient.post<SOCServicePublic>("/corporate/soc/services", payload).then((r) => r.data),

  update: (id: string, payload: SOCServiceUpdatePayload) =>
    apiClient.patch<SOCServicePublic>(`/corporate/soc/services/${id}`, payload).then((r) => r.data),

  createIncident: (serviceId: string, payload: SOCIncidentCreatePayload) =>
    apiClient
      .post<SOCIncidentPublic>(`/corporate/soc/services/${serviceId}/incidents`, payload)
      .then((r) => r.data),

  listIncidents: (serviceId: string, status?: IncidentStatus) =>
    apiClient
      .get<SOCIncidentPublic[]>(`/corporate/soc/services/${serviceId}/incidents`, { params: { status } })
      .then((r) => r.data),

  updateIncident: (incidentId: string, payload: SOCIncidentUpdatePayload) =>
    apiClient.patch<SOCIncidentPublic>(`/corporate/soc/incidents/${incidentId}`, payload).then((r) => r.data),
};
