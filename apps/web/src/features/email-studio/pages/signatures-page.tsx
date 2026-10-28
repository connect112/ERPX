import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Copy, Pencil, Plus, Trash2, Upload } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { type Signature, type SignaturePayload, studioApi, studioKeys, useSignatures } from "@/features/email-studio/api/studio-api";
import { useStudioPermissions } from "@/features/email-studio/lib/permissions";
import { errorMessage } from "@/features/institutions/lib/format";
import { CheckField, SelectField, TextField } from "@/features/our-internships/components/letter-fields";

const BLANK: SignaturePayload = {
  name: "", scope: "company", person_name: "", designation: "", company_name: "", email: "", phone: "", website: "", logo_asset_id: null, signature_asset_id: null, style: {}, is_default: false,
};

function Block({ s }: { s: Pick<Signature, "person_name" | "designation" | "company_name" | "email" | "phone" | "website" | "style" | "signature_image_url" | "logo_url" | "signature_approved"> }) {
  return (
    <div className="rounded-md border bg-white p-3 text-gray-900" style={{ color: s.style.color, fontSize: s.style.font_size, textAlign: s.style.align }}>
      {s.signature_image_url && s.signature_approved && <img src={s.signature_image_url} alt="Approved signature" className="mb-1 h-12 object-contain" />}
      {s.person_name && <div className="font-bold">{s.person_name}</div>}
      {s.designation && <div>{s.designation}</div>}
      {s.company_name && <div>{s.company_name}</div>}
      {(s.email || s.phone) && <div>{[s.email, s.phone].filter(Boolean).join(" | ")}</div>}
      {s.website && <div className="text-blue-700">{s.website}</div>}
      {s.logo_url && <img src={s.logo_url} alt="Logo" className="mt-2 h-8 object-contain" />}
    </div>
  );
}

