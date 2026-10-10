import { Copy, ExternalLink } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { FunnelRow, FunnelStage, Placement, TrackedLink } from "@/features/social-media/api/social-media-api";
import { useCreateLink, useFunnel, useLeadOptions, useLinks, useSocialLeads, useUpdateLink } from "@/features/social-media/api/social-media-hooks";
import { errorMessage, formatInZone } from "@/features/social-media/lib/format";
import { formatDay, formatNumber } from "@/features/social-media/lib/numbers";
import { safeHref } from "@/features/social-media/lib/links";

const NATIVE_SELECT = "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";
const ZONE = "Asia/Kolkata";
const PLACEMENTS: Record<Placement, string> = { bio: "Profile bio", post: "Post caption", story: "Story", dm: "Direct message", comment: "Comment reply", other: "Somewhere else" };
const STEPS: { key: keyof FunnelStage; label: string }[] = [
  { key: "leads", label: "Leads linked" },
  { key: "contacted", label: "Contacted" },
  { key: "qualified", label: "Qualified" },
  { key: "applied", label: "Applied" },
  { key: "enrolled", label: "Enrolled" },
];
const ORIGIN_LABEL: Record<string, string> = { comment: "Comment", message: "Direct message", link: "Tracked link", manual: "Added by hand" };
const FOLLOW_LABEL = { none: "No follow-up set", scheduled: "Follow-up set", overdue: "Follow-up overdue", closed: "Closed" } as const;
const FOLLOW_VARIANT = { none: "outline", scheduled: "secondary", overdue: "destructive", closed: "outline" } as const;

function Stages({ stage }: { stage: FunnelStage }) {
  const max = Math.max(1, stage.leads);
  return (
    <ol className="space-y-2" aria-label="How far the linked leads got">
      {STEPS.map(({ key, label }) => (
        <li key={key} className="space-y-0.5">
          <div className="flex justify-between text-sm">
            <span>{label}</span>
            <span className="font-medium">{formatNumber(stage[key])}</span>
          </div>
          <div className="h-2 rounded bg-muted">
            <div className="h-2 rounded bg-primary" style={{ width: `${(stage[key] / max) * 100}%` }} />
          </div>
        </li>
      ))}
      {stage.lost > 0 && <li className="text-xs text-muted-foreground">{stage.lost} lead(s) were marked lost in the CRM.</li>}
    </ol>
  );
}

