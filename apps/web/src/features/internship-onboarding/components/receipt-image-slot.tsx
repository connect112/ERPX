import { useMutation } from "@tanstack/react-query";
import { Trash2, Upload } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/features/institutions/lib/format";
import { type AssetKind, type ImageSlot, type ReceiptAssetInfo, receiptsApi } from "@/features/internship-onboarding/receipts-api";

export const MAX_IMAGE_BYTES = 2 * 1024 * 1024;

interface Props {
  internshipId: string;
  kind: AssetKind;
  label: string;
  slot: ImageSlot;
  assets: ReceiptAssetInfo[];
  canEdit: boolean;
  onChange: (patch: Partial<ImageSlot>) => void;
  /** The image that was just uploaded (already chosen for this slot): the designer adds it to its list without reloading anything. */
  onUploaded: (asset: ReceiptAssetInfo) => void;
  /** Offer the alignment choice (the logo). */
  alignable?: boolean;
}

/** A thumbnail of a stored image, fetched with the staff member's own login and released when it is replaced or the panel closes. The box has
 *  a fixed size from the start, so the layout does not move when the picture arrives. */
export function AssetThumb({ internshipId, assetId, alt }: { internshipId: string; assetId: string; alt: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    let made: string | null = null;
    setUrl(null);
    receiptsApi
      .assetImage(internshipId, assetId)
      .then((blob) => {
        if (cancelled) return;
        made = URL.createObjectURL(blob);
        setUrl(made);
      })
      .catch(() => !cancelled && setUrl(null));
    return () => {
      cancelled = true;
      if (made) URL.revokeObjectURL(made);
    };
  }, [internshipId, assetId]);
  return (
    <div className="flex h-16 w-28 shrink-0 items-center justify-center rounded border bg-white p-1">
      {url ? <img src={url} alt={alt} className="max-h-full max-w-full object-contain" /> : <span className="h-8 w-16 rounded bg-muted" aria-hidden />}
    </div>
  );
}

export function ReceiptImageSlot({ internshipId, kind, label, slot, assets, canEdit, onChange, onUploaded, alignable }: Props) {
  const [problem, setProblem] = useState<string | null>(null);
  const mine = assets.filter((a) => a.kind === kind);
  const upload = useMutation({
    mutationFn: (file: File) => receiptsApi.uploadAsset(internshipId, kind, file),
    onSuccess: (asset) => {
      setProblem(null);
      onChange({ asset_id: asset.id, show: true }); // the new image is chosen for this slot straight away
      onUploaded(asset);
    },
    onError: (e) => setProblem(errorMessage(e, "The image could not be uploaded.")),
  });
  const choose = (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_IMAGE_BYTES) return setProblem("The image is larger than 2 MB.");
    if (!["image/png", "image/jpeg"].includes(file.type)) return setProblem("Upload a PNG or JPG image.");
    setProblem(null);
    upload.mutate(file);
  };

  return (
    <fieldset className="space-y-2 rounded-md border p-3" disabled={!canEdit}>
      <legend className="px-1 text-sm font-medium">{label}</legend>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={slot.show} onChange={(e) => onChange({ show: e.target.checked })} />
        Show on the document
      </label>
      <div className="flex flex-wrap items-center gap-3">
        {slot.asset_id ? <AssetThumb internshipId={internshipId} assetId={slot.asset_id} alt={`${label} in use`} /> : <span className="text-xs text-muted-foreground">No image chosen.</span>}
        {canEdit && (
          <>
            {/* "relative": the hidden file input is positioned inside this label. Without it the input is placed against the whole window, far below the
                page, and gives the document thousands of pixels of blank scrolling. */}
            <label className="relative inline-flex cursor-pointer items-center gap-1 text-sm text-primary">
              <Upload className="h-4 w-4" />
              {slot.asset_id ? "Upload another" : "Upload"} (PNG or JPG, up to 2 MB)
              <input
                type="file"
                className="sr-only"
                aria-label={`Upload ${label}`}
                accept="image/png,image/jpeg"
                disabled={upload.isPending}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  choose(file);
                }}
              />
            </label>
            {slot.asset_id && (
              <Button type="button" size="sm" variant="ghost" aria-label={`Remove ${label}`} onClick={() => onChange({ asset_id: null })}>
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </>
        )}
      </div>
      {mine.length >= 1 && canEdit && (
        <select
          aria-label={`Use a saved ${label.toLowerCase()}`}
          className="w-full rounded-md border bg-background px-2 py-1 text-sm"
          value={slot.asset_id ?? ""}
          onChange={(e) => onChange({ asset_id: e.target.value || null, show: e.target.value ? true : slot.show })}
        >
          <option value="">Choose a saved image…</option>
          {mine.map((a) => (
            <option key={a.id} value={a.id}>
              {a.filename} ({a.width_px}×{a.height_px})
            </option>
          ))}
        </select>
      )}
      <div className="grid grid-cols-2 gap-2">
        {(["width_mm", "height_mm"] as const).map((k) => (
          <label key={k} className="space-y-1 text-xs text-muted-foreground">
            {k === "width_mm" ? "Largest width (mm)" : "Largest height (mm)"}
            <Input type="number" min={6} max={80} value={slot[k]} onChange={(e) => onChange({ [k]: Number(e.target.value) || slot[k] })} />
          </label>
        ))}
      </div>
      {alignable && (
        <label className="block space-y-1 text-xs text-muted-foreground">
          Alignment
          <select aria-label={`${label} alignment`} className="w-full rounded-md border bg-background px-2 py-1 text-sm" value={slot.align} onChange={(e) => onChange({ align: e.target.value as ImageSlot["align"] })}>
            <option value="auto">Follow the header alignment</option>
            <option value="left">Left</option>
            <option value="center">Centre</option>
            <option value="right">Right</option>
          </select>
        </label>
      )}
      <p className="min-h-4 text-xs text-muted-foreground" aria-live="polite">
        {upload.isPending ? "Uploading…" : ""}
      </p>
      {problem && (
        <p className="text-xs text-destructive" role="alert">
          {problem}
        </p>
      )}
    </fieldset>
  );
}
