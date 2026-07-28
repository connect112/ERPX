import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AlbumCreatePayload,
  type AlbumUpdatePayload,
  mediaApi,
} from "@/features/media/api/media-api";

const mediaKeys = {
  all: ["media"] as const,
  albums: (params: { skip?: number; limit?: number }) => [...mediaKeys.all, "albums", params] as const,
  album: (id: string) => [...mediaKeys.all, "albums", id] as const,
  assets: (albumId: string) => [...mediaKeys.all, "albums", albumId, "assets"] as const,
};

export function useAlbumsList(params: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: mediaKeys.albums(params),
    queryFn: () => mediaApi.listAlbums(params),
    placeholderData: keepPreviousData,
  });
}

export function useAlbum(id: string | undefined) {
  return useQuery({
    queryKey: mediaKeys.album(id ?? ""),
    queryFn: () => mediaApi.getAlbum(id as string),
    enabled: !!id,
  });
}

export function useCreateAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AlbumCreatePayload) => mediaApi.createAlbum(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mediaKeys.all }),
  });
}

export function useUpdateAlbum(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AlbumUpdatePayload) => mediaApi.updateAlbum(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mediaKeys.all }),
  });
}

export function useDeleteAlbum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => mediaApi.deleteAlbum(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mediaKeys.all }),
  });
}

export function useAlbumAssets(albumId: string | undefined) {
  return useQuery({
    queryKey: mediaKeys.assets(albumId ?? ""),
    queryFn: () => mediaApi.listAlbumAssets(albumId as string),
    enabled: !!albumId,
  });
}

export function useUploadAsset(albumId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, caption }: { file: File; caption?: string }) => {
      const { asset_id, upload_url } = await mediaApi.requestAssetUpload(albumId, {
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        caption,
      });

      const uploadResponse = await mediaApi.uploadToPresignedUrl(upload_url, file);
      if (!uploadResponse.ok) {
        throw new Error("Upload to storage failed.");
      }

      return mediaApi.confirmAssetUpload(asset_id);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mediaKeys.assets(albumId) }),
  });
}

export function useAssetDownloadUrl() {
  return useMutation({
    mutationFn: (assetId: string) => mediaApi.getAssetDownloadUrl(assetId),
  });
}

export function useUpdateAssetCaption(albumId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ assetId, caption }: { assetId: string; caption: string | null }) =>
      mediaApi.updateAssetCaption(assetId, caption),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mediaKeys.assets(albumId) }),
  });
}

export function useDeleteAsset(albumId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assetId: string) => mediaApi.deleteAsset(assetId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mediaKeys.assets(albumId) }),
  });
}
