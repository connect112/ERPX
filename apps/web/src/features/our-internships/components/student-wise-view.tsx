import { ArrowDown, ArrowUp, ArrowUpDown, Check, Pencil, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { StudentPerformance } from "@/features/our-internships/api/our-internships-api";
import {
  formatMarks,
  formatScore,
  formatTeamScore,
  selectableIds,
  type SortDirection,
  type SortKey,
  sortStudents,
} from "@/features/our-internships/lib/performance";

function SortHeader({ label, column, sort, direction, onSort }: { label: string; column: SortKey; sort: SortKey; direction: SortDirection; onSort: (key: SortKey) => void }) {
  const Icon = sort !== column ? ArrowUpDown : direction === "asc" ? ArrowUp : ArrowDown;
  return (
    <button
      type="button"
      className="inline-flex items-center gap-1 font-medium hover:text-foreground"
      aria-label={`Sort by ${label}`}
      onClick={() => onSort(column)}
    >
      {label}
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
    </button>
  );
}

/**
 * Every eligible student on one line with what the selection is based on: team and its hackathon score, individual
 * score, workshop exam marks. Click a column to sort (best first for the scores); tick students and add them.
 */
export function StudentWiseView({
  rows,
  showInstitution,
  pending,
  onSelect,
  onEdit,
  onRemove,
}: {
  rows: StudentPerformance[];
  showInstitution: boolean;
  pending: boolean;
  onSelect: (studentIds: string[]) => void;
  /** When given, each row can be edited / taken off its event. */
  onEdit?: (row: StudentPerformance) => void;
  onRemove?: (row: StudentPerformance) => void;
}) {
  const [sort, setSort] = useState<SortKey>("name");
  const [direction, setDirection] = useState<SortDirection>("asc");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [hideSelected, setHideSelected] = useState(false);

  const visible = useMemo(() => sortStudents(hideSelected ? rows.filter((r) => !r.selected) : rows, sort, direction), [rows, sort, direction, hideSelected]);
  const available = useMemo(() => new Set(selectableIds(rows)), [rows]);
  // ticks for people who are no longer on the list (a filter changed) or are now selected are dropped, not silently kept
  const ticked = [...picked].filter((id) => available.has(id));

  const toggleSort = (key: SortKey) => {
    if (key === sort) setDirection(direction === "asc" ? "desc" : "asc");
    else {
      setSort(key);
      setDirection(key === "name" ? "asc" : "desc");
    }
  };
  const toggle = (id: string, on: boolean) => {
    const next = new Set(picked);
    if (on) next.add(id);
    else next.delete(id);
    setPicked(next);
  };
  const allVisibleTicked = visible.filter((r) => !r.selected).every((r) => picked.has(r.student_id)) && visible.some((r) => !r.selected);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={hideSelected} onChange={(e) => setHideSelected(e.target.checked)} />
          Hide students already selected
        </label>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{ticked.length} ticked</span>
          <Button
            disabled={ticked.length === 0 || pending}
            onClick={() => {
              onSelect(ticked);
              setPicked(new Set());
            }}
          >
            Add {ticked.length || ""} to selected list
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="overflow-x-auto p-0">
          {visible.length === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">No students match.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <input
                      type="checkbox"
                      aria-label="Tick every student shown"
                      checked={allVisibleTicked}
                      onChange={(e) => setPicked(e.target.checked ? new Set(visible.filter((r) => !r.selected).map((r) => r.student_id)) : new Set())}
                    />
                  </TableHead>
                  <TableHead>
                    <SortHeader label="Student" column="name" sort={sort} direction={direction} onSort={toggleSort} />
                  </TableHead>
                  {showInstitution && <TableHead>Institution</TableHead>}
                  <TableHead>Event</TableHead>
                  <TableHead>Team</TableHead>
                  <TableHead>
                    <SortHeader label="Team score" column="team_score" sort={sort} direction={direction} onSort={toggleSort} />
                  </TableHead>
                  <TableHead>
                    <SortHeader label="Individual" column="individual" sort={sort} direction={direction} onSort={toggleSort} />
                  </TableHead>
                  <TableHead>
                    <SortHeader label="Exam marks" column="exam" sort={sort} direction={direction} onSort={toggleSort} />
                  </TableHead>
                  {(onEdit || onRemove) && <TableHead className="text-right">Actions</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {visible.map((r) => (
                  <TableRow key={`${r.event_id}-${r.student_id}`}>
                    <TableCell>
                      {r.selected ? (
                        <Check className="h-4 w-4 text-emerald-600" aria-label="Already selected" />
                      ) : (
                        <input
                          type="checkbox"
                          aria-label={`Select ${r.name}`}
                          checked={picked.has(r.student_id)}
                          onChange={(e) => toggle(r.student_id, e.target.checked)}
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="font-medium">{r.name}</span>
                      {r.selected && (
                        <Badge variant="success" className="ml-2">
                          Selected
                        </Badge>
                      )}
                      <span className="block text-xs text-muted-foreground">
                        {r.email}
                        {r.phone ? ` · ${r.phone}` : ""}
                      </span>
                      {r.remarks && <span className="block text-xs italic text-muted-foreground">“{r.remarks}”</span>}
                    </TableCell>
                    {showInstitution && <TableCell>{r.institution_name}</TableCell>}
                    <TableCell className="text-muted-foreground">{r.event_name}</TableCell>
                    <TableCell>{r.team ? r.team.team_name : <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell>{r.team ? formatTeamScore(r.team.tasks_scored > 0 ? r.team.score : null, r.team.max_total, r.team.rank) : "—"}</TableCell>
                    <TableCell>{formatScore(r.individual_score)}</TableCell>
                    <TableCell>
                      {formatMarks(r.exam_score, r.exam_total, r.exam_percent)}
                      {r.exams.length > 1 && (
                        <span className="block text-xs text-muted-foreground">
                          {r.exams.map((x) => `${x.title}: ${x.attended ? formatMarks(x.score, x.total_marks) : "did not sit"}`).join(" · ")}
                        </span>
                      )}
                      {r.exams.length === 1 && !r.exams[0].attended && <span className="block text-xs text-muted-foreground">did not sit</span>}
                    </TableCell>
                    {(onEdit || onRemove) && (
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          {onEdit && (
                            <Button size="icon" variant="ghost" aria-label={`Edit ${r.name}`} onClick={() => onEdit(r)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                          )}
                          {onRemove && (
                            <Button size="icon" variant="ghost" aria-label={`Remove ${r.name} from ${r.event_name}`} onClick={() => onRemove(r)}>
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      <p className="text-xs text-muted-foreground">{visible.length} shown</p>
    </div>
  );
}
