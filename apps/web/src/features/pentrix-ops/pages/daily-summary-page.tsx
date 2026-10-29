import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type DailySummary, type DayStatus, openFile, paymentsApi, useDailySummaries, useDay } from "@/features/pentrix-ops/api/payments-api";
import { PaymentDialog, PaymentsTabs, StatusBadge } from "@/features/pentrix-ops/components/payment-parts";
import type { Payment } from "@/features/pentrix-ops/api/payments-api";
import { addDays, dayLabel, istDateTime, istTime, rupees, todayIst, usePentrixPermissions } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";

const DAY_STATUS: Record<DayStatus, { label: string; tone: "success" | "destructive" | "secondary" | "info" }> = {
  matched: { label: "Matches Pentrix", tone: "success" },
  mismatch: { label: "Differences found", tone: "destructive" },
  error: { label: "Check failed", tone: "destructive" },
  open: { label: "Today, in progress", tone: "info" },
  unreconciled: { label: "Not yet checked", tone: "secondary" },
};

function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-md border p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function DayDetail({ day, canManage, canOpenCandidate }: { day: DailySummary; canManage: boolean; canOpenCandidate: boolean }) {
  const queryClient = useQueryClient();
  const detail = useDay(day.date);
  const [open, setOpen] = useState<Payment | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const closed = day.date < todayIst();
  const reconcile = useMutation({
    mutationFn: () => paymentsApi.reconcile(day.date),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["pentrix-ops", "payments"] }),
  });
  const live = detail.data?.summary ?? day;

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="text-base">{dayLabel(day.date)}</CardTitle>
          <CardDescription>
            {live.reconciled && live.reconciled_at ? `Checked against Pentrix ${istDateTime(live.reconciled_at)}` : closed ? "Not yet checked against Pentrix" : "Today is still going; figures are live."}
          </CardDescription>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setExportError(null);
              openFile(`/payments/daily/${day.date}/export`, `pentrix-payments-${day.date}.csv`, "save").catch((e) => setExportError(errorMessage(e, "Could not export.")));
            }}
          >
            <Download className="h-4 w-4" /> Export this day
          </Button>
          {canManage && closed && (
            <Button size="sm" disabled={reconcile.isPending} onClick={() => reconcile.mutate()}>
              {reconcile.isPending ? "Checking…" : live.status === "matched" ? "Check again" : "Reconcile now"}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {exportError && <p role="alert" className="text-sm text-destructive">{exportError}</p>}
        {reconcile.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(reconcile.error, "Could not reconcile this day.")}</p>}
        {live.status === "error" && (
          <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
            The check against Pentrix did not complete{live.last_error ? `: ${live.last_error}` : ""}. {canManage ? "Use Reconcile now to try again." : "It is retried automatically."}
          </p>
        )}
        {live.mismatches.length > 0 && (
          <div className="rounded-md border border-destructive/40 p-3">
            <p className="text-sm font-medium">ERPX and Pentrix disagree on {live.mismatches.length} item{live.mismatches.length === 1 ? "" : "s"}</p>
            <ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">
              {live.mismatches.map((m, i) => <li key={i}>{m.detail}</li>)}
            </ul>
          </div>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Figure label="Successful payments" value={String(live.successful_count)} />
          <Figure label="Total collected" value={rupees(live.collected_paise)} />
          <Figure label="Pending" value={String(live.pending_count)} hint="Started this day, still open" />
          <Figure label="Failed" value={String(live.failed_count)} />
          <Figure
            label="Refunds"
            value={String(live.refund_count)}
            hint={`${rupees(live.refunded_paise)} refunded${live.partial_refund_count ? ` · ${live.partial_refund_count} partial (amount not recorded)` : ""}`}
          />
          <Figure label="Net collected" value={rupees(live.net_paise)} hint="Collected minus complete refunds" />
          {live.repaired_count > 0 && <Figure label="Repaired from Pentrix" value={String(live.repaired_count)} hint="Payments ERPX had missed or held out of date" />}
        </div>

        {detail.isLoading && <Skeleton className="h-24" />}
        {detail.data && detail.data.transactions.length === 0 && <p className="text-sm text-muted-foreground">No payments were made, failed or refunded on this day.</p>}
        {detail.data && detail.data.transactions.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Candidate</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Time</TableHead>
                <TableHead>Reference</TableHead>
                <TableHead>Invoice</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right"><span className="sr-only">Details</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.data.transactions.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.candidate_name || "Candidate"}<div className="text-xs text-muted-foreground">{p.candidate_email}</div></TableCell>
                  <TableCell className="tabular-nums">{rupees(p.amount_paise, p.currency)}</TableCell>
                  <TableCell>{istTime((p.paid_at ?? p.refunded_at ?? p.failed_at ?? p.created_at) as string)}</TableCell>
                  <TableCell className="font-mono text-xs">{p.reference ?? "—"}</TableCell>
                  <TableCell className="font-mono text-xs">{p.invoice_number ?? "—"}</TableCell>
                  <TableCell><StatusBadge payment={p} /></TableCell>
                  <TableCell className="text-right"><Button size="sm" variant="outline" onClick={() => setOpen(p)}>Details</Button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      {open && <PaymentDialog payment={open} canOpenCandidate={canOpenCandidate} onClose={() => setOpen(null)} />}
    </Card>
  );
}

/** What was collected each calendar day in India, checked against Pentrix after the day closes. */
export function DailySummaryPage() {
  const perms = usePentrixPermissions();
  const [to, setTo] = useState(todayIst());
  const [from, setFrom] = useState(addDays(todayIst(), -13));
  const [selected, setSelected] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const days = useDailySummaries(from, to);
  const rangeOk = from <= to && Date.parse(to) - Date.parse(from) <= 92 * 86_400_000;
  const current = days.data?.find((d) => d.date === selected) ?? null;

  return (
    <div className="space-y-5 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Pentrix Daily Summary</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          What was collected each calendar day in India. Shortly after midnight ERPX checks the day that just closed against Pentrix payment by payment, repairs anything it
          had missed, and flags anything that still disagrees.
        </p>
      </div>
      <PaymentsTabs />

      <Card>
        <CardHeader className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label htmlFor="day-from">From</Label>
              <Input id="day-from" type="date" className="w-40" max={to} value={from} onChange={(e) => setFrom(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="day-to">To</Label>
              <Input id="day-to" type="date" className="w-40" min={from} max={todayIst()} value={to} onChange={(e) => setTo(e.target.value)} />
            </div>
            <Button
              variant="outline"
              disabled={!rangeOk}
              onClick={() => {
                setExportError(null);
                openFile(`/payments/daily/export?date_from=${from}&date_to=${to}`, `pentrix-daily-summary-${from}-to-${to}.csv`, "save").catch((e) => setExportError(errorMessage(e, "Could not export.")));
              }}
            >
              <Download className="h-4 w-4" /> Export
            </Button>
          </div>
          {!rangeOk && <p role="alert" className="text-sm text-destructive">Choose a start date on or before the end date, at most 93 days apart.</p>}
          {exportError && <p role="alert" className="text-sm text-destructive">{exportError}</p>}
        </CardHeader>
        <CardContent className="p-0">
          {days.isLoading && <Skeleton className="m-6 h-40" />}
          {days.isError && <p role="alert" className="p-6 text-sm text-destructive">{errorMessage(days.error, "Could not load the daily summaries.")}</p>}
          {days.data && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Day</TableHead>
                  <TableHead>Successful</TableHead>
                  <TableHead>Collected</TableHead>
                  <TableHead>Refunds</TableHead>
                  <TableHead>Net</TableHead>
                  <TableHead>Pending</TableHead>
                  <TableHead>Failed</TableHead>
                  <TableHead>Check</TableHead>
                  <TableHead className="text-right"><span className="sr-only">Open</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {days.data.map((d) => {
                  const status = DAY_STATUS[d.status];
                  return (
                    <TableRow key={d.date} data-state={selected === d.date ? "selected" : undefined}>
                      <TableCell className="font-medium whitespace-nowrap">{dayLabel(d.date)}</TableCell>
                      <TableCell className="tabular-nums">{d.successful_count}</TableCell>
                      <TableCell className="tabular-nums">{rupees(d.collected_paise)}</TableCell>
                      <TableCell className="tabular-nums">{d.refund_count ? `${d.refund_count} · ${rupees(d.refunded_paise)}` : "—"}</TableCell>
                      <TableCell className="tabular-nums">{rupees(d.net_paise)}</TableCell>
                      <TableCell className="tabular-nums">{d.pending_count}</TableCell>
                      <TableCell className="tabular-nums">{d.failed_count}</TableCell>
                      <TableCell><Badge variant={status.tone}>{status.label}</Badge>{d.mismatches.length > 0 && <span className="ml-2 text-xs text-muted-foreground">{d.mismatches.length}</span>}</TableCell>
                      <TableCell className="text-right">
                        <Button size="sm" variant="outline" aria-label={`Open ${dayLabel(d.date)}`} onClick={() => setSelected(selected === d.date ? null : d.date)}>
                          {selected === d.date ? "Close" : "Open"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {current && <DayDetail key={current.date} day={current} canManage={perms.canManagePayments} canOpenCandidate={perms.canRegistrations} />}
    </div>
  );
}
