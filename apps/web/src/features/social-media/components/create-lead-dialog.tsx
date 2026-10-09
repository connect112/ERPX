import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { LeadCreated, LeadPayload } from "@/features/social-media/api/social-media-api";
import { useCreateLead, useLeadHint, useLeadOptions, useLinks } from "@/features/social-media/api/social-media-hooks";
import { errorMessage } from "@/features/social-media/lib/format";

const NATIVE_SELECT = "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";

export interface LeadTarget {
  kind: "comment" | "dm";
  id: string;
  handle: string;
}

function DialogBody({ target, onClose }: { target: LeadTarget; onClose: () => void }) {
  const hint = useLeadHint(target.kind, target.id);
  const options = useLeadOptions(true);
  const links = useLinks();
  const create = useCreateLead(target.kind);
  const me = useMyRoles();
  const [name, setName] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [courseId, setCourseId] = useState<string | null>(null);
  const [courseLabel, setCourseLabel] = useState("");
  const [note, setNote] = useState("");
  const [assignee, setAssignee] = useState("");
  const [linkId, setLinkId] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [followUp, setFollowUp] = useState(false);
  const [followType, setFollowType] = useState<"call" | "email" | "meeting" | "other">("call");
  const [followAt, setFollowAt] = useState("");
  const [followNotes, setFollowNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<LeadCreated | null>(null);

  const permissions = me.data?.effective_permissions ?? [];
  const canFollowUp = (me.data?.is_superuser ?? false) || permissions.includes("crm.followups.manage");
  const suggestion = hint.data?.suggested_course ?? null;
  const chosenCourse = courseId ?? "";
  const shownName = name ?? hint.data?.default_name ?? "";

  function submit() {
    setError(null);
    const payload: LeadPayload = {
      full_name: shownName,
      phone: phone.trim() || undefined,
      email: email.trim() || undefined,
      course_id: chosenCourse || undefined,
      course_label: !chosenCourse && courseLabel.trim() ? courseLabel.trim() : undefined,
      note: note.trim() || undefined,
      assigned_to_user_id: assignee || undefined,
      link_id: linkId || undefined,
      marketing_campaign_id: campaignId || undefined,
      follow_up: followUp && followAt ? { type: followType, scheduled_at: new Date(followAt).toISOString(), notes: followNotes.trim() || undefined } : undefined,
    };
    create.mutate({ id: target.id, payload }, { onSuccess: setDone, onError: (e) => setError(errorMessage(e, "Couldn't create the lead.")) });
  }

  if (hint.isLoading || options.isLoading) return <Skeleton className="h-40 w-full" />;
  if (hint.data?.existing_lead_id && !done) {
    return (
      <div className="space-y-3 text-sm">
        <p>A lead was already created from this {target.kind === "comment" ? "comment" : "conversation"}.</p>
        <Link className="text-primary underline" to={`/crm/leads/${hint.data.existing_lead_id}`} onClick={onClose}>
          Open it in the CRM
        </Link>
      </div>
    );
  }
  if (done) {
    return (
      <div className="space-y-3 text-sm">
        <p role="status" className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-emerald-900">
          The lead was created in the CRM{done.follow_up_id ? " with a follow-up reminder for the team" : ""}.
        </p>
        {done.warnings.map((w) => (
          <p key={w} role="alert" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900">
            {w}
          </p>
        ))}
        <p className="text-xs text-muted-foreground">{done.basis}</p>
        <Link className="text-primary underline" to={`/crm/leads/${done.lead_id}`} onClick={onClose}>
          Open it in the CRM
        </Link>
      </div>
    );
  }
  return (
    <div className="space-y-3 text-sm">
      <p className="rounded-md bg-muted/40 p-3 text-xs text-muted-foreground">
        Only create a lead for a genuine enquiry. ERPX keeps the handle @{target.handle}, the course and your note. Add a phone number or email only if the person gave you one: it is never taken from Instagram. The words of a message are not copied into the CRM.
      </p>
      <div className="space-y-1">
        <Label htmlFor="lead-name">Name</Label>
        <Input id="lead-name" maxLength={255} value={shownName} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="lead-phone">Phone (optional)</Label>
          <Input id="lead-phone" inputMode="tel" maxLength={32} value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="lead-email">Email (optional)</Label>
          <Input id="lead-email" type="email" maxLength={255} value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
      </div>
      <div className="space-y-1">
        <Label htmlFor="lead-course">Course they are interested in</Label>
        {suggestion && courseId === null && (
          <p className="text-xs text-muted-foreground">
            Their words mention &ldquo;{suggestion.matched.join(", ")}&rdquo;, which looks like {suggestion.title}.{" "}
            <button type="button" className="text-primary underline" onClick={() => setCourseId(suggestion.course_id)}>
              Use {suggestion.title}
            </button>{" "}
            (only a suggestion: you decide)
          </p>
        )}
        <select id="lead-course" className={NATIVE_SELECT} value={chosenCourse} onChange={(e) => setCourseId(e.target.value)}>
          <option value="">Not sure / other</option>
          {options.data?.courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
            </option>
          ))}
        </select>
        {!chosenCourse && <Input aria-label="Course, in your words" placeholder="Course, in your words (optional)" maxLength={255} value={courseLabel} onChange={(e) => setCourseLabel(e.target.value)} />}
      </div>
      <div className="space-y-1">
        <Label htmlFor="lead-note">Note for the team (optional)</Label>
        <Textarea id="lead-note" rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="lead-assignee">Assign to (optional)</Label>
          <select id="lead-assignee" className={NATIVE_SELECT} value={assignee} onChange={(e) => setAssignee(e.target.value)}>
            <option value="">Nobody yet</option>
            {options.data?.team.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="lead-campaign">Marketing campaign (optional)</Label>
          <select id="lead-campaign" className={NATIVE_SELECT} value={campaignId} onChange={(e) => setCampaignId(e.target.value)}>
            <option value="">None</option>
            {options.data?.campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      {(links.data?.length ?? 0) > 0 && (
        <div className="space-y-1">
          <Label htmlFor="lead-link">They told you they used this tracked link (optional)</Label>
          <select id="lead-link" className={NATIVE_SELECT} value={linkId} onChange={(e) => setLinkId(e.target.value)}>
            <option value="">No / don&apos;t know</option>
            {links.data?.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </div>
      )}
      {canFollowUp && (
        <div className="space-y-2 rounded-md border p-3">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={followUp} onChange={(e) => setFollowUp(e.target.checked)} />
            <span>Set a follow-up reminder for the team</span>
          </label>
          {followUp && (
            <div className="grid gap-2 sm:grid-cols-2">
              <select aria-label="Follow-up type" className={NATIVE_SELECT} value={followType} onChange={(e) => setFollowType(e.target.value as typeof followType)}>
                <option value="call">Call</option>
                <option value="email">Email</option>
                <option value="meeting">Meeting</option>
                <option value="other">Other</option>
              </select>
              <Input aria-label="Follow-up time" type="datetime-local" value={followAt} onChange={(e) => setFollowAt(e.target.value)} />
              <Input className="sm:col-span-2" aria-label="Follow-up note" placeholder="What to do (optional)" maxLength={500} value={followNotes} onChange={(e) => setFollowNotes(e.target.value)} />
              <p className="text-xs text-muted-foreground sm:col-span-2">This is a reminder for your team. It doesn&apos;t send the person anything.</p>
            </div>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <DialogFooter>
        <Button variant="outline" onClick={onClose} disabled={create.isPending}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={create.isPending || !shownName.trim() || (followUp && !followAt)}>
          {create.isPending ? "Creating…" : "Create lead"}
        </Button>
      </DialogFooter>
    </div>
  );
}

/** A person decides this is a genuine enquiry and creates the CRM lead. Nothing here is automatic. */
export function CreateLeadDialog({ target, onClose }: { target: LeadTarget | null; onClose: () => void }) {
  if (!target) return null;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Create a lead</DialogTitle>
          <DialogDescription>Add this person to the CRM as a lead from social media.</DialogDescription>
        </DialogHeader>
        <DialogBody target={target} onClose={onClose} />
      </DialogContent>
    </Dialog>
  );
}
