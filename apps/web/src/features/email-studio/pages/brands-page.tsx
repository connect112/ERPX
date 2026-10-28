import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2, Upload } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { type Brand, type BrandPayload, studioApi, studioKeys, useBrands } from "@/features/email-studio/api/studio-api";
import { useStudioPermissions } from "@/features/email-studio/lib/permissions";
import { errorMessage } from "@/features/institutions/lib/format";
import { CheckField, ColorField, TextField } from "@/features/our-internships/components/letter-fields";

const BLANK: BrandPayload = {
  name: "", company_name: "", logo_asset_id: null, primary_color: "#2563eb", secondary_color: "#1e40af", accent_color: "#f59e0b", background_color: "#f4f4f5",
  text_color: "#111827", website: "", contact_email: "", phone: "", address: "", tagline: "", social_links: [], from_name: "", reply_to: "", is_default: false,
};

/** The brands ERPX sends email as: logo, colours, contact details, and the sender's name. One of them is the default. */
export function BrandsPage() {
  const brands = useBrands();
  const perms = useStudioPermissions();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Brand | "new" | null>(null);
  const remove = useMutation({
    mutationFn: (id: string) => studioApi.deleteBrand(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: studioKeys.brands }),
  });
  if (brands.isLoading) return <Skeleton className="h-48 w-full" />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted-foreground">
          A brand profile fills a template with its colours, logo and contact details. Changing a brand affects emails sent from now on; emails already sent never change.
        </p>
        <Button disabled={!perms.canManage} onClick={() => setEditing("new")}>
          <Plus className="h-4 w-4" /> New brand
        </Button>
      </div>
      {remove.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(remove.error, "Could not delete the brand.")}</p>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {brands.data?.map((b) => (
          <div key={b.id} className="space-y-3 rounded-lg border p-4">
            <div className="flex items-center gap-3">
              {b.logo_url ? <img src={b.logo_url} alt={`${b.name} logo`} className="h-10 w-10 rounded object-contain" /> : <div className="h-10 w-10 rounded" style={{ backgroundColor: b.primary_color }} aria-hidden="true" />}
              <div className="min-w-0">
                <p className="truncate font-medium">{b.name}</p>
                <p className="truncate text-xs text-muted-foreground">{b.company_name || "No company name"}</p>
              </div>
              {b.is_default && <Badge variant="info" className="ml-auto">Default</Badge>}
            </div>
            <div className="flex gap-1" aria-label="Brand colours">
              {[b.primary_color, b.secondary_color, b.accent_color, b.background_color, b.text_color].map((c, i) => (
                <span key={i} className="h-5 w-8 rounded border" style={{ backgroundColor: c }} title={c} />
              ))}
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={!perms.canManage} onClick={() => setEditing(b)}>
                <Pencil className="h-3.5 w-3.5" /> Edit
              </Button>
              <Button size="sm" variant="ghost" aria-label={`Delete ${b.name}`} disabled={!perms.canManage || remove.isPending} onClick={() => { if (window.confirm(`Delete the brand "${b.name}"?`)) remove.mutate(b.id); }}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        ))}
        {brands.data?.length === 0 && <p className="rounded-md border p-8 text-center text-sm text-muted-foreground md:col-span-2 xl:col-span-3">No brand profiles yet. Create one to give your emails a logo and colours.</p>}
      </div>
      {editing && <BrandDialog brand={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function BrandDialog({ brand, onClose }: { brand: Brand | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<BrandPayload>(brand ? { ...BLANK, ...brand } : BLANK);
  const [logoUrl, setLogoUrl] = useState<string | null>(brand?.logo_url ?? null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const set = <K extends keyof BrandPayload>(key: K, value: BrandPayload[K]) => setForm((f) => ({ ...f, [key]: value }));
  const save = useMutation({
    mutationFn: () => studioApi.saveBrand(form, brand?.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studioKeys.brands });
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{brand ? `Edit ${brand.name}` : "New brand profile"}</DialogTitle>
          <DialogDescription>The sender's address stays the one your mail provider is set up for; here you choose the name people see and where replies go.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="br-name" label="Brand name" value={form.name} onChange={(v) => set("name", v)} maxLength={120} />
          <TextField id="br-company" label="Company name" value={form.company_name} onChange={(v) => set("company_name", v)} maxLength={200} />
          <div className="space-y-1.5 sm:col-span-2">
            <span className="text-sm font-medium">Company logo</span>
            <div className="flex items-center gap-3">
              {logoUrl && <img src={logoUrl} alt="Logo" className="h-12 max-w-[10rem] object-contain" />}
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted">
                <Upload className="h-4 w-4" /> {logoUrl ? "Replace" : "Upload"} logo
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/gif,image/webp"
                  className="sr-only"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (!file) return;
                    try {
                      const asset = await studioApi.uploadAsset(file, "image");
                      set("logo_asset_id", asset.id);
                      setLogoUrl(asset.url);
                      setUploadError(null);
                    } catch (error) {
                      setUploadError(errorMessage(error, "Could not upload that image."));
                    }
                  }}
                />
              </label>
              {logoUrl && <Button type="button" variant="ghost" size="sm" onClick={() => { set("logo_asset_id", null); setLogoUrl(null); }}>Remove</Button>}
            </div>
            <p className="text-xs text-muted-foreground">PNG, JPG, GIF or WebP up to 2 MB. Email clients cannot show SVG.</p>
            {uploadError && <p role="alert" className="text-sm text-destructive">{uploadError}</p>}
          </div>
          <ColorField id="br-primary" label="Primary colour" value={form.primary_color} onChange={(v) => set("primary_color", v)} />
          <ColorField id="br-secondary" label="Secondary colour" value={form.secondary_color} onChange={(v) => set("secondary_color", v)} />
          <ColorField id="br-accent" label="Accent colour" value={form.accent_color} onChange={(v) => set("accent_color", v)} />
          <ColorField id="br-bg" label="Background colour" value={form.background_color} onChange={(v) => set("background_color", v)} />
          <ColorField id="br-text" label="Text colour" value={form.text_color} onChange={(v) => set("text_color", v)} />
          <TextField id="br-tagline" label="Tagline" value={form.tagline} onChange={(v) => set("tagline", v)} maxLength={200} />
          <TextField id="br-site" label="Website" value={form.website} placeholder="https://" onChange={(v) => set("website", v)} />
          <TextField id="br-email" label="Contact email" value={form.contact_email} onChange={(v) => set("contact_email", v)} />
          <TextField id="br-phone" label="Phone" value={form.phone} onChange={(v) => set("phone", v)} />
          <TextField id="br-address" label="Address" value={form.address} onChange={(v) => set("address", v)} maxLength={500} />
          <TextField id="br-from" label="Sender name" hint="What recipients see as the sender." value={form.from_name} onChange={(v) => set("from_name", v)} maxLength={120} />
          <TextField id="br-reply" label="Reply-to address" hint="Where replies go." value={form.reply_to} onChange={(v) => set("reply_to", v)} />
          <div className="space-y-2 sm:col-span-2">
            <span className="text-sm font-medium">Social links</span>
            {form.social_links.map((s, i) => (
              <div key={i} className="flex gap-2">
                <input aria-label={`Social link ${i + 1} label`} className="w-32 rounded-md border bg-background px-2 py-1.5 text-sm" placeholder="LinkedIn" value={s.label} onChange={(e) => set("social_links", form.social_links.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} />
                <input aria-label={`Social link ${i + 1} address`} className="min-w-0 flex-1 rounded-md border bg-background px-2 py-1.5 text-sm" placeholder="https://" value={s.url} onChange={(e) => set("social_links", form.social_links.map((x, j) => (j === i ? { ...x, url: e.target.value } : x)))} />
                <Button type="button" size="icon" variant="ghost" aria-label={`Remove social link ${i + 1}`} onClick={() => set("social_links", form.social_links.filter((_, j) => j !== i))}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
            <Button type="button" size="sm" variant="outline" disabled={form.social_links.length >= 10} onClick={() => set("social_links", [...form.social_links, { label: "", url: "" }])}>
              <Plus className="h-3.5 w-3.5" /> Add a link
            </Button>
          </div>
          <div className="sm:col-span-2">
            <CheckField id="br-default" label="Use as the default brand" checked={form.is_default} onChange={(v) => set("is_default", v)} />
          </div>
        </div>
        {save.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(save.error, "Could not save the brand.")}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button disabled={!form.name.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving..." : "Save brand"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
