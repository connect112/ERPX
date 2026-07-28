import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { documentsApi } from "@/features/documents/api/documents-api";

const documentsKeys = {
  all: ["documents"] as const,
  list: (entityType: string, entityId: string) =>
    [...documentsKeys.all, "list", entityType, entityId] as const,
};

export function useDocumentsList(entityType: string, entityId: string | undefined) {
  return useQuery({
    queryKey: documentsKeys.list(entityType, entityId ?? ""),
    queryFn: () => documentsApi.list({ entity_type: entityType, entity_id: entityId as string }),
    enabled: !!entityId,
  });
}

export function useUploadDocument(entityType: string, entityId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      const { document_id, upload_url } = await documentsApi.requestUpload({
        entity_type: entityType,
        entity_id: entityId,
        filename: file.name,
        content_type: file.type || "application/octet-stream",
      });

      const uploadResponse = await documentsApi.uploadToPresignedUrl(upload_url, file);
      if (!uploadResponse.ok) {
        throw new Error("Upload to storage failed.");
      }

      return documentsApi.confirm(document_id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsKeys.list(entityType, entityId) });
    },
  });
}

export function useDeleteDocument(entityType: string, entityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => documentsApi.remove(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsKeys.list(entityType, entityId) });
    },
  });
}

export function useDownloadDocument() {
  return useMutation({
    mutationFn: (documentId: string) => documentsApi.getDownloadUrl(documentId),
  });
}
