import { ArrowLeft, Images, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAlbum, useAlbumAssets, useDeleteAlbum, useUploadAsset } from "@/features/media/api/media-hooks";
import { AssetCard } from "@/features/media/components/asset-card";

export function AlbumDetailPage() {
  const { albumId } = useParams<{ albumId: string }>();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: album, isLoading } = useAlbum(albumId);
  const { data: assets, isLoading: assetsLoading } = useAlbumAssets(albumId);
  const uploadAsset = useUploadAsset(albumId ?? "");
  const deleteAlbum = useDeleteAlbum();

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    uploadAsset.mutate(
      { file },
      { onError: () => setError("Upload failed. Please try again.") }
    );
  };

  const handleDeleteAlbum = () => {
    if (!albumId) return;
    deleteAlbum.mutate(albumId, { onSuccess: () => navigate("/media/albums") });
  };

  if (isLoading || !album) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/media/albums")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{album.title}</h1>
            {album.description && <p className="mt-1 text-muted-foreground">{album.description}</p>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => fileInputRef.current?.click()} disabled={uploadAsset.isPending}>
            <Upload className="h-4 w-4" />
            {uploadAsset.isPending ? "Uploading..." : "Upload"}
          </Button>
          <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileSelected} />
          <Button variant="outline" onClick={handleDeleteAlbum} disabled={deleteAlbum.isPending}>
            <Trash2 className="h-4 w-4" />
            Delete album
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {assetsLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-56 w-full" />
          ))}
        </div>
      )}

      {!assetsLoading && (assets?.length ?? 0) === 0 && (
        <p className="flex flex-col items-center gap-2 py-16 text-center text-sm text-muted-foreground">
          <Images className="h-10 w-10 text-muted-foreground/50" />
          No assets in this album yet. Upload the first one to get started.
        </p>
      )}

      {!assetsLoading && (assets?.length ?? 0) > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {assets?.map((asset) => (
            <AssetCard key={asset.id} albumId={album.id} asset={asset} />
          ))}
        </div>
      )}
    </div>
  );
}
