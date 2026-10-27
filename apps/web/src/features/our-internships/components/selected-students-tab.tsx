import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserMinus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/features/institutions/lib/format";
import {
  type SelectedStudent,
  ourInternshipsApi,
  ourInternshipsKeys,
} from "@/features/our-internships/api/our-internships-api";
import { formatMarks, formatScore, formatTeamScore } from "@/features/our-internships/lib/performance";

/** The shortlist for this internship: review each student's results, add a note, or take someone off before offers go out. */
export function SelectedStudentsTab({ internshipId }: { internshipId: string }) {
  const queryClient = useQueryClient();
  const selected = useQuery({ queryKey: ourInternshipsKeys.selected(internshipId), queryFn: () => ourInternshipsApi.selected(internshipId) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });
  const remove = useMutation({ mutationFn: (studentId: string) => ourInternshipsApi.unselect(internshipId, studentId), onSuccess: refresh });
  const saveNote = useMutation({
    mutationFn: (v: { studentId: string; note: string | null }) => ourInternshipsApi.setNote(internshipId, v.studentId, v.note),
    onSuccess: refresh,
  });

  if (selected.isLoading) return <Skeleton className="h-32 w-full" />;
  if (selected.isError) return <p className="text-sm text-destructive">Could not load the selected students.</p>;
  const items = selected.data?.items ?? [];
  if (items.length === 0) {
    return (
      <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">
        No one is selected yet. Choose students in the Students or Teams tab and they appear here.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      <Card>
        <CardContent className="overflow-x-auto p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Student</TableHead>
                <TableHead>Institution</TableHead>
                <TableHead>Results</TableHead>
                <TableHead>Note</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((s) => (
                <TableRow key={s.student_id}>
                  <TableCell>
                    <span className="font-medium">{s.name}</span>
                    <span className="block text-xs text-muted-foreground">
                      {s.email}
                      {s.phone ? ` · ${s.phone}` : ""}
                    </span>
                  </TableCell>
                  <TableCell>{s.institution_name}</TableCell>
                  <TableCell className="text-xs">
                    {s.standings.length === 0 && <span className="text-muted-foreground">No results recorded</span>}
                    {s.standings.map((st) => (
                      <div key={st.event_id} className="mb-1 last:mb-0">
                        <span className="font-medium">{st.event_name}</span>: exam {formatMarks(st.exam_score, st.exam_total, st.exam_percent)} · team{" "}
                        {st.team ? `${st.team.team_name} ${formatTeamScore(st.team.tasks_scored > 0 ? st.team.score : null, st.team.max_total, st.team.rank)}` : "—"}{" "}
                        · individual {formatScore(st.individual_score)}
                      </div>
                    ))}
                  </TableCell>
                  <TableCell>
                    <NoteBox student={s} onSave={(note) => saveNote.mutate({ studentId: s.student_id, note })} />
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove ${s.name} from the selected list`}
                      onClick={() => {
                        if (window.confirm(`Remove ${s.name} from the selected list?`)) remove.mutate(s.student_id);
                      }}
                    >
                      <UserMinus className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <p className="text-xs text-muted-foreground">{items.length} selected</p>
      {(remove.isError || saveNote.isError) && <p className="text-sm text-destructive">{errorMessage(remove.error ?? saveNote.error, "Could not save that change.")}</p>}
    </div>
  );
}

function NoteBox({ student, onSave }: { student: SelectedStudent; onSave: (note: string | null) => void }) {
  const [value, setValue] = useState(student.note ?? "");
  return (
    <Input
      aria-label={`Note for ${student.name}`}
      className="h-8 min-w-[10rem]"
      maxLength={2000}
      placeholder="Add a note"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => {
        const next = value.trim() || null;
        if (next !== (student.note ?? null)) onSave(next);
      }}
    />
  );
}
