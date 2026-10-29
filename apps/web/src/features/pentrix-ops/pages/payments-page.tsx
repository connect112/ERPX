import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type Payment, paymentsApi, usePayments, usePaymentsSummary } from "@/features/pentrix-ops/api/payments-api";
import { InvoiceButtons, PaymentDialog, PaymentsTabs, StatusBadge } from "@/features/pentrix-ops/components/payment-parts";
import { agoOrDate, dayMonthIst, istTime, rupees, usePentrixPermissions } from "@/features/pentrix-ops/lib/format";
import { usePaymentFilters } from "@/features/pentrix-ops/lib/use-payment-filters";
import { errorMessage } from "@/features/institutions/lib/format";
import { selectClass } from "@/features/our-internships/components/letter-fields";

const STATUS = [["", "Any"], ["paid", "Paid"], ["pending", "Pending"], ["failed", "Failed"], ["refunded", "Refunded"], ["partially_refunded", "Partially refunded"]];
const PURPOSE = [["", "Any"], ["program_fee", "Programme fee"], ["individual_interaction_token", "Token fee"]];

/** Every Pentrix payment, with who paid, how much, the transaction reference and the invoice. Pentrix records them; this is a live copy. */
export function PaymentsPage() {
  const perms = usePentrixPermissions();
  const queryClient = useQueryClient();
  const { filters, update, clear, active } = usePaymentFilters();
  const [search, setSearch] = useState(filters.q);
  const [open, setOpen] = useState<Payment | null>(null);
  const payments = usePayments(filters);
  const summary = usePaymentsSummary();
  const sync = useMutation({ mutationFn: paymentsApi.sync, onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["pentrix-ops"] }) });
  const data = payments.data;
  const pages = data ? Math.max(Math.ceil(data.total / data.page_size), 1) : 1;
  const syncState = summary.data?.sync;

  return (
    <div className="space-y-5 p-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pentrix Payments</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Payments made on Pentrix. A payment is shown as paid only once Pentrix has recorded it after its payment provider confirmed it; nothing here moves money.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {syncState?.last_synced_at && <span className="text-xs text-muted-foreground">Last checked with Pentrix {agoOrDate(syncState.last_synced_at)}</span>}
          {perms.canManagePayments && (
            <Button variant="outline" disabled={sync.isPending} onClick={() => sync.mutate()}>
              <RefreshCw className={`h-4 w-4 ${sync.isPending ? "animate-spin" : ""}`} /> {syncState?.last_error ? "Retry synchronisation" : "Refresh from Pentrix"}
            </Button>
          )}
        </div>
      </div>
      <PaymentsTabs />
      {sync.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(sync.error, "Could not reach Pentrix.")}</p>}
      {syncState?.last_error && (
        <p role="status" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
          The last synchronisation with Pentrix did not complete ({syncState.last_error}). It retries every minute; the figures below may be a little behind.
        </p>
      )}

      <Card>
        <CardHeader className="space-y-4">
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              update({ q: search.trim() });
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="pay-search">Search</Label>
              <Input id="pay-search" className="w-64" placeholder="Name, email, reference or invoice" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="pay-status">Status</Label>
              <select id="pay-status" className={`${selectClass} w-44`} value={filters.status} onChange={(e) => update({ status: e.target.value })}>
                {STATUS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="pay-purpose">For</Label>
              <select id="pay-purpose" className={`${selectClass} w-44`} value={filters.purpose} onChange={(e) => update({ purpose: e.target.value })}>
                {PURPOSE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="pay-from">From</Label>
              <Input id="pay-from" type="date" className="w-40" value={filters.date_from} onChange={(e) => update({ date_from: e.target.value })} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="pay-to">To</Label>
              <Input id="pay-to" type="date" className="w-40" value={filters.date_to} onChange={(e) => update({ date_to: e.target.value })} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="pay-sort">Sort by</Label>
              <select id="pay-sort" className={`${selectClass} w-36`} value={filters.sort} onChange={(e) => update({ sort: e.target.value })}>
                <option value="date">Date</option>
                <option value="amount">Amount</option>
                <option value="status">Status</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="pay-order">Order</Label>
              <select id="pay-order" className={`${selectClass} w-40`} value={filters.order} onChange={(e) => update({ order: e.target.value as "asc" | "desc" })}>
                <option value="desc">Newest / highest first</option>
                <option value="asc">Oldest / lowest first</option>
              </select>
            </div>
            <Button type="submit" variant="outline">Search</Button>
            {active && (
              <Button type="button" variant="ghost" onClick={() => { setSearch(""); clear(); }}>Clear filters</Button>
            )}
          </form>
          <CardDescription>{data ? `${data.total} payment${data.total === 1 ? "" : "s"}${active ? " match" : ""}` : ""}</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {payments.isLoading && <Skeleton className="m-6 h-40" />}
          {payments.isError && <p role="alert" className="p-6 text-sm text-destructive">{errorMessage(payments.error, "Could not load the payments.")}</p>}
          {data && data.items.length === 0 && <p className="p-8 text-center text-sm text-muted-foreground">{active ? "No payments match these filters." : "No payments have been made yet."}</p>}
          {data && data.items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidate</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Transaction reference</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Invoice</TableHead>
                  <TableHead className="text-right"><span className="sr-only">Details</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((p) => {
                  const when = p.paid_at ?? p.created_at;
                  return (
                    <TableRow key={p.id}>
                      <TableCell>
                        {perms.canRegistrations && p.candidate_id ? (
                          <Link className="font-medium hover:underline" to={`/pentrix-ops/registrations/${p.candidate_id}`}>{p.candidate_name || "Candidate"}</Link>
                        ) : (
                          <span className="font-medium">{p.candidate_name || "Candidate"}</span>
                        )}
                        <div className="text-xs text-muted-foreground">{p.candidate_email}</div>
                      </TableCell>
                      <TableCell className="tabular-nums">{rupees(p.amount_paise, p.currency)}<div className="text-xs text-muted-foreground">{p.purpose_label}</div></TableCell>
                      <TableCell>{when ? dayMonthIst(when) : "—"}{when && <div className="text-xs text-muted-foreground">{istTime(when)}{p.paid_at ? "" : " (started)"}</div>}</TableCell>
                      <TableCell>{p.method}</TableCell>
                      <TableCell className="font-mono text-xs">{p.reference ?? "—"}</TableCell>
                      <TableCell><StatusBadge payment={p} /></TableCell>
                      <TableCell>
                        {p.invoice_available ? (
                          <div className="space-y-1">
                            <div className="font-mono text-xs">{p.invoice_number ?? p.receipt_number ?? "—"}</div>
                            <InvoiceButtons payment={p} />
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button size="sm" variant="outline" aria-label={`Transaction details for ${p.candidate_name}`} onClick={() => setOpen(p)}>Details</Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
          {data && data.total > data.page_size && (
            <div className="flex items-center justify-between border-t px-6 py-3 text-sm">
              <span className="text-muted-foreground">Page {data.page} of {pages}</span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={filters.page <= 1} onClick={() => update({ page: filters.page - 1 })}>Previous</Button>
                <Button size="sm" variant="outline" disabled={filters.page >= pages} onClick={() => update({ page: filters.page + 1 })}>Next</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      {open && <PaymentDialog payment={open} canOpenCandidate={perms.canRegistrations} onClose={() => setOpen(null)} />}
    </div>
  );
}
