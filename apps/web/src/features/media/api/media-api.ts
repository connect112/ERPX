import { apiClient } from "@/api/client";

export type MediaAssetStatus = "pending" | "uploaded";

export interface AlbumPublic {
  id: string;
  organization_id: string;
  created_by_user_id: string | null;
  title: string;
  description: string | null;
  created_at: string;
}

export interface AlbumListResponse {
  items: AlbumPublic[];
  total: number;
}

export interface AlbumCreatePayload {
  title: string;
  description?: string;
}

export type AlbumUpdatePayload = Partial<AlbumCreatePayload>;

export interface MediaAssetPublic {
  id: string;
  organization_id: string;
  album_id: string;
  uploaded_by_user_id: string | null;
  filename: string;
  content_type: string;
  size_bytes: number | null;
  caption: string | null;
  status: MediaAssetStatus;
  created_at: string;
}

export interface PresignedAssetUploadRequest {
  filename: string;
  content_type: string;
  caption?: string;
}

export interface PresignedAssetUploadResponse {
  asset_id: string;
  upload_url: string;
}

export const mediaApi = {
  listAlbums: (params: { skip?: number; limit?: number }) =>
    apiClient.get<AlbumListResponse>("/media/albums", { params }).then((r) => r.data),

  getAlbum: (id: string) => apiClient.get<AlbumPublic>(`/media/albums/${id}`).then((r) => r.data),

  createAlbum: (payload: AlbumCreatePayload) =>
    apiClient.post<AlbumPublic>("/media/albums", payload).then((r) => r.data),

  updateAlbum: (id: string, payload: AlbumUpdatePayload) =>
    apiClient.patch<AlbumPublic>(`/media/albums/${id}`, payload).then((r) => r.data),

  deleteAlbum: (id: string) => apiClient.delete(`/media/albums/${id}`).then((r) => r.data),

  requestAssetUpload: (albumId: string, payload: PresignedAssetUploadRequest) =>
    apiClient
      .post<PresignedAssetUploadResponse>(`/media/albums/${albumId}/assets/presigned-upload`, payload)
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

  confirmAssetUpload: (assetId: string) =>
    apiClient.post<MediaAssetPublic>(`/media/assets/${assetId}/confirm`).then((r) => r.data),

  listAlbumAssets: (albumId: string) =>
    apiClient.get<MediaAssetPublic[]>(`/media/albums/${albumId}/assets`).then((r) => r.data),

  getAssetDownloadUrl: (assetId: string) =>
    apiClient
      .get<{ download_url: string }>(`/media/assets/${assetId}/download-url`)
      .then((r) => r.data.download_url),

  updateAssetCaption: (assetId: string, caption: string | null) =>
    apiClient.patch<MediaAssetPublic>(`/media/assets/${assetId}`, { caption }).then((r) => r.data),

  deleteAsset: (assetId: string) => apiClient.delete(`/media/assets/${assetId}`).then((r) => r.data),
};
