import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Mail, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { candidatesApi, useCandidates } from "@/features/pentrix-ops/api/candidates-api";
import { pentrixKeys } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { AssessmentBadge, BookingBadge, PaymentBadge, QualificationBadge } from "@/features/pentrix-ops/components/candidate-badges";
import { MarketingWizard } from "@/features/pentrix-ops/components/marketing-wizard";
import { type Selection, selectionFilters } from "@/features/pentrix-ops/api/marketing-api";
import { CandidateFilterBar } from "@/features/pentrix-ops/components/candidate-filters";
import { REGISTRATION_SORTS, useUrlFilters } from "@/features/pentrix-ops/lib/use-url-filters";
import { agoOrDate, dayMonthIst, usePentrixPermissions } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";

/** Everyone who has registered on Pentrix. The list, its filters and its paging are done by the server, so it stays quick however many there are. */
export function RegistrationsPage() {
  const queryClient = useQueryClient();
  const perms = usePentrixPermissions();
  const { filters, update, clear, active } = useUrlFilters();
  // Who is ticked: candidates one by one (kept across pages), or everyone matching the filters less any unticked.
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [everyone, setEveryone] = useState(false);
  const [sending, setSending] = useState(false);
  const filterKey = JSON.stringify({ ...filters, page: 0 });
  useEffect(() => {
    setPicked(new Set());
    setEveryone(false);
  }, [filterKey]);
  const candidates = useCandidates(filters);
  const sync = useMutation({ mutationFn: candidatesApi.sync, onSuccess: () => void queryClient.invalidateQueries({ queryKey: pentrixKeys.all }) });
  const data = candidates.data;
  const pages = data ? Math.max(Math.ceil(data.total / data.page_size), 1) : 1;
  const pageIds = useMemo(() => (data?.items ?? []).map((c) => c.id), [data]);
  const onPage = pageIds.filter((id) => (everyone ? !picked.has(id) : picked.has(id))).length;
  const allOnPage = pageIds.length > 0 && onPage === pageIds.length;
  const count = everyone ? (data?.total ?? 0) - picked.size : picked.size;
  const isTicked = (id: string) => (everyone ? !picked.has(id) : picked.has(id));
  const toggle = (id: string) => setPicked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const togglePage = () => setPicked((s) => {
    const n = new Set(s);
    // In "everyone" mode the set holds who was taken out; otherwise who was put in.
    const wantTicked = !allOnPage;
    for (const id of pageIds) { if (wantTicked === !everyone) n.add(id); else n.delete(id); }
    return n;
  });
  const selection: Selection = everyone
    ? { mode: "filter", filters: selectionFilters(filters), exclude_ids: [...picked] }
    : { mode: "ids", ids: [...picked] };

  return (
    <div className="space-y-5 p-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pentrix Registrations</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Everyone who has registered on Pentrix, with where they are in the journey: assessment, qualification, booking and payment. Combine the filters to find, for
            example, people who qualified but have not booked or paid.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {perms.canSendMarketing && (
            <Button disabled={count === 0} onClick={() => setSending(true)}>
              <Mail className="h-4 w-4" /> Send Marketing Email{count > 0 ? ` (${count})` : ""}
            </Button>
          )}
          <Button variant="outline" disabled={sync.isPending} onClick={() => sync.mutate()}>
            <RefreshCw className={`h-4 w-4 ${sync.isPending ? "animate-spin" : ""}`} /> Refresh from Pentrix
          </Button>
        </div>
      </div>
      {sync.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(sync.error, "Could not reach Pentrix.")}</p>}

      <Card>
        <CardHeader className="space-y-4">
          <CandidateFilterBar idPrefix="reg" filters={filters} update={update} clear={clear} active={active} sorts={REGISTRATION_SORTS} />
          <CardDescription>{data ? `${data.total} candidate${data.total === 1 ? "" : "s"}${active ? " match" : ""}` : ""}</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {perms.canSendMarketing && data && data.items.length > 0 && (allOnPage || everyone) && (data.total > data.items.length || everyone) && (
            <div role="status" className="flex flex-wrap items-center gap-3 border-b bg-muted/40 px-6 py-2 text-sm">
              {everyone ? (
                <>
                  <span>All {data.total} matching candidates are selected{picked.size ? `, less ${picked.size} you unticked` : ""}.</span>
                  <Button size="sm" variant="link" className="h-auto p-0" onClick={() => { setEveryone(false); setPicked(new Set()); }}>Clear selection</Button>
                </>
              ) : (
                <>
                  <span>All {data.items.length} on this page are selected.</span>
                  <Button size="sm" variant="link" className="h-auto p-0" onClick={() => { setEveryone(true); setPicked(new Set()); }}>Select all {data.total} matching these filters</Button>
                </>
              )}
            </div>
          )}
          {candidates.isLoading && <Skeleton className="m-6 h-40" />}
          {candidates.isError && <p role="alert" className="p-6 text-sm text-destructive">{errorMessage(candidates.error, "Could not load the candidates.")}</p>}
          {data && data.items.length === 0 && (
            <p className="p-8 text-center text-sm text-muted-foreground">{active ? "No candidates match these filters." : "Nobody has registered yet."}</p>
          )}
          {data && data.items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  {perms.canSendMarketing && (
                    <TableHead className="w-8">
                      <input type="checkbox" aria-label="Select everyone on this page" checked={allOnPage} onChange={togglePage} />
                    </TableHead>
                  )}
                  <TableHead>Candidate</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Registered</TableHead>
                  <TableHead>Assessment</TableHead>
                  <TableHead>Qualification</TableHead>
                  <TableHead>Booking</TableHead>
                  <TableHead>Payment</TableHead>
                  <TableHead>Marketing</TableHead>
                  <TableHead>Latest activity</TableHead>
                  <TableHead className="text-right"><span className="sr-only">Open</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((c) => (
                  <TableRow key={c.id} data-state={isTicked(c.id) ? "selected" : undefined}>
                    {perms.canSendMarketing && (
                      <TableCell>
                        <input type="checkbox" aria-label={`Select ${c.full_name || c.email}`} checked={isTicked(c.id)} onChange={() => toggle(c.id)} />
                      </TableCell>
                    )}
                    <TableCell>
                      <div className="font-medium">{c.full_name || "Candidate"}</div>
                      <div className="text-xs text-muted-foreground">{c.email}</div>
                    </TableCell>
                    <TableCell>{c.phone ?? <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell>{dayMonthIst(c.registered_at)}</TableCell>
                    <TableCell><AssessmentBadge assessment={c.assessment} /></TableCell>
                    <TableCell><QualificationBadge qualified={c.assessment.qualified} /></TableCell>
                    <TableCell><BookingBadge booking={c.booking} /></TableCell>
                    <TableCell><PaymentBadge payment={c.payment} /></TableCell>
                    <TableCell>{c.marketing_opt_in ? <Badge variant="success">Agreed</Badge> : <span className="text-sm text-muted-foreground">Not agreed</span>}</TableCell>
                    <TableCell className="whitespace-nowrap text-muted-foreground">{agoOrDate(c.last_activity_at)}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="outline">
                        <Link to={`/pentrix-ops/registrations/${c.id}`} aria-label={`Open ${c.full_name}`}>Open</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
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
      {sending && <MarketingWizard selection={selection} onClose={() => { setSending(false); setPicked(new Set()); setEveryone(false); }} />}
    </div>
  );
}
