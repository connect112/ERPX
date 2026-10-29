import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type Campaign,
  type MarketingTemplate,
  marketingApi,
  useAssignableTemplates,
  useCampaign,
  useCampaignRecipients,
  useCampaigns,
  useMarketingTemplates,
} from "@/features/pentrix-ops/api/marketing-api";
import { EmailFrame, TemplateBadge } from "@/features/pentrix-ops/components/marketing-wizard";
import { dayMonthIst, istDateTime, usePentrixPermissions } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";
import { selectClass } from "@/features/our-internships/components/letter-fields";

const day = (value: string | null) => (value ? dayMonthIst(`${value}T12:00:00+05:30`) : "");
const refresh = ["pentrix-ops", "marketing"] as const;

function AssignDialog({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const assignable = useAssignableTemplates(true);
  const [templateId, setTemplateId] = useState("");
  const [name, setName] = useState("");
  const [from, setFrom] = useState("");
  const [until, setUntil] = useState("");
  const save = useMutation({
    mutationFn: () => marketingApi.assign({ template_id: templateId, campaign_name: name.trim(), available_from: from || null, available_until: until || null }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: refresh });
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Make a template available</DialogTitle>
          <DialogDescription>
            Choose a published Email Studio template for Pentrix marketing email, name the campaign and, if you like, the dates it can be used between. Design and edit
            templates in Email Studio.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <div className="space-y-1">
            <Label htmlFor="mk-template">Template</Label>
            <select id="mk-template" className={`${selectClass} w-full`} value={templateId} onChange={(e) => { setTemplateId(e.target.value); if (!name) setName(assignable.data?.find((t) => t.template_id === e.target.value)?.name ?? ""); }}>
              <option value="">Choose a published template…</option>
              {assignable.data?.map((t) => <option key={t.template_id} value={t.template_id}>{t.name} ({t.category})</option>)}
            </select>
            {assignable.data && assignable.data.length === 0 && <p className="text-xs text-muted-foreground">No published templates are free. Publish one in Email Studio first.</p>}
          </div>
          <div className="space-y-1">
            <Label htmlFor="mk-name">Campaign name</Label>
            <Input id="mk-name" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="mk-from">Available from</Label>
              <Input id="mk-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="mk-until">Available until</Label>
              <Input id="mk-until" type="date" min={from || undefined} value={until} onChange={(e) => setUntil(e.target.value)} />
            </div>
          </div>
          {save.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(save.error, "Could not save.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={!templateId || !name.trim() || save.isPending}>{save.isPending ? "Saving…" : "Make available"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditDialog({ item, onClose }: { item: MarketingTemplate; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(item.campaign_name);
  const [from, setFrom] = useState(item.available_from ?? "");
  const [until, setUntil] = useState(item.available_until ?? "");
  const [enabled, setEnabled] = useState(item.enabled);
  const save = useMutation({
    mutationFn: () => marketingApi.update(item.id, { campaign_name: name.trim(), available_from: from || null, available_until: until || null, enabled }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: refresh });
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{item.name}</DialogTitle>
          <DialogDescription>The wording and design are edited in Email Studio; here you choose when it can be sent.</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <div className="space-y-1">
            <Label htmlFor="me-name">Campaign name</Label>
            <Input id="me-name" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><Label htmlFor="me-from">Available from</Label><Input id="me-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></div>
            <div className="space-y-1"><Label htmlFor="me-until">Available until</Label><Input id="me-until" type="date" min={from || undefined} value={until} onChange={(e) => setUntil(e.target.value)} /></div>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Switched on</label>
          {save.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(save.error, "Could not save.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={!name.trim() || save.isPending}>{save.isPending ? "Saving…" : "Save"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PreviewDialog({ item, onClose }: { item: MarketingTemplate; onClose: () => void }) {
  const [preview, setPreview] = useState<{ subject: string; html: string } | null>(null);
  const load = useMutation({ mutationFn: () => marketingApi.previewEmail({ assignment_id: item.id }), onSuccess: setPreview });
  // eslint-disable-next-line react-hooks/exhaustive-deps -- loaded once when the dialog opens
  useEffect(() => load.mutate(), []);
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{item.campaign_name}</DialogTitle>
          <DialogDescription>With sample candidate details.</DialogDescription>
        </DialogHeader>
        {load.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(load.error, "Could not preview this template.")}</p>}
        {!preview && !load.isError && <Skeleton className="h-64" />}
        {preview && (
          <>
            <p className="text-sm"><span className="text-muted-foreground">Subject: </span>{preview.subject}</p>
            <EmailFrame html={preview.html} title="Template preview" />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function TemplatesTab() {
  const perms = usePentrixPermissions();
  const queryClient = useQueryClient();
  const templates = useMarketingTemplates();
  const [assigning, setAssigning] = useState(false);
  const [editing, setEditing] = useState<MarketingTemplate | null>(null);
  const [previewing, setPreviewing] = useState<MarketingTemplate | null>(null);
  const remove = useMutation({ mutationFn: marketingApi.remove, onSuccess: () => void queryClient.invalidateQueries({ queryKey: refresh }) });
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="text-base">Templates available for Pentrix marketing</CardTitle>
          <CardDescription>Only a published template, inside its dates and switched on, can be sent. Create and edit templates in Email Studio.</CardDescription>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline"><Link to="/administration/email-templates"><ExternalLink className="h-4 w-4" /> Email Studio</Link></Button>
          {perms.canManageMarketing && <Button onClick={() => setAssigning(true)}>Make a template available</Button>}
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {templates.isLoading && <Skeleton className="m-6 h-24" />}
        {templates.isError && <p role="alert" className="p-6 text-sm text-destructive">{errorMessage(templates.error, "Could not load the templates.")}</p>}
        {templates.data && templates.data.length === 0 && <p className="p-8 text-center text-sm text-muted-foreground">No template has been made available yet.</p>}
        {remove.isError && <p role="alert" className="px-6 pb-3 text-sm text-destructive">{errorMessage(remove.error, "Could not remove it.")}</p>}
        {templates.data && templates.data.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign</TableHead><TableHead>Category</TableHead><TableHead>Available</TableHead><TableHead>Last updated</TableHead><TableHead>Status</TableHead>
                <TableHead className="text-right"><span className="sr-only">Actions</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {templates.data.map((t) => (
                <TableRow key={t.id}>
                  <TableCell><div className="font-medium">{t.campaign_name}</div><div className="text-xs text-muted-foreground">{t.name}{t.subject ? ` · ${t.subject}` : ""}</div></TableCell>
                  <TableCell>{t.category}</TableCell>
                  <TableCell className="text-sm">{t.available_from ? day(t.available_from) : "Any time"} – {t.available_until ? day(t.available_until) : "no end"}</TableCell>
                  <TableCell className="text-sm">{t.last_updated ? dayMonthIst(t.last_updated) : "—"}</TableCell>
                  <TableCell><TemplateBadge t={t} /></TableCell>
                  <TableCell className="space-x-2 text-right">
                    {t.published && <Button size="sm" variant="outline" disabled={!perms.canSendMarketing} title={perms.canSendMarketing ? undefined : "Needs permission to send marketing email"} onClick={() => setPreviewing(t)}>Preview</Button>}
                    {perms.canManageMarketing && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => setEditing(t)}>Edit</Button>
                        <Button size="sm" variant="ghost" disabled={remove.isPending} aria-label={`Remove ${t.campaign_name}`} onClick={() => remove.mutate(t.id)}>Remove</Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      {assigning && <AssignDialog onClose={() => setAssigning(false)} />}
      {editing && <EditDialog item={editing} onClose={() => setEditing(null)} />}
      {previewing && <PreviewDialog item={previewing} onClose={() => setPreviewing(null)} />}
    </Card>
  );
}

const CAMPAIGN_TONE: Record<Campaign["status"], "info" | "success" | "secondary"> = { sending: "info", completed: "success", cancelled: "secondary" };
const COUNT_LABELS: [string, string][] = [["queued", "Queued"], ["sending", "Sending"], ["sent", "Sent"], ["delivered", "Delivered"], ["failed", "Failed"], ["bounced", "Bounced"], ["skipped", "Skipped"]];

function CampaignDetail({ id }: { id: string }) {
  const perms = usePentrixPermissions();
  const queryClient = useQueryClient();
  const campaign = useCampaign(id);
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const recipients = useCampaignRecipients(id, status, page);
  const cancel = useMutation({ mutationFn: () => marketingApi.cancel(id), onSuccess: () => void queryClient.invalidateQueries({ queryKey: refresh }) });
  const c = campaign.data;
  const pages = recipients.data ? Math.max(Math.ceil(recipients.data.total / recipients.data.page_size), 1) : 1;
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="text-base">{c?.campaign_name ?? "Campaign"}</CardTitle>
          <CardDescription>{c ? `${c.subject} · started ${istDateTime(c.confirmed_at)}` : ""}</CardDescription>
        </div>
        {c?.status === "sending" && perms.canSendMarketing && (
          <Button variant="outline" size="sm" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancel what is not yet sent</Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {cancel.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(cancel.error, "Could not cancel.")}</p>}
        {c && (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
              {COUNT_LABELS.map(([key, label]) => (
                <div key={key} className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="text-xl font-semibold tabular-nums">{c.counts[key] ?? 0}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Sent means the mail server accepted the message. Delivered and bounced counts need delivery reports from the mail provider, which ERPX does not receive at the moment, so they
              stay at 0.
            </p>
            {Object.keys(c.excluded).length > 0 && (
              <div className="text-sm">
                <p className="font-medium">Left out when this was confirmed</p>
                <ul className="text-muted-foreground">{Object.entries(c.excluded).map(([k, v]) => <li key={k}>{v} · {k}</li>)}</ul>
              </div>
            )}
          </>
        )}
        <div className="flex items-end gap-3">
          <div className="space-y-1">
            <Label htmlFor="cr-status">Show</Label>
            <select id="cr-status" className={`${selectClass} w-40`} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">Everyone</option>
              {COUNT_LABELS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </div>
        </div>
        {recipients.isLoading && <Skeleton className="h-24" />}
        {recipients.data && (
          <Table>
            <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Status</TableHead><TableHead>Sent</TableHead><TableHead>Note</TableHead></TableRow></TableHeader>
            <TableBody>
              {recipients.data.items.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.name || "Candidate"}</TableCell><TableCell>{r.email}</TableCell>
                  <TableCell><Badge variant={r.status === "sent" || r.status === "delivered" ? "success" : r.status === "failed" || r.status === "bounced" ? "destructive" : "secondary"}>{r.status}</Badge></TableCell>
                  <TableCell className="text-sm">{r.sent_at ? istDateTime(r.sent_at) : "—"}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{r.error ?? ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {recipients.data && recipients.data.total > recipients.data.page_size && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Page {page} of {pages}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CampaignsTab() {
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const campaigns = useCampaigns(page);
  const data = campaigns.data;
  const pages = data ? Math.max(Math.ceil(data.total / data.page_size), 1) : 1;
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader><CardTitle className="text-base">Campaigns sent</CardTitle><CardDescription>Every confirmed send, and how each message ended.</CardDescription></CardHeader>
        <CardContent className="p-0">
          {campaigns.isLoading && <Skeleton className="m-6 h-24" />}
          {campaigns.isError && <p role="alert" className="p-6 text-sm text-destructive">{errorMessage(campaigns.error, "Could not load the campaigns.")}</p>}
          {data && data.items.length === 0 && <p className="p-8 text-center text-sm text-muted-foreground">Nothing has been sent yet. Choose candidates in Registrations and use Send Marketing Email.</p>}
          {data && data.items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow><TableHead>Campaign</TableHead><TableHead>Status</TableHead><TableHead>Recipients</TableHead><TableHead>Sent</TableHead><TableHead>Queued</TableHead><TableHead>Failed</TableHead><TableHead>Skipped</TableHead><TableHead>Started</TableHead><TableHead className="text-right"><span className="sr-only">Open</span></TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((c) => (
                  <TableRow key={c.id} data-state={open === c.id ? "selected" : undefined}>
                    <TableCell><div className="font-medium">{c.campaign_name}</div><div className="text-xs text-muted-foreground">{c.subject}</div></TableCell>
                    <TableCell><Badge variant={CAMPAIGN_TONE[c.status]}>{c.status}</Badge></TableCell>
                    <TableCell className="tabular-nums">{c.recipient_count}</TableCell>
                    <TableCell className="tabular-nums">{c.counts.sent ?? 0}</TableCell>
                    <TableCell className="tabular-nums">{(c.counts.queued ?? 0) + (c.counts.sending ?? 0)}</TableCell>
                    <TableCell className="tabular-nums">{c.counts.failed ?? 0}</TableCell>
                    <TableCell className="tabular-nums">{c.counts.skipped ?? 0}</TableCell>
                    <TableCell className="whitespace-nowrap text-sm">{istDateTime(c.confirmed_at)}</TableCell>
                    <TableCell className="text-right"><Button size="sm" variant="outline" aria-label={`Open ${c.campaign_name}`} onClick={() => setOpen(open === c.id ? null : c.id)}>{open === c.id ? "Close" : "Open"}</Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {data && data.total > data.page_size && (
            <div className="flex items-center justify-between border-t px-6 py-3 text-sm">
              <span className="text-muted-foreground">Page {page} of {pages}</span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
                <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      {open && <CampaignDetail key={open} id={open} />}
    </div>
  );
}

/** Pentrix marketing email: which Email Studio templates may be used and when, and the campaigns that have been sent. */
export function MarketingPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "campaigns" ? "campaigns" : "templates";
  const perms = usePentrixPermissions();
  const choose = (next: "templates" | "campaigns") => setParams(next === "templates" ? new URLSearchParams() : new URLSearchParams({ tab: next }), { replace: true });
  const cls = (active: boolean) => `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${active ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`;
  return (
    <div className="space-y-5 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Pentrix Marketing</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Updates and offers for Pentrix candidates, designed in Email Studio and sent only to people who agreed to receive them. Choose recipients in{" "}
          {perms.canRegistrations ? <Link className="text-primary hover:underline" to="/pentrix-ops/registrations">Registrations</Link> : "Registrations"}. Booking, payment and account emails are separate and never
          depend on this.
        </p>
      </div>
      <nav aria-label="Marketing views" className="inline-flex gap-1 rounded-md bg-muted p-1">
        <button type="button" className={cls(tab === "templates")} aria-current={tab === "templates" ? "page" : undefined} onClick={() => choose("templates")}>Templates</button>
        <button type="button" className={cls(tab === "campaigns")} aria-current={tab === "campaigns" ? "page" : undefined} onClick={() => choose("campaigns")}>Campaigns</button>
      </nav>
      {tab === "templates" ? <TemplatesTab /> : <CampaignsTab />}
    </div>
  );
}
