import { useState } from "react";
import { Link } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { type Payment, usePaymentsSummary } from "@/features/pentrix-ops/api/payments-api";
import { PaymentDialog, StatusBadge } from "@/features/pentrix-ops/components/payment-parts";
import { dayMonthIst, istTime, rupees, usePentrixPermissions } from "@/features/pentrix-ops/lib/format";

function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** Today's collections in India and the latest payment. Only shown to people who may see payments; shows nothing if Pentrix is not set up. */
export function DailyPaymentsWidget({ withRecent = false }: { withRecent?: boolean }) {
  const perms = usePentrixPermissions();
  const summary = usePaymentsSummary(perms.canPayments);
  const [open, setOpen] = useState<Payment | null>(null);
  if (!perms.canPayments || summary.isError) return null;
  const data = summary.data;
  const latest = data?.latest_payment;

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-base">Pentrix daily payments</CardTitle>
          <CardDescription>Today, in India Standard Time.</CardDescription>
        </div>
        <Link to="/pentrix-ops/payments" className="text-sm text-primary hover:underline">Open Pentrix Payments</Link>
      </CardHeader>
      <CardContent className="space-y-5">
        {summary.isLoading && <Skeleton className="h-20" />}
        {data && (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <Figure label="Confirmed collections today" value={rupees(data.collected_today_paise)} hint={data.refunded_today_paise ? `${rupees(data.refunded_today_paise)} refunded today` : undefined} />
              <Figure label="Successful payments today" value={String(data.successful_today)} />
              <Figure label="Pending payments" value={String(data.pending_payments)} />
            </div>
            <div className="text-sm">
              <span className="text-muted-foreground">Latest payment: </span>
              {latest ? (
                <button type="button" className="font-medium hover:underline" onClick={() => setOpen(latest)}>
                  {latest.candidate_name || "Candidate"}, {rupees(latest.amount_paise, latest.currency)}
                </button>
              ) : (
                <span>None yet</span>
              )}
              {latest?.paid_at && <span className="text-muted-foreground"> · {dayMonthIst(latest.paid_at)}, {istTime(latest.paid_at)}</span>}
            </div>
            {withRecent && data.recent.length > 0 && (
              <div>
                <p className="mb-1 text-sm font-medium">Recent transactions</p>
                <ul className="divide-y">
                  {data.recent.map((p) => (
                    <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                      <button type="button" className="text-left hover:underline" onClick={() => setOpen(p)}>
                        <span className="font-medium">{p.candidate_name || "Candidate"}</span>
                        <span className="text-xs text-muted-foreground"> · {p.reference ?? "no reference yet"}</span>
                      </button>
                      <span className="flex items-center gap-3">
                        <span className="tabular-nums">{rupees(p.amount_paise, p.currency)}</span>
                        <StatusBadge payment={p} />
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </CardContent>
      {open && <PaymentDialog payment={open} canOpenCandidate={perms.canRegistrations} onClose={() => setOpen(null)} />}
    </Card>
  );
}
