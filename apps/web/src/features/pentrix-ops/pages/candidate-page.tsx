import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Pencil } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { type Candidate, type CandidateDetail, candidatesApi, useCandidateDetail } from "@/features/pentrix-ops/api/candidates-api";
import { EMPTY_PAYMENT_FILTERS, usePayments } from "@/features/pentrix-ops/api/payments-api";
import { InvoiceButtons } from "@/features/pentrix-ops/components/payment-parts";
import { pentrixKeys } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { AssessmentRecordView } from "@/features/pentrix-ops/components/assessment-record";
import { AssessmentBadge, BookingBadge, PaymentBadge, QualificationBadge } from "@/features/pentrix-ops/components/candidate-badges";
import { PAYMENT_LABEL, PAYMENT_TONE, STATUS_TONE, dayMonthIst, istDate, istDateTime, istTime, rupees, usePentrixPermissions } from "@/features/pentrix-ops/lib/format";
import type { BookingStatus } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { errorMessage } from "@/features/institutions/lib/format";

const words = (value: string) => value.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">{children}</dd>
    </div>
  );
}

function EditDialog({ candidate, onClose }: { candidate: Candidate; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(candidate.full_name);
  const [phone, setPhone] = useState(candidate.phone ?? "");
  const save = useMutation({
    mutationFn: () => candidatesApi.edit(candidate.id, { full_name: name.trim(), phone: phone.trim() || null }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pentrixKeys.all });
      onClose();
    },
  });
  const unchanged = name.trim() === candidate.full_name && phone.trim() === (candidate.phone ?? "");
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Edit candidate</DialogTitle>
          <DialogDescription>
            Saved in Pentrix, so the candidate sees it too, and recorded with your name. The email address is how they sign in and cannot be changed here.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="cand-name">Full name</Label>
            <Input id="cand-name" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="cand-phone">Phone number</Label>
            <Input id="cand-phone" type="tel" value={phone} maxLength={24} placeholder="+91 98765 43210" onChange={(e) => setPhone(e.target.value)} />
          </div>
          {save.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(save.error, "Could not save the changes.")}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={save.isPending || unchanged || !name.trim()}>{save.isPending ? "Saving…" : "Save"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Registration({ detail }: { detail: CandidateDetail }) {
  const c = detail.candidate;
  const reg = detail.profile?.registration;
  const enrollment = detail.profile?.enrollment;
  return (
    <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
      <Fact label="Full name">{c.full_name}</Fact>
      <Fact label="Email">
        {c.email} {c.email_verified ? <Badge variant="success">Verified</Badge> : <Badge variant="warning">Not verified</Badge>}
      </Fact>
      <Fact label="Phone">{c.phone ?? <span className="text-muted-foreground">Not provided</span>}</Fact>
      <Fact label="Registered">{istDateTime(c.registered_at)}</Fact>
      <Fact label="Signs in with">{reg ? (reg.sign_in === "google" ? "Google" : "Email and password") : "—"}</Fact>
      <Fact label="Terms and privacy accepted">
        {reg ? (reg.terms_accepted_at ? `${dayMonthIst(reg.terms_accepted_at)} (terms ${reg.terms_version ?? "—"}, privacy ${reg.privacy_version ?? "—"})` : "Not on record") : "—"}
      </Fact>
      <Fact label="Assessment"><AssessmentBadge assessment={c.assessment} /></Fact>
      <Fact label="Qualification"><QualificationBadge qualified={c.assessment.qualified} /></Fact>
      <Fact label="Booking"><BookingBadge booking={c.booking} /></Fact>
      <Fact label="Payment"><PaymentBadge payment={c.payment} /></Fact>
      <Fact label="Program">
        {enrollment ? `${words(enrollment.status)}${enrollment.current_module ? ` · ${enrollment.current_module}` : ""}` : <span className="text-muted-foreground">Not enrolled</span>}
      </Fact>
    </dl>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-md border p-6 text-center text-sm text-muted-foreground">{children}</p>;
}

/** One candidate: registration, assessment, bookings, payments and invoices, the emails sent to them, and a record of changes made from ERPX. */
export function CandidatePage() {
  const { id = "" } = useParams();
  const perms = usePentrixPermissions();
  const detail = useCandidateDetail(id);
  const [editing, setEditing] = useState(false);
  const data = detail.data;
  const profile = data?.profile ?? null;
  // ERPX's own copy of this candidate's payments, which is where invoices can be viewed and downloaded.
  const records = usePayments({ ...EMPTY_PAYMENT_FILTERS, candidate: data?.candidate.pentrix_user_id }, 50, perms.canPayments && !!data);
  const recordFor = (pentrixPaymentId: string) => records.data?.items.find((r) => r.pentrix_payment_id === pentrixPaymentId);

  useEffect(() => setEditing(false), [id]);

  return (
    <div className="space-y-5 p-8">
      <Link to="/pentrix-ops/registrations" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> All registrations
      </Link>
      {detail.isLoading && <Skeleton className="h-64" />}
      {detail.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(detail.error, "Could not load this candidate.")}</p>}
      {data && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">{data.candidate.full_name || "Candidate"}</h1>
              <p className="mt-1 text-sm text-muted-foreground">{data.candidate.email}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <QualificationBadge qualified={data.candidate.assessment.qualified} />
              <PaymentBadge payment={data.candidate.payment} />
              {perms.canEditRegistrations && (
                <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                  <Pencil className="h-4 w-4" /> Edit
                </Button>
              )}
            </div>
          </div>

          {!data.live && (
            <p role="status" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
              {data.error ?? "Pentrix could not be reached."} Showing the summary ERPX holds; the full record (attempts, bookings, payments) will appear when Pentrix is reachable.
            </p>
          )}

          <Tabs defaultValue="registration">
            <TabsList className="flex-wrap h-auto">
              <TabsTrigger value="registration">Registration</TabsTrigger>
              <TabsTrigger value="assessment">Assessment</TabsTrigger>
              <TabsTrigger value="bookings">Bookings{profile ? ` (${profile.bookings.length})` : ""}</TabsTrigger>
              <TabsTrigger value="payments">Payments and invoices{profile ? ` (${profile.payments.length})` : ""}</TabsTrigger>
              <TabsTrigger value="emails">Emails ({data.emails.length})</TabsTrigger>
              <TabsTrigger value="activity">Changes{profile ? ` (${profile.activity.length})` : ""}</TabsTrigger>
            </TabsList>

            <Card className="mt-3">
              <CardContent className="p-6">
                <TabsContent value="registration" className="mt-0"><Registration detail={data} /></TabsContent>

                <TabsContent value="assessment" className="mt-0">
                  {profile ? <AssessmentRecordView record={profile.assessment} /> : <Empty>The assessment record needs Pentrix to be reachable.</Empty>}
                </TabsContent>

                <TabsContent value="bookings" className="mt-0">
                  {!profile ? (
                    <Empty>The booking history needs Pentrix to be reachable.</Empty>
                  ) : profile.bookings.length === 0 ? (
                    <Empty>No appointments have been booked.</Empty>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Reference</TableHead>
                          <TableHead>When (IST)</TableHead>
                          <TableHead>Assigned to</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Meeting</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {profile.bookings.map((b) => (
                          <TableRow key={b.id}>
                            <TableCell className="font-mono text-xs">{b.reference ?? "—"}</TableCell>
                            <TableCell>
                              <div>{istDate(b.slot_start)}</div>
                              <div className="text-xs text-muted-foreground">{istTime(b.slot_start)} · {b.duration_minutes} min{b.reschedule_count ? ` · moved ${b.reschedule_count}×` : ""}</div>
                            </TableCell>
                            <TableCell>{b.assigned_staff_name ?? <span className="text-muted-foreground">Not assigned</span>}</TableCell>
                            <TableCell><Badge variant={STATUS_TONE[b.status as BookingStatus] ?? "secondary"}>{words(b.status)}</Badge></TableCell>
                            <TableCell>
                              {b.meeting_url ? <a className="text-primary hover:underline" href={b.meeting_url} target="_blank" rel="noopener noreferrer">Link</a> : <span className="text-muted-foreground">None</span>}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </TabsContent>

                <TabsContent value="payments" className="mt-0">
                  {!profile ? (
                    <Empty>The payment history needs Pentrix to be reachable.</Empty>
                  ) : profile.payments.length === 0 ? (
                    <Empty>No payments have been started.</Empty>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Date</TableHead>
                          <TableHead>For</TableHead>
                          <TableHead>Amount</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Transaction reference</TableHead>
                          <TableHead>Invoice</TableHead>
                          {perms.canPayments && <TableHead><span className="sr-only">Invoice file</span></TableHead>}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {profile.payments.map((p) => (
                          <TableRow key={p.id}>
                            <TableCell>{p.created_at ? dayMonthIst(p.created_at) : "—"}</TableCell>
                            <TableCell>{words(p.purpose)}</TableCell>
                            <TableCell>{rupees(p.amount_paise, p.currency)}</TableCell>
                            <TableCell>
                              <Badge variant={PAYMENT_TONE[p.status === "succeeded" ? "paid" : p.status === "created" ? "pending" : p.status] ?? "secondary"}>
                                {PAYMENT_LABEL[p.status === "succeeded" ? "paid" : p.status === "created" ? "pending" : p.status] ?? words(p.status)}
                              </Badge>
                            </TableCell>
                            <TableCell className="font-mono text-xs">{p.reference ?? "—"}</TableCell>
                            <TableCell className="font-mono text-xs">{p.invoice_number ?? "—"}</TableCell>
                            {perms.canPayments && <TableCell>{recordFor(p.id) ? <InvoiceButtons payment={recordFor(p.id)!} /> : <span className="text-muted-foreground">—</span>}</TableCell>}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </TabsContent>

                <TabsContent value="emails" className="mt-0">
                  {data.emails.length === 0 ? (
                    <Empty>ERPX has not sent this candidate any email yet.</Empty>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Sent</TableHead>
                          <TableHead>Subject</TableHead>
                          <TableHead>Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.emails.map((e) => (
                          <TableRow key={e.id}>
                            <TableCell className="whitespace-nowrap">{istDateTime(e.sent_at)}</TableCell>
                            <TableCell>
                              <div>{e.subject || "(no subject)"}</div>
                              {e.error && <div className="text-xs text-destructive">{e.error}</div>}
                            </TableCell>
                            <TableCell><Badge variant={e.status === "sent" ? "success" : e.status === "failed" ? "destructive" : "secondary"}>{words(e.status)}</Badge></TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </TabsContent>

                <TabsContent value="activity" className="mt-0">
                  {!profile ? (
                    <Empty>The change history needs Pentrix to be reachable.</Empty>
                  ) : profile.activity.length === 0 ? (
                    <Empty>No details have been changed from ERPX.</Empty>
                  ) : (
                    <ul className="space-y-3 text-sm">
                      {profile.activity.map((a, i) => (
                        <li key={i} className="rounded-md border p-3">
                          <div className="text-xs text-muted-foreground">{a.at ? istDateTime(a.at) : ""}</div>
                          {Object.entries(a.changes ?? {}).map(([field, change]) => (
                            <div key={field}>
                              <strong>{field === "full_name" ? "Name" : "Phone"}</strong>: {change.from || "(none)"} → {change.to || "(none)"}
                            </div>
                          ))}
                        </li>
                      ))}
                    </ul>
                  )}
                </TabsContent>
              </CardContent>
            </Card>
          </Tabs>
          {editing && <EditDialog candidate={data.candidate} onClose={() => setEditing(false)} />}
        </>
      )}
    </div>
  );
}
