import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type ResultRow, useLearningResults } from "@/features/learning/api/learning-api";
import type { TabProps } from "@/features/learning/components/learning-workspace";
import { useDebounced } from "@/features/institutions/lib/use-debounced";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";
const kindLabel: Record<ResultRow["kind"], string> = { exam: "Exam", assignment: "Assignment", assessment: "Assessment", project: "Project", practical: "Practical", viva: "Viva" };
const stateLabel: Record<string, string> = { not_started: "Not started", in_progress: "In progress", submitted: "Submitted, not graded", graded: "Graded" };

/**
 * Results of every kind of activity, each in its own marks. There is deliberately no total or average across them: no weighting policy exists,
 * so none is invented. A student whose access was withdrawn stays in the list, marked, so their history is never lost.
 */
export function ResultsView({ courseId, internship, needsChoice }: TabProps) {
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim());
  const scope = internship ? { internshipId: internship.id } : { courseId: courseId ?? undefined };
  const results = useLearningResults(scope, { kind: kind || undefined, status: status || undefined, q: q || undefined });

  return (
    <div className="space-y-3" data-testid="results-view">
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Kind of activity" className={selectClass} value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">All kinds</option>
          {(results.data?.included ?? Object.keys(kindLabel)).map((k) => (
            <option key={k} value={k}>
              {kindLabel[k as ResultRow["kind"]]}
            </option>
          ))}
        </select>
        <select aria-label="Completion" className={selectClass} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any completion</option>
          <option value="completed">Completed</option>
          <option value="pending">Not completed</option>
        </select>
        <Input className="w-64" placeholder="Search student or activity" aria-label="Search results" value={search} onChange={(e) => setSearch(e.target.value)} />
        <span className="text-xs text-muted-foreground">Each activity is shown in its own marks; there is no combined score.</span>
      </div>
      {needsChoice && <p className="text-sm text-muted-foreground">Showing the course's own results. Choose an internship above to add that internship's students and activities (cohorts are never mixed).</p>}
      {results.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : results.isError || !results.data ? (
        <p className="text-sm text-destructive">Could not load the results.</p>
      ) : results.data.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No results to show.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Student</TableHead>
              <TableHead>Activity</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Marks</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {results.data.rows.map((r) => (
              <TableRow key={`${r.kind}-${r.activity_id}-${r.student_key}`}>
                <TableCell>
                  <div className="font-medium">{r.student_name}</div>
                  {r.student_email && <div className="text-xs text-muted-foreground">{r.student_email}</div>}
                  {r.access_status === "revoked" && <Badge variant="warning">Access revoked</Badge>}
                </TableCell>
                <TableCell>
                  <div>{r.activity_title}</div>
                  <div className="flex gap-1 text-xs text-muted-foreground">
                    <Badge variant="secondary">{kindLabel[r.kind]}</Badge>
                    <Badge variant={r.scope === "internship" ? "info" : "secondary"}>{r.scope === "internship" ? "Internship" : "Course"}</Badge>
                  </div>
                </TableCell>
                <TableCell className="text-sm">{stateLabel[r.state] ?? r.state}</TableCell>
                <TableCell className="text-right text-sm">
                  {r.score != null && r.total_marks != null ? (
                    <>
                      {r.score} / {r.total_marks}
                      {r.percent != null && <span className="text-muted-foreground"> ({r.percent}%)</span>}
                      {r.passed != null && <Badge className="ml-2" variant={r.passed ? "success" : "destructive"}>{r.passed ? "Pass" : "Fail"}</Badge>}
                    </>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
