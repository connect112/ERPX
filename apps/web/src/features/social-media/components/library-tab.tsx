import { Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { Asset } from "@/features/social-media/api/social-media-api";
import { useAssets, useDeleteAsset, useUploadAsset, useUseAsLogo } from "@/features/social-media/api/social-media-hooks";
import { errorMessage } from "@/features/social-media/lib/format";

const NATIVE_SELECT =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";
const KIND_LABEL: Record<Asset["kind"], string> = { logo: "Logo", photo: "Photo", screenshot: "Screenshot", background: "AI background" };

function Thumb({ asset, onDelete, onUseAsLogo, canManage, busy }: { asset: Asset; onDelete: (a: Asset) => void; onUseAsLogo: (a: Asset) => void; canManage: boolean; busy: boolean }) {
  return (
    <Card>
      <CardContent className="space-y-2 p-3">
        <div className="flex aspect-square items-center justify-center overflow-hidden rounded-md border bg-muted">
          {asset.url ? (
            <img src={asset.url} alt={asset.alt_text || asset.filename} className="max-h-full max-w-full object-contain" loading="lazy" />
          ) : (
            <span className="text-xs text-muted-foreground">No preview</span>
          )}
        </div>
        <p className="truncate text-sm font-medium" title={asset.filename}>
          {asset.filename}
        </p>
        <div className="flex flex-wrap gap-1">
          <Badge variant="secondary">{KIND_LABEL[asset.kind]}</Badge>
          {asset.is_logo && <Badge variant="success">Approved logo</Badge>}
          {asset.synthetic && <Badge variant="warning">AI-made, not real</Badge>}
        </div>
        <p className="text-xs text-muted-foreground">
          {asset.width}×{asset.height}
        </p>
        {canManage && (
          <div className="flex flex-wrap gap-1.5">
            {asset.kind === "logo" && !asset.is_logo && (
              <Button size="sm" disabled={busy} onClick={() => onUseAsLogo(asset)}>
                Use as the logo
              </Button>
            )}
            <Button size="sm" variant="outline" disabled={busy} onClick={() => onDelete(asset)} aria-label={`Delete ${asset.filename}`}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** The approved logo and the pictures artwork can use. Everything uploaded is checked and re-encoded on the server. */
export function LibraryTab() {
  const assets = useAssets();
  const upload = useUploadAsset();
  const remove = useDeleteAsset();
  const useLogo = useUseAsLogo();
  const me = useMyRoles();
  const canManage = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.manage");
  const fileRef = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState("photo");
  const [alt, setAlt] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const logo = assets.data?.find((a) => a.is_logo);
  const busy = upload.isPending || remove.isPending || useLogo.isPending;

  function submit() {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setMessage({ ok: false, text: "Choose a file first." });
      return;
    }
    setMessage(null);
    upload.mutate(
      { file, kind, altText: alt },
      {
        onSuccess: () => {
          setMessage({ ok: true, text: kind === "logo" ? "Uploaded. Press “Use as the logo” to make it the approved logo." : "Uploaded." });
          setAlt("");
          if (fileRef.current) fileRef.current.value = "";
        },
        onError: (e) => setMessage({ ok: false, text: errorMessage(e, "Couldn't upload that file.") }),
      },
    );
  }

  function del(asset: Asset) {
    if (!window.confirm(`Delete "${asset.filename}"? This can't be undone.`)) return;
    setMessage(null);
    remove.mutate(asset.id, { onError: (e) => setMessage({ ok: false, text: errorMessage(e, "Couldn't delete it.") }) });
  }

  function makeLogo(asset: Asset) {
    setMessage(null);
    useLogo.mutate(asset.id, {
      onSuccess: () => setMessage({ ok: true, text: "This is now the approved logo. New artwork uses it." }),
      onError: (e) => setMessage({ ok: false, text: errorMessage(e, "Couldn't set the logo.") }),
    });
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Approved logo</CardTitle>
          <CardDescription>Artwork uses this exact file. It is only ever scaled, never redrawn. Upload a PNG with a transparent background if you can.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm">
          {assets.isLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : logo ? (
            <div className="flex items-center gap-4">
              {logo.url && <img src={logo.url} alt="The approved logo" className="h-16 w-auto max-w-[8rem] rounded border bg-white object-contain p-1" />}
              <span>
                {logo.filename} ({logo.width}×{logo.height})
              </span>
            </div>
          ) : (
            <p className="text-muted-foreground">No approved logo yet. Artwork is made without one until you upload it below (kind: Logo) and press “Use as the logo”.</p>
          )}
        </CardContent>
      </Card>

      {canManage && (
        <Card>
          <CardHeader>
            <CardTitle>Upload an image</CardTitle>
            <CardDescription>PNG, JPEG or WebP, up to 8 MB. Use real photographs and real lab screenshots where you have them. SVG isn&apos;t supported.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="lib-file">File</Label>
              <Input id="lib-file" ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lib-kind">What is it?</Label>
              <select id="lib-kind" className={NATIVE_SELECT} value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="photo">A photograph</option>
                <option value="screenshot">A real screenshot (for example from a lab)</option>
                <option value="logo">A logo</option>
              </select>
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="lib-alt">Description for people who can&apos;t see it (alt text)</Label>
              <Input id="lib-alt" value={alt} maxLength={420} onChange={(e) => setAlt(e.target.value)} />
            </div>
            <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
              <Button onClick={submit} disabled={upload.isPending}>
                <Upload className="mr-1 h-4 w-4" /> {upload.isPending ? "Uploading..." : "Upload"}
              </Button>
              {message && (
                <span role={message.ok ? "status" : "alert"} className={message.ok ? "text-sm text-emerald-700" : "text-sm text-destructive"}>
                  {message.text}
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {assets.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : assets.isError ? (
        <p className="text-sm text-destructive">Couldn&apos;t load the library.</p>
      ) : assets.data && assets.data.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">Nothing uploaded yet.</CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {assets.data?.map((asset) => (
            <Thumb key={asset.id} asset={asset} onDelete={del} onUseAsLogo={makeLogo} canManage={canManage} busy={busy} />
          ))}
        </div>
      )}
    </div>
  );
}
