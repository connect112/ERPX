import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { AssessmentRecord } from "@/features/pentrix-ops/api/candidates-api";
import { QualificationBadge } from "@/features/pentrix-ops/components/candidate-badges";
import { duration, istDateTime, percent } from "@/features/pentrix-ops/lib/format";

const PART_LABEL: Record<string, string> = { readiness_commitment: "Readiness and commitment", technical: "Technical" };

/** The criteria, the final result and every attempt with how it was scored. Used on the assessment screen and on a candidate's own page. */
export function AssessmentRecordView({ record }: { record: AssessmentRecord }) {
  const { criteria } = record;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-md border p-4">
          <p className="text-xs text-muted-foreground">Final qualification</p>
          <div className="mt-1.5 flex items-center gap-2">
            <QualificationBadge qualified={record.qualified} />
            {record.qualified_at && <span className="text-xs text-muted-foreground">{istDateTime(record.qualified_at)}</span>}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">The result of the latest submitted attempt.</p>
        </div>
        <div className="rounded-md border p-4">
          <p className="text-xs text-muted-foreground">Criteria to qualify</p>
          <p className="mt-1.5 text-sm">Readiness and commitment: at least <strong>{percent(criteria.readiness_commitment_pct)}</strong></p>
          <p className="text-sm">Technical: at least <strong>{percent(criteria.technical_pct)}</strong></p>
        </div>
        <div className="rounded-md border p-4">
          <p className="text-xs text-muted-foreground">Attempts</p>
          <p className="mt-1.5 text-2xl font-semibold">{record.attempts.filter((a) => a.status === "submitted").length}</p>
          <p className="text-xs text-muted-foreground">submitted ({record.attempts.length} started)</p>
        </div>
      </div>

      {record.attempts.length === 0 ? (
        <p className="rounded-md border p-6 text-center text-sm text-muted-foreground">This candidate has not started the assessment.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Attempt</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Time taken</TableHead>
              <TableHead>Readiness</TableHead>
              <TableHead>Technical</TableHead>
              <TableHead>Result</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {record.attempts.map((a, index) => (
              <TableRow key={a.id}>
                <TableCell className="font-medium">#{record.attempts.length - index}</TableCell>
                <TableCell>{a.started_at ? istDateTime(a.started_at) : "—"}</TableCell>
                <TableCell>{a.status === "submitted" ? duration(a.duration_seconds) : <Badge variant="secondary">{a.status === "in_progress" ? "In progress" : "Expired"}</Badge>}</TableCell>
                {(["readiness_commitment", "technical"] as const).map((part) => {
                  const detail = a.parts[part];
                  const value = part === "technical" ? a.technical_pct : a.readiness_commitment_pct;
                  return (
                    <TableCell key={part}>
                      <div>{percent(value)}</div>
                      {detail && (
                        <div className="text-xs text-muted-foreground" title={PART_LABEL[part]}>
                          {detail.correct} of {detail.total} correct
                        </div>
                      )}
                    </TableCell>
                  );
                })}
                <TableCell>{a.status === "submitted" ? <QualificationBadge qualified={a.qualified} /> : <span className="text-muted-foreground">—</span>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
