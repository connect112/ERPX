import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { candidatesApi, useCandidates } from "@/features/pentrix-ops/api/candidates-api";
import { pentrixKeys } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { AssessmentBadge, BookingBadge, PaymentBadge, QualificationBadge } from "@/features/pentrix-ops/components/candidate-badges";
import { CandidateFilterBar } from "@/features/pentrix-ops/components/candidate-filters";
import { REGISTRATION_SORTS, useUrlFilters } from "@/features/pentrix-ops/lib/use-url-filters";
import { agoOrDate, dayMonthIst } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";

/** Everyone who has registered on Pentrix. The list, its filters and its paging are done by the server, so it stays quick however many there are. */
export function RegistrationsPage() {
  const queryClient = useQueryClient();
  const { filters, update, clear, active } = useUrlFilters();
  const candidates = useCandidates(filters);
  const sync = useMutation({ mutationFn: candidatesApi.sync, onSuccess: () => void queryClient.invalidateQueries({ queryKey: pentrixKeys.all }) });
  const data = candidates.data;
  const pages = data ? Math.max(Math.ceil(data.total / data.page_size), 1) : 1;

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
        <Button variant="outline" disabled={sync.isPending} onClick={() => sync.mutate()}>
          <RefreshCw className={`h-4 w-4 ${sync.isPending ? "animate-spin" : ""}`} /> Refresh from Pentrix
        </Button>
      </div>
      {sync.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(sync.error, "Could not reach Pentrix.")}</p>}

      <Card>
        <CardHeader className="space-y-4">
          <CandidateFilterBar idPrefix="reg" filters={filters} update={update} clear={clear} active={active} sorts={REGISTRATION_SORTS} />
          <CardDescription>{data ? `${data.total} candidate${data.total === 1 ? "" : "s"}${active ? " match" : ""}` : ""}</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {candidates.isLoading && <Skeleton className="m-6 h-40" />}
          {candidates.isError && <p role="alert" className="p-6 text-sm text-destructive">{errorMessage(candidates.error, "Could not load the candidates.")}</p>}
          {data && data.items.length === 0 && (
            <p className="p-8 text-center text-sm text-muted-foreground">{active ? "No candidates match these filters." : "Nobody has registered yet."}</p>
          )}
          {data && data.items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidate</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Registered</TableHead>
                  <TableHead>Assessment</TableHead>
                  <TableHead>Qualification</TableHead>
                  <TableHead>Booking</TableHead>
                  <TableHead>Payment</TableHead>
                  <TableHead>Latest activity</TableHead>
                  <TableHead className="text-right"><span className="sr-only">Open</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((c) => (
                  <TableRow key={c.id}>
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
    </div>
  );
}
