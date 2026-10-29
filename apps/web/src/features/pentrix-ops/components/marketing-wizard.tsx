import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type Campaign,
  type EmailPreview,
  type MarketingTemplate,
  type Selection,
  marketingApi,
  newSendKey,
  useMarketingOptions,
  useMarketingTemplates,
} from "@/features/pentrix-ops/api/marketing-api";
import { dayMonthIst } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";
import { selectClass } from "@/features/our-internships/components/letter-fields";

const STEPS = ["Recipients", "Template", "Preview template", "Final preview", "Confirm and send"] as const;

/** The email as a candidate will receive it. The HTML is shown in a sandboxed frame, so nothing in it can run. */
export function EmailFrame({ html, title }: { html: string; title: string }) {
  return <iframe title={title} sandbox="" srcDoc={html} className="h-[420px] w-full rounded-md border bg-white" />;
}

function Stepper({ step }: { step: number }) {
  return (
    <ol className="flex flex-wrap items-center gap-2 text-sm" aria-label="Steps">
      {STEPS.map((label, i) => (
        <li key={label} aria-current={i === step ? "step" : undefined} className={`flex items-center gap-1.5 ${i === step ? "font-medium text-foreground" : "text-muted-foreground"}`}>
          <span className={`flex h-5 w-5 items-center justify-center rounded-full border text-xs ${i < step ? "border-primary bg-primary text-primary-foreground" : i === step ? "border-primary" : ""}`}>
            {i < step ? <Check className="h-3 w-3" /> : i + 1}
          </span>
          {label}
          {i < STEPS.length - 1 && <span className="mx-1 text-muted-foreground/50">›</span>}
        </li>
      ))}
    </ol>
  );
}

interface Props {
  selection: Selection;
  onClose: () => void;
}

/**
 * Send a marketing email to the selected candidates. Five steps: who will receive it, which template, a preview of the template, a final
 * preview of exactly what will be sent, and an explicit confirmation. Nothing is sent until the last button; consent is checked by the
 * server both now and again when each message goes out.
 */