function RowsTable({ rows, first, showOpens }: { rows: FunnelRow[]; first: string; showOpens?: boolean }) {
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">Nothing linked yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr>
            <th className="py-2 pr-3 font-medium">{first}</th>
            {showOpens && <th className="py-2 pr-3 font-medium">Opens</th>}
            <th className="py-2 pr-3 font-medium">Leads</th>
            <th className="py-2 pr-3 font-medium">Contacted</th>
            <th className="py-2 pr-3 font-medium">Qualified</th>
            <th className="py-2 pr-3 font-medium">Applied</th>
            <th className="py-2 pr-3 font-medium">Enrolled</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.label}-${i}`} className="border-t">
              <td className="max-w-[240px] truncate py-2 pr-3 font-medium">
                {ORIGIN_LABEL[r.label] ?? r.label}
                {r.permalink && (
                  <a href={safeHref(r.permalink)} target="_blank" rel="noopener noreferrer" aria-label="Open on Instagram" className="ml-1 inline-block align-middle">
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </td>
              {showOpens && <td className="py-2 pr-3">{formatNumber(r.opens ?? 0)}</td>}
              <td className="py-2 pr-3">{r.leads}</td>
              <td className="py-2 pr-3">{r.contacted}</td>
              <td className="py-2 pr-3">{r.qualified}</td>
              <td className="py-2 pr-3">{r.applied}</td>
              <td className="py-2 pr-3">{r.enrolled}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LinkDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateLink();
  const options = useLeadOptions(true);
  const [name, setName] = useState("");
  const [destination, setDestination] = useState("https://");
  const [placement, setPlacement] = useState<Placement>("bio");
  const [course, setCourse] = useState("");
  const [campaign, setCampaign] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit() {
    setError(null);
    create.mutate(
      { name, destination: destination.trim(), placement, course_label: course.trim() || undefined, marketing_campaign_id: campaign || undefined },
      { onSuccess: onClose, onError: (e) => setError(errorMessage(e, "Couldn't create the link.")) },
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New tracked link</DialogTitle>
          <DialogDescription>A short address that counts opens and sends people on to your website with UTM parameters, so the website&apos;s own analytics can see where visits came from. It doesn&apos;t identify anyone.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="space-y-1">
            <Label htmlFor="link-name">Name</Label>
            <Input id="link-name" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} placeholder="Bio link: SOC course" />
          </div>
          <div className="space-y-1">
            <Label htmlFor="link-dest">Where it goes</Label>
            <Input id="link-dest" type="url" maxLength={500} value={destination} onChange={(e) => setDestination(e.target.value)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="link-place">Where you will use it</Label>
              <select id="link-place" className={NATIVE_SELECT} value={placement} onChange={(e) => setPlacement(e.target.value as Placement)}>
                {Object.entries(PLACEMENTS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="link-campaign">Marketing campaign (optional)</Label>
              <select id="link-campaign" className={NATIVE_SELECT} value={campaign} onChange={(e) => setCampaign(e.target.value)}>
                <option value="">None</option>
                {options.data?.campaigns.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="link-course">Course it is about (optional)</Label>
            <Input id="link-course" maxLength={255} value={course} onChange={(e) => setCourse(e.target.value)} />
          </div>
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={create.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={create.isPending || !name.trim() || destination.trim().length < 9}>
            {create.isPending ? "Creating…" : "Create link"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function LinkCard({ link, canManage }: { link: TrackedLink; canManage: boolean }) {
  const update = useUpdateLink();
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function copy() {
    try {
      await navigator.clipboard.writeText(link.short_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Couldn't copy. Select the address and copy it by hand.");
    }
  }

  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-medium">{link.name}</p>
            <p className="text-xs text-muted-foreground">
              {PLACEMENTS[link.placement]}
              {link.course_label ? ` · ${link.course_label}` : ""}
            </p>
          </div>
          <Badge variant={link.is_active ? "success" : "secondary"}>{link.is_active ? "Active" : "Paused"}</Badge>
        </div>
        <p className="break-all rounded bg-muted/40 p-2 font-mono text-xs" data-testid="short-url">
          {link.short_url}
        </p>
        <p className="break-all text-xs text-muted-foreground">Goes to: {link.final_url}</p>
        <p className="text-sm">
          <span className="font-medium">{formatNumber(link.clicks_28d)}</span> opens in the last 28 days, {formatNumber(link.clicks_total)} in all
          {link.last_click_day ? `, last on ${formatDay(link.last_click_day)}` : ""}
        </p>
        {error && (
          <p role="alert" className="text-xs text-destructive">
            {error}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={copy}>
            <Copy className="mr-1 h-3.5 w-3.5" />
            {copied ? "Copied" : "Copy address"}
          </Button>
          {canManage && (
            <Button size="sm" variant="outline" disabled={update.isPending} onClick={() => update.mutate({ id: link.id, payload: { is_active: !link.is_active } }, { onError: (e) => setError(errorMessage(e, "That didn't work.")) })}>
              {link.is_active ? "Pause" : "Resume"}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function SocialLeads() {
  const leads = useSocialLeads(true);
  if (leads.isLoading) return <Skeleton className="h-24 w-full" />;
  if (leads.isError) return <p className="text-sm text-destructive">Couldn&apos;t load the leads.</p>;
  const items = leads.data?.items ?? [];
  if (items.length === 0) return <p className="text-sm text-muted-foreground">No leads have been created from Comments or Messages yet. Open a comment or conversation and choose Create lead when it is a genuine enquiry.</p>;
  return (
    <ul className="space-y-2">
      {items.map((l) => (
        <li key={l.lead_id} className="rounded-md border p-3 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <Link className="font-medium text-primary hover:underline" to={`/crm/leads/${l.lead_id}`}>
                {l.name}
              </Link>
              <span className="text-xs text-muted-foreground">
                {" "}
                · @{l.handle ?? "unknown"} · {l.course ?? "course not recorded"} · {l.status}
              </span>
            </div>
            <div className="flex flex-wrap gap-1">
              {l.needs_first_contact && <Badge variant="warning">Needs a first contact</Badge>}
              <Badge variant={FOLLOW_VARIANT[l.follow_up]}>{FOLLOW_LABEL[l.follow_up]}</Badge>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Linked {formatInZone(l.created_at, ZONE)}
            {l.assigned_to ? ` · assigned to ${l.assigned_to}` : " · not assigned"}
            {l.next_follow_up_at ? ` · next follow-up ${formatInZone(l.next_follow_up_at, ZONE)}` : ""}
          </p>
          <p className="text-xs text-muted-foreground">{l.basis}</p>
        </li>
      ))}
    </ul>
  );
}

/** Enquiries that became CRM leads (by a person), tracked links, and how far those leads got, without claiming credit. */
export function LeadsTab() {
  const [days, setDays] = useState(28);
  const [creating, setCreating] = useState(false);
  const funnel = useFunnel(days);
  const links = useLinks();
  const me = useMyRoles();
  const permissions = me.data?.effective_permissions ?? [];
  const isSuper = me.data?.is_superuser ?? false;
  const canManage = isSuper || permissions.includes("social_media.manage");
  const canSeeLeads = isSuper || permissions.includes("crm.leads.view");
  const data = funnel.data;
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        Not every comment is a lead. A team member decides, in Comments or Messages, which ones are genuine enquiries and creates the lead in the CRM. This page shows what happened to those leads. It never says a post caused an enrolment.
      </p>

      <div className="flex items-center gap-1" role="group" aria-label="Period">
        {[7, 28, 90].map((d) => (
          <Button key={d} size="sm" variant={days === d ? "default" : "outline"} onClick={() => setDays(d)}>
            Last {d} days
          </Button>
        ))}
      </div>

      {funnel.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : funnel.isError || !data ? (
        <p className="text-sm text-destructive">Couldn&apos;t load the report.</p>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Enquiries seen</CardTitle>
                <CardDescription>
                  {formatDay(data.period.start)} to {formatDay(data.period.end)}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p>
                  Comments labelled as enquiries: <span className="text-2xl font-semibold">{data.enquiries_seen.comments}</span>. Conversations: <span className="text-2xl font-semibold">{data.enquiries_seen.messages}</span>.
                </p>
                <p className="text-xs text-muted-foreground">{data.enquiries_seen.note}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Leads linked by the team</CardTitle>
                <CardDescription>As each lead stands in the CRM today.</CardDescription>
              </CardHeader>
              <CardContent>
                <Stages stage={data.linked} />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">By post</CardTitle>
              <CardDescription>Leads a team member created from comments on each post.</CardDescription>
            </CardHeader>
            <CardContent>
              <RowsTable rows={data.by_post} first="Post" />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">By tracked link</CardTitle>
              <CardDescription>Opens are visits, not people, and aren&apos;t matched to leads. Leads appear here only when the team member said the person used that link.</CardDescription>
            </CardHeader>
            <CardContent>
              <RowsTable rows={data.by_link} first="Link" showOpens />
            </CardContent>
          </Card>
          <div className="grid gap-3 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">By course of interest</CardTitle>
              </CardHeader>
              <CardContent>
                <RowsTable rows={data.by_course} first="Course" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">By where it came from</CardTitle>
              </CardHeader>
              <CardContent>
                <RowsTable rows={data.by_origin} first="Origin" />
              </CardContent>
            </Card>
          </div>
          <div className="rounded-md border p-3">
            <p className="mb-1 text-sm font-medium">What these numbers do and don&apos;t mean</p>
            <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
              {data.assumptions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </div>
        </>
      )}

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Tracked links</h2>
          {canManage && <Button size="sm" onClick={() => setCreating(true)}>New tracked link</Button>}
        </div>
        {links.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : (links.data ?? []).length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">No tracked links yet. Make one for your bio or a post to see how many people open it.</CardContent>
          </Card>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {links.data?.map((l) => (
              <LinkCard key={l.id} link={l} canManage={canManage} />
            ))}
          </div>
        )}
      </div>

      {canSeeLeads && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Leads from social media</h2>
          <SocialLeads />
        </div>
      )}
      {creating && <LinkDialog onClose={() => setCreating(false)} />}
    </div>
  );
}
