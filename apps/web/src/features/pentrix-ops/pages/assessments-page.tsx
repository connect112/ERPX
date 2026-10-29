import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EMPTY_FILTERS, useAssessments } from "@/features/pentrix-ops/api/candidates-api";
import { AssessmentBadge, BookingBadge, PaymentBadge, QualificationBadge } from "@/features/pentrix-ops/components/candidate-badges";
import { CandidateFilterBar } from "@/features/pentrix-ops/components/candidate-filters";
import { ASSESSMENT_SORTS, useUrlFilters } from "@/features/pentrix-ops/lib/use-url-filters";
import { dayMonthIst, percent } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";

const DEFAULTS = { ...EMPTY_FILTERS, sort: "assessed" };

/** Candidates with their assessment attempt, score and whether they qualified. The scoring is Pentrix's own: ERPX shows what it stored. */
export function AssessmentsPage() {
  const { filters, update, clear, active } = useUrlFilters(DEFAULTS);
  const assessments = useAssessments(filters);
  const data = assessments.data;
  const pages = data ? Math.max(Math.ceil(data.total / data.page_size), 1) : 1;

  return (
    <div className="space-y-5 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Pentrix Assessments</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Who has taken the Pentrix assessment, how they scored and whether they qualified. A candidate qualifies when their readiness and technical results both meet the
          criteria set in Pentrix; ERPX does not mark assessments itself.
        </p>
      </div>
      <Card>
        <CardHeader className="space-y-4">
          <CandidateFilterBar idPrefix="asm" filters={filters} update={update} clear={clear} active={active} sorts={ASSESSMENT_SORTS} />
          <CardDescription>{data ? `${data.total} candidate${data.total === 1 ? "" : "s"}${active ? " match" : ""}` : ""}</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {assessments.isLoading && <Skeleton className="m-6 h-40" />}
          {assessments.isError && <p role="alert" className="p-6 text-sm text-destructive">{errorMessage(assessments.error, "Could not load the assessments.")}</p>}
          {data && data.items.length === 0 && (
            <p className="p-8 text-center text-sm text-muted-foreground">{active ? "No candidates match these filters." : "Nobody has registered yet."}</p>
          )}
          {data && data.items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidate</TableHead>
                  <TableHead>Registered</TableHead>
                  <TableHead>Assessment</TableHead>
                  <TableHead>Assessment date</TableHead>
                  <TableHead>Latest score</TableHead>
                  <TableHead>Qualification</TableHead>
                  <TableHead>Payment</TableHead>
                  <TableHead>Booking</TableHead>
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
                    <TableCell>{dayMonthIst(c.registered_at)}</TableCell>
                    <TableCell><AssessmentBadge assessment={c.assessment} /></TableCell>
                    <TableCell>{c.assessment.assessed_at ? dayMonthIst(c.assessment.assessed_at) : <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell>
                      {c.assessment.qualified === null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <div className="text-sm">
                          <div>Readiness {percent(c.assessment.readiness_commitment_pct)}</div>
                          <div className="text-muted-foreground">Technical {percent(c.assessment.technical_pct)}</div>
                        </div>
                      )}
                    </TableCell>
                    <TableCell><QualificationBadge qualified={c.assessment.qualified} /></TableCell>
                    <TableCell><PaymentBadge payment={c.payment} /></TableCell>
                    <TableCell><BookingBadge booking={c.booking} /></TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="outline">
                        <Link to={`/pentrix-ops/assessments/${c.id}`} aria-label={`Open the assessment of ${c.full_name}`}>Open</Link>
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