export function MarketingWizard({ selection, onClose }: Props) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [assignment, setAssignment] = useState<MarketingTemplate | null>(null);
  const [previewing, setPreviewing] = useState<MarketingTemplate | null>(null);
  const [brandId, setBrandId] = useState<string | null>(null);
  const [signatureId, setSignatureId] = useState<string | null>(null);
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [sent, setSent] = useState<Campaign | null>(null);
  const [campaignDate, setCampaignDate] = useState("");
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const sendKey = useRef(newSendKey());

  const recipients = useQuery({
    queryKey: ["pentrix-ops", "marketing", "wizard-recipients", selection, assignment?.id ?? ""],
    queryFn: () => marketingApi.previewRecipients(selection, assignment?.id),
  });
  const templates = useMarketingTemplates({ usable: true, on: campaignDate, category, q: search });
  const everyCategory = useMarketingTemplates({ usable: true });
  const categories = useMemo(() => [...new Set((everyCategory.data ?? []).map((t) => t.category))].sort(), [everyCategory.data]);
  const options = useMarketingOptions(step >= 3);

  const preview = useQuery({
    queryKey: ["pentrix-ops", "marketing", "wizard-preview", assignment?.id ?? "", brandId, signatureId, candidateId, selection],
    queryFn: () =>
      marketingApi.previewEmail({ assignment_id: (assignment as MarketingTemplate).id, selection, candidate_id: candidateId, brand_profile_id: brandId, signature_id: signatureId }),
    enabled: !!assignment && step >= 3,
  });
  const templatePreview = useQuery({
    queryKey: ["pentrix-ops", "marketing", "wizard-template-preview", previewing?.id ?? ""],
    queryFn: () => marketingApi.previewEmail({ assignment_id: (previewing as MarketingTemplate).id }),
    enabled: !!previewing && step === 2,
  });

  const send = useMutation({
    mutationFn: () =>
      marketingApi.send({
        assignment_id: (assignment as MarketingTemplate).id,
        selection,
        brand_profile_id: brandId ?? preview.data?.brand_profile_id ?? null,
        signature_id: signatureId ?? preview.data?.signature_id ?? null,
        expected_count: preview.data?.recipients?.eligible ?? 0,
        idempotency_key: sendKey.current,
      }),
    onSuccess: (campaign) => {
      setSent(campaign);
      void queryClient.invalidateQueries({ queryKey: ["pentrix-ops", "marketing"] });
    },
  });

  const eligible = recipients.data?.eligible ?? 0;
  const final: EmailPreview | undefined = preview.data;
  const blocked = !!final && (final.missing.length > 0 || final.warnings.some((w) => w.startsWith("Unsupported")));
  const people = final?.recipients?.people ?? recipients.data?.people ?? [];

  function choose(t: MarketingTemplate) {
    setAssignment(t);
    setBrandId(null);
    setSignatureId(null);
    setCandidateId(null);
    setConfirmed(false);
    send.reset();
    setStep(3);
  }

  if (sent) {
    return (
      <Dialog open onOpenChange={(open) => !open && onClose()}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Queued to send</DialogTitle>
            <DialogDescription>
              {sent.recipient_count} email{sent.recipient_count === 1 ? " is" : "s are"} queued for “{sent.campaign_name}”. They go out a few at a time and each person's consent is checked
              again just before theirs is sent.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Close</Button>
            <Button asChild><Link to="/pentrix-ops/marketing?tab=campaigns">Track it</Link></Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !send.isPending && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Send Marketing Email</DialogTitle>
          <DialogDescription>Nothing is sent until you confirm on the last step.</DialogDescription>
        </DialogHeader>
        <Stepper step={step} />

        {step === 0 && (
          <section className="space-y-4" aria-label="Recipients">
            {recipients.isLoading && <Skeleton className="h-32" />}
            {recipients.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(recipients.error, "Could not work out who would receive it.")}</p>}
            {recipients.data && (
              <>
                <p className="text-sm">
                  You selected <strong>{recipients.data.selected}</strong> candidate{recipients.data.selected === 1 ? "" : "s"}. <strong>{recipients.data.eligible}</strong> can be emailed.
                </p>
                {recipients.data.excluded.length > 0 && (
                  <div className="rounded-md border p-3">
                    <p className="text-sm font-medium">Left out ({recipients.data.excluded.reduce((n, e) => n + e.count, 0)})</p>
                    <ul className="mt-1 text-sm text-muted-foreground">
                      {recipients.data.excluded.map((e) => (
                        <li key={e.reason}>{e.count} · {e.label}</li>
                      ))}
                    </ul>
                    <p className="mt-2 text-xs text-muted-foreground">Only candidates who agreed to marketing email, have a verified address and have not unsubscribed are ever emailed.</p>
                  </div>
                )}
                {recipients.data.people.length > 0 && (
                  <>
                    <Table>
                      <TableHeader>
                        <TableRow><TableHead>Name</TableHead><TableHead>Email</TableHead></TableRow>
                      </TableHeader>
                      <TableBody>
                        {recipients.data.people.map((p) => (
                          <TableRow key={p.id}><TableCell>{p.name || "Candidate"}</TableCell><TableCell>{p.email}</TableCell></TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    {recipients.data.eligible > recipients.data.people_shown && (
                      <p className="text-xs text-muted-foreground">Showing the first {recipients.data.people_shown} of {recipients.data.eligible}.</p>
                    )}
                  </>
                )}
              </>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button disabled={eligible === 0} onClick={() => setStep(1)}>Choose a template</Button>
            </div>
          </section>
        )}

        {step === 1 && (
          <section className="space-y-4" aria-label="Template">
            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1">
                <Label htmlFor="mw-search">Search</Label>
                <Input id="mw-search" className="w-52" placeholder="Campaign or template" value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="mw-category">Category</Label>
                <select id="mw-category" className={`${selectClass} w-48`} value={category} onChange={(e) => setCategory(e.target.value)}>
                  <option value="">Any</option>
                  {categories.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="mw-date">Campaign date</Label>
                <Input id="mw-date" type="date" className="w-40" value={campaignDate} onChange={(e) => setCampaignDate(e.target.value)} />
              </div>
            </div>
            {templates.isLoading && <Skeleton className="h-24" />}
            {templates.data && templates.data.length === 0 && (
              <p className="rounded-md border p-4 text-sm text-muted-foreground">
                No template is available{campaignDate ? " on that date" : " today"}. Templates are made available under Pentrix → Marketing, from published Email Studio templates.
              </p>
            )}
            {templates.data && templates.data.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow><TableHead>Campaign</TableHead><TableHead>Category</TableHead><TableHead>Available</TableHead><TableHead>Last updated</TableHead><TableHead className="text-right"><span className="sr-only">Actions</span></TableHead></TableRow>
                </TableHeader>
                <TableBody>
                  {templates.data.map((t) => (
                    <TableRow key={t.id}>
                      <TableCell><div className="font-medium">{t.campaign_name}</div><div className="text-xs text-muted-foreground">{t.name} · {t.subject}</div></TableCell>
                      <TableCell>{t.category}</TableCell>
                      <TableCell className="text-sm">{t.available_from ? dayMonthIst(`${t.available_from}T12:00:00+05:30`) : "Any time"} – {t.available_until ? dayMonthIst(`${t.available_until}T12:00:00+05:30`) : "no end"}</TableCell>
                      <TableCell className="text-sm">{t.last_updated ? dayMonthIst(t.last_updated) : "—"}</TableCell>
                      <TableCell className="space-x-2 text-right">
                        <Button size="sm" variant="outline" aria-label={`Preview ${t.campaign_name}`} onClick={() => { setPreviewing(t); setStep(2); }}>Preview</Button>
                        <Button size="sm" aria-label={`Use ${t.campaign_name}`} onClick={() => choose(t)}>Use</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <div className="flex justify-between gap-2">
              <Button variant="outline" onClick={() => setStep(0)}>Back</Button>
              <Button variant="ghost" onClick={onClose}>Cancel</Button>
            </div>
          </section>
        )}

        {step === 2 && previewing && (
          <section className="space-y-3" aria-label="Preview template">
            <p className="text-sm text-muted-foreground">
              {previewing.campaign_name} with sample candidate details. Each recipient's own name and details replace the sample ones.
            </p>
            {templatePreview.isLoading && <Skeleton className="h-64" />}
            {templatePreview.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(templatePreview.error, "Could not preview this template.")}</p>}
            {templatePreview.data && (
              <>
                <p className="text-sm"><span className="text-muted-foreground">Subject: </span>{templatePreview.data.subject}</p>
                <EmailFrame html={templatePreview.data.html} title="Template preview" />
              </>
            )}
            <div className="flex justify-between gap-2">
              <Button variant="outline" onClick={() => { setPreviewing(null); setStep(1); }}>Back to templates</Button>
              <Button onClick={() => choose(previewing)}>Use this template</Button>
            </div>
          </section>
        )}

        {step === 3 && assignment && (
          <section className="space-y-4" aria-label="Final preview">
            {preview.isLoading && <Skeleton className="h-64" />}
            {preview.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(preview.error, "Could not build the preview.")}</p>}
            {final && (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor="mw-brand">Brand profile</Label>
                    <select id="mw-brand" className={`${selectClass} w-full`} value={brandId ?? final.brand_profile_id ?? ""} onChange={(e) => setBrandId(e.target.value || null)}>
                      {!final.brand_profile_id && <option value="">None</option>}
                      {options.data?.brands.map((b) => <option key={b.id} value={b.id}>{b.name}{b.is_default ? " (default)" : ""}</option>)}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="mw-signature">Signature</Label>
                    <select id="mw-signature" className={`${selectClass} w-full`} value={signatureId ?? final.signature_id ?? ""} onChange={(e) => setSignatureId(e.target.value || null)}>
                      <option value="">None</option>
                      {options.data?.signatures.map((s) => <option key={s.id} value={s.id}>{s.name}{s.is_default ? " (default)" : ""}</option>)}
                    </select>
                  </div>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="mw-as">Preview as</Label>
                  <select id="mw-as" className={`${selectClass} w-full max-w-sm`} value={candidateId ?? final.candidate?.id ?? ""} onChange={(e) => setCandidateId(e.target.value || null)}>
                    {people.map((p) => <option key={p.id} value={p.id}>{p.name || p.email} ({p.email})</option>)}
                  </select>
                </div>
                <dl className="grid gap-2 text-sm sm:grid-cols-2">
                  <div><dt className="text-muted-foreground">Subject</dt><dd className="font-medium">{final.subject}</dd></div>
                  <div><dt className="text-muted-foreground">Recipients</dt><dd className="font-medium">{final.recipients?.eligible ?? 0}</dd></div>
                  <div className="sm:col-span-2">
                    <dt className="text-muted-foreground">Attachments</dt>
                    <dd>{final.attachments.length === 0 ? "None" : final.attachments.map((a) => `${a.name} (${Math.round(a.size_bytes / 1024)} KB)`).join(", ")}</dd>
                  </div>
                </dl>
                {final.missing.length > 0 && <p role="alert" className="rounded-md border border-destructive/40 p-3 text-sm text-destructive">This email uses values that are missing: {final.missing.join(", ")}. Fix the template in Email Studio before sending.</p>}
                {final.warnings.length > 0 && <ul className="list-disc pl-5 text-sm text-amber-700 dark:text-amber-300">{final.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
                <EmailFrame html={final.html} title="Final preview" />
              </>
            )}
            <div className="flex justify-between gap-2">
              <Button variant="outline" onClick={() => setStep(1)}>Choose another template</Button>
              <Button disabled={!final || blocked || (final.recipients?.eligible ?? 0) === 0} onClick={() => setStep(4)}>Continue</Button>
            </div>
          </section>
        )}

        {step === 4 && assignment && final && (
          <section className="space-y-4" aria-label="Confirm and send">
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div><dt className="text-muted-foreground">Campaign</dt><dd className="font-medium">{assignment.campaign_name}</dd></div>
              <div><dt className="text-muted-foreground">Subject</dt><dd className="font-medium">{final.subject}</dd></div>
              <div><dt className="text-muted-foreground">Brand profile</dt><dd>{final.brand ?? "None"}</dd></div>
              <div><dt className="text-muted-foreground">Signature</dt><dd>{final.signature ?? "None"}</dd></div>
              <div><dt className="text-muted-foreground">Will be sent to</dt><dd className="font-medium">{final.recipients?.eligible ?? 0} people</dd></div>
              <div><dt className="text-muted-foreground">Left out</dt><dd>{(final.recipients?.excluded ?? []).reduce((n, e) => n + e.count, 0)}</dd></div>
            </dl>
            <p className="text-sm text-muted-foreground">
              Every email has an unsubscribe link. Emails go out about a minute apart in small batches, and each person's consent is checked again just before theirs is sent.
              Emails already sent cannot be taken back.
            </p>
            <label className="flex cursor-pointer items-start gap-2.5 text-sm">
              <input type="checkbox" className="mt-0.5" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
              <span>I have checked the preview and want to send this email to {final.recipients?.eligible ?? 0} people.</span>
            </label>
            {send.isError && (
              <p role="alert" className="rounded-md border border-destructive/40 p-3 text-sm text-destructive">
                {errorMessage(send.error, "Could not send.")}
                <Button variant="link" className="px-1" onClick={() => { send.reset(); void preview.refetch(); void recipients.refetch(); setConfirmed(false); setStep(3); }}>Review again</Button>
              </p>
            )}
            <div className="flex justify-between gap-2">
              <Button variant="outline" disabled={send.isPending} onClick={() => setStep(3)}>Back</Button>
              <Button disabled={!confirmed || send.isPending || blocked} onClick={() => send.mutate()}>
                {send.isPending ? "Sending…" : `Send to ${final.recipients?.eligible ?? 0} people`}
              </Button>
            </div>
          </section>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function TemplateBadge({ t }: { t: MarketingTemplate }) {
  if (t.usable) return <Badge variant="success">Available</Badge>;
  return <Badge variant="secondary">{t.problem ?? "Not available"}</Badge>;
}
