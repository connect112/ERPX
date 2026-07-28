import { apiClient } from "@/api/client";

export type DocumentStatus = "pending" | "uploaded";

export interface DocumentPublic {
  id: string;
  organization_id: string;
  uploaded_by_user_id: string | null;
  entity_type: string;
  entity_id: string | null;
  filename: string;
  content_type: string;
  size_bytes: number | null;
  status: DocumentStatus;
  created_at: string;
}

export interface PresignedUploadRequest {
  entity_type: string;
  entity_id?: string;
  filename: string;
  content_type: string;
}

export interface PresignedUploadResponse {
  document_id: string;
  upload_url: string;
}

export const documentsApi = {
  requestUpload: (payload: PresignedUploadRequest) =>
    apiClient
      .post<PresignedUploadResponse>("/documents/presigned-upload", payload)
      .then((r) => r.data),

  // Uploads directly to object storage (MinIO/S3) using the presigned URL —
  // deliberately NOT `apiClient` here, this must not go through our API's
  // baseURL/auth interceptors, it's a direct PUT to the storage endpoint.
  uploadToPresignedUrl: (uploadUrl: string, file: File) =>
    fetch(uploadUrl, {
      method: "PUT",
      body: file,
      headers: { "Content-Type": file.type || "application/octet-stream" },
    }),

  confirm: (documentId: string) =>
    apiClient.post<DocumentPublic>(`/documents/${documentId}/confirm`).then((r) => r.data),

  list: (params: { entity_type: string; entity_id: string }) =>
    apiClient.get<DocumentPublic[]>("/documents", { params }).then((r) => r.data),

  getDownloadUrl: (documentId: string) =>
    apiClient
      .get<{ download_url: string }>(`/documents/${documentId}/download-url`)
      .then((r) => r.data.download_url),

  remove: (documentId: string) => apiClient.delete(`/documents/${documentId}`).then((r) => r.data),
};
