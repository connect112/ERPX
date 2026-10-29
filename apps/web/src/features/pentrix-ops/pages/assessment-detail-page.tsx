import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAssessmentDetail } from "@/features/pentrix-ops/api/candidates-api";
import { AssessmentRecordView } from "@/features/pentrix-ops/components/assessment-record";
import { PaymentBadge, QualificationBadge } from "@/features/pentrix-ops/components/candidate-badges";
import { usePentrixPermissions } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";

/** One candidate's assessment: every attempt, how it was scored, the criteria and the final result. No contact details or payment history. */
export function AssessmentDetailPage() {
  const { id = "" } = useParams();
  const perms = usePentrixPermissions();
  const detail = useAssessmentDetail(id);
  const data = detail.data;

  return (
    <div className="space-y-5 p-8">
      <Link to="/pentrix-ops/assessments" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> All assessments
      </Link>
      {detail.isLoading && <Skeleton className="h-64" />}
      {detail.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(detail.error, "Could not load this assessment.")}</p>}
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
              {perms.canRegistrations && (
                <Link className="text-sm text-primary hover:underline" to={`/pentrix-ops/registrations/${data.candidate.id}`}>
                  Open candidate record
                </Link>
              )}
            </div>
          </div>
          {!data.live && (
            <p role="status" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
              {data.error ?? "Pentrix could not be reached."} The attempts cannot be shown right now; try again in a moment.
            </p>
          )}
          {data.assessment && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Assessment results</CardTitle>
              </CardHeader>
              <CardContent>
                <AssessmentRecordView record={data.assessment} />
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