/** Reusable signatures. A handwritten-signature image is only ever one an administrator uploaded and approved; nothing is drawn for you. */
export function SignaturesPage() {
  const sigs = useSignatures();
  const perms = useStudioPermissions();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Signature | "new" | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: studioKeys.signatures });
  const act = useMutation({ mutationFn: async (job: () => Promise<unknown>) => job(), onSuccess: refresh });
  if (sigs.isLoading) return <Skeleton className="h-48 w-full" />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Create company or personal signatures, choose one for a template, and place it with {"{{signature}}"}. A signature image appears in emails only after it is approved.
        </p>
        <Button disabled={!perms.canManage} onClick={() => setEditing("new")}>
          <Plus className="h-4 w-4" /> New signature
        </Button>
      </div>
      {act.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(act.error, "Could not do that.")}</p>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {sigs.data?.map((s) => (
          <div key={s.id} className="space-y-3 rounded-lg border p-4">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium">{s.name}</p>
              <Badge variant="outline">{s.scope === "company" ? "Company" : "Individual"}</Badge>
              {s.is_default && <Badge variant="info">Default</Badge>}
              {s.signature_asset_id && (s.signature_approved ? <Badge variant="success">Image approved</Badge> : <Badge variant="warning">Image not approved</Badge>)}
            </div>
            <Block s={s} />
            <div className="flex flex-wrap gap-1">
              <Button size="sm" variant="outline" disabled={!perms.canManage} onClick={() => setEditing(s)}>
                <Pencil className="h-3.5 w-3.5" /> Edit
              </Button>
              <Button size="sm" variant="ghost" aria-label={`Duplicate ${s.name}`} disabled={!perms.canManage || act.isPending} onClick={() => act.mutate(() => studioApi.saveSignature({ ...s, name: `${s.name} (copy)`, is_default: false, signature_asset_id: null }))}>
                <Copy className="h-3.5 w-3.5" />
              </Button>
              {!s.is_default && (
                <Button size="sm" variant="ghost" disabled={!perms.canManage || act.isPending} onClick={() => act.mutate(() => studioApi.saveSignature({ ...s, is_default: true }, s.id))}>
                  Set default
                </Button>
              )}
              {s.signature_asset_id && (
                <Button size="sm" variant="ghost" disabled={!perms.canPublish || act.isPending} title={perms.canPublish ? undefined : "You need permission to publish email templates"} onClick={() => act.mutate(() => studioApi.approveSignature(s.id, !s.signature_approved))}>
                  <BadgeCheck className="h-3.5 w-3.5" /> {s.signature_approved ? "Withdraw approval" : "Approve image"}
                </Button>
              )}
              <Button size="sm" variant="ghost" aria-label={`Delete ${s.name}`} disabled={!perms.canManage || act.isPending} onClick={() => { if (window.confirm(`Delete the signature "${s.name}"?`)) act.mutate(() => studioApi.deleteSignature(s.id)); }}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        ))}
        {sigs.data?.length === 0 && <p className="rounded-md border p-8 text-center text-sm text-muted-foreground md:col-span-2 xl:col-span-3">No signatures yet.</p>}
      </div>
      {editing && <SignatureDialog signature={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function SignatureDialog({ signature, onClose }: { signature: Signature | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SignaturePayload>(signature ? { ...BLANK, ...signature } : BLANK);
  const [images, setImages] = useState({ signature: signature?.signature_image_url ?? null, logo: signature?.logo_url ?? null });
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof SignaturePayload>(key: K, value: SignaturePayload[K]) => setForm((f) => ({ ...f, [key]: value }));
  const save = useMutation({
    mutationFn: () => studioApi.saveSignature(form, signature?.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studioKeys.signatures });
      onClose();
    },
  });
  const upload = async (file: File | undefined, field: "signature" | "logo") => {
    if (!file) return;
    try {
      const asset = await studioApi.uploadAsset(file, "image");
      set(field === "signature" ? "signature_asset_id" : "logo_asset_id", asset.id);
      setImages((i) => ({ ...i, [field]: asset.url }));
      setError(null);
    } catch (e) {
      setError(errorMessage(e, "Could not upload that image."));
    }
  };
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{signature ? `Edit ${signature.name}` : "New signature"}</DialogTitle>
          <DialogDescription>Use a signature image only if you are authorised to; it must be approved before emails show it.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="sg-name" label="Signature name" value={form.name} onChange={(v) => set("name", v)} maxLength={120} />
          <SelectField id="sg-scope" label="Kind" value={form.scope} onChange={(v) => set("scope", v)} options={[{ value: "company", label: "Company" }, { value: "individual", label: "Individual signatory" }]} />
          <TextField id="sg-person" label="Person name" value={form.person_name} onChange={(v) => set("person_name", v)} />
          <TextField id="sg-desig" label="Designation" value={form.designation} onChange={(v) => set("designation", v)} />
          <TextField id="sg-company" label="Company name" value={form.company_name} onChange={(v) => set("company_name", v)} />
          <TextField id="sg-email" label="Email" value={form.email} onChange={(v) => set("email", v)} />
          <TextField id="sg-phone" label="Phone" value={form.phone} onChange={(v) => set("phone", v)} />
          <TextField id="sg-site" label="Website" value={form.website} placeholder="https://" onChange={(v) => set("website", v)} />
          <div className="space-y-1.5">
            <span className="text-sm font-medium">Logo</span>
            <div className="flex items-center gap-2">
              {images.logo && <img src={images.logo} alt="Logo" className="h-8 object-contain" />}
              <label className="inline-flex cursor-pointer items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-muted">
                <Upload className="h-3.5 w-3.5" /> Upload
                <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" className="sr-only" onChange={(e) => { void upload(e.target.files?.[0], "logo"); e.target.value = ""; }} />
              </label>
            </div>
          </div>
          <div className="space-y-1.5">
            <span className="text-sm font-medium">Approved signature image (optional)</span>
            <div className="flex items-center gap-2">
              {images.signature && <img src={images.signature} alt="Signature" className="h-10 object-contain" />}
              <label className="inline-flex cursor-pointer items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-muted">
                <Upload className="h-3.5 w-3.5" /> Upload
                <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" className="sr-only" onChange={(e) => { void upload(e.target.files?.[0], "signature"); e.target.value = ""; }} />
              </label>
            </div>
            <p className="text-xs text-muted-foreground">A new image has to be approved again before it appears in emails.</p>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:col-span-2">
            <label className="space-y-1 text-sm">
              Text colour
              <input type="color" className="block h-9 w-full cursor-pointer rounded-md border bg-background p-1" value={form.style.color ?? "#111827"} onChange={(e) => set("style", { ...form.style, color: e.target.value })} />
            </label>
            <label className="space-y-1 text-sm">
              Text size
              <input type="number" min={10} max={22} className="block h-9 w-full rounded-md border bg-background px-2" value={form.style.font_size ?? 14} onChange={(e) => set("style", { ...form.style, font_size: Number(e.target.value) })} />
            </label>
            <label className="space-y-1 text-sm">
              Alignment
              <select className="block h-9 w-full rounded-md border bg-background px-2" value={form.style.align ?? "left"} onChange={(e) => set("style", { ...form.style, align: e.target.value as "left" | "center" | "right" })}>
                <option value="left">Left</option>
                <option value="center">Centre</option>
                <option value="right">Right</option>
              </select>
            </label>
          </div>
          <div className="sm:col-span-2">
            <CheckField id="sg-default" label="Use as the default signature" checked={form.is_default} onChange={(v) => set("is_default", v)} />
          </div>
          <div className="sm:col-span-2">
            <p className="mb-1 text-sm font-medium">Preview</p>
            <Block s={{ ...form, signature_image_url: images.signature, logo_url: images.logo, signature_approved: !!signature?.signature_approved && form.signature_asset_id === signature?.signature_asset_id }} />
          </div>
        </div>
        {(error || save.isError) && <p role="alert" className="text-sm text-destructive">{error ?? errorMessage(save.error, "Could not save the signature.")}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button disabled={!form.name.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving..." : "Save signature"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
