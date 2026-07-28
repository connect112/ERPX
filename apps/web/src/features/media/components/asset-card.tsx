import { Download, ImageOff, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { mediaApi, type MediaAssetPublic } from "@/features/media/api/media-api";
import { useDeleteAsset, useUpdateAssetCaption } from "@/features/media/api/media-hooks";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface AssetCardProps {
  albumId: string;
  asset: MediaAssetPublic;
}

export function AssetCard({ albumId, asset }: AssetCardProps) {
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [caption, setCaption] = useState(asset.caption ?? "");
  const isImage = asset.content_type.startsWith("image/");

  const updateCaption = useUpdateAssetCaption(albumId);
  const deleteAsset = useDeleteAsset(albumId);

  useEffect(() => {
    let cancelled = false;
    if (isImage) {
      mediaApi.getAssetDownloadUrl(asset.id).then((url) => {
        if (!cancelled) setDownloadUrl(url);
      });
    }
    return () => {
      cancelled = true;
    };
  }, [asset.id, isImage]);

  const handleDownload = async () => {
    const url = downloadUrl ?? (await mediaApi.getAssetDownloadUrl(asset.id));
    const link = document.createElement("a");
    link.href = url;
    link.download = asset.filename;
    link.click();
  };

  return (
    <Card className="overflow-hidden">
      <div className="flex aspect-video items-center justify-center bg-muted">
        {isImage && downloadUrl ? (
          <img src={downloadUrl} alt={asset.caption ?? asset.filename} className="h-full w-full object-cover" />
        ) : (
          <ImageOff className="h-8 w-8 text-muted-foreground/50" />
        )}
      </div>
      <CardContent className="space-y-2 p-3">
        <p className="truncate text-sm font-medium" title={asset.filename}>
          {asset.filename}
        </p>
        <p className="text-xs text-muted-foreground">{formatBytes(asset.size_bytes)}</p>
        <Input
          placeholder="Add a caption..."
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          onBlur={() => {
            if (caption !== (asset.caption ?? "")) {
              updateCaption.mutate({ assetId: asset.id, caption: caption || null });
            }
          }}
          className="h-8 text-xs"
        />
        <div className="flex justify-end gap-1">
          <Button variant="ghost" size="icon" onClick={handleDownload} aria-label={`Download ${asset.filename}`}>
            <Download className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => deleteAsset.mutate(asset.id)}
            aria-label={`Delete ${asset.filename}`}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
