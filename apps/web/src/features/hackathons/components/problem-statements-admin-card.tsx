import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type ProblemStatement,
  type ProblemStatementInput,
  hackathonsApi,
} from "@/features/hackathons/api/hackathons-api";
import { PointsMeter } from "@/features/hackathons/components/points-meter";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

interface Row {
  id?: string;
  text: string;
  points: string;
}

const toPoints = (value: string) => (value.trim() === "" ? 0 : Math.max(0, Math.floor(Number(value)) || 0));
const sum = (rows: Row[]) => rows.reduce((total, row) => total + toPoints(row.points), 0);

/** One list of "text + points" rows (sub-tasks or rubric rules) with add / remove. */
function PointsRows({
  rows,
  onChange,
  textLabel,
  textPlaceholder,
  addLabel,
}: {
  rows: Row[];
  onChange: (rows: Row[]) => void;
  textLabel: string;
  textPlaceholder: string;
  addLabel: string;
}) {
  const patch = (index: number, change: Partial<Row>) =>
    onChange(rows.map((row, i) => (i === index ? { ...row, ...change } : row)));
  return (
    <div className="space-y-2">
      {rows.map((row, index) => (
        <div key={index} className="flex items-start gap-2">
          <Input
            aria-label={`${textLabel} ${index + 1}`}
            placeholder={textPlaceholder}
            value={row.text}
            onChange={(e) => patch(index, { text: e.target.value })}
          />
          <Input
            aria-label={`Points for ${textLabel.toLowerCase()} ${index + 1}`}
            type="number"
            min={0}
            step={1}
            className="w-24 shrink-0"
            placeholder="Points"
            value={row.points}
            onChange={(e) => patch(index, { points: e.target.value })}
          />
          <Button
            type="button"
            size="icon"
            variant="ghost"
            aria-label={`Remove ${textLabel.toLowerCase()} ${index + 1}`}
            onClick={() => onChange(rows.filter((_, i) => i !== index))}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" onClick={() => onChange([...rows, { text: "", points: "" }])}>
        <Plus className="h-4 w-4" />
        {addLabel}
      </Button>
    </div>
  );
}

function TaskEditor({
  initial,
  busy,
  error,
  onSave,
  onCancel,
}: {
  initial: ProblemStatement | null;
  busy: boolean;
  error: string | null;
  onSave: (input: ProblemStatementInput) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [marks, setMarks] = useState(initial ? String(initial.marks) : "");
  const [showDescription, setShowDescription] = useState(Boolean(initial?.description));
  const [description, setDescription] = useState(initial?.description ?? "");
  const [subTasks, setSubTasks] = useState<Row[]>(
    (initial?.sub_tasks ?? []).map((s) => ({ id: s.id, text: s.title, points: String(s.points) }))
  );
  const [rubric, setRubric] = useState<Row[]>(
    (initial?.rubric ?? []).map((r) => ({ id: r.id, text: r.criterion, points: String(r.points) }))
  );

  const total = toPoints(marks);
  const subTotal = sum(subTasks);
  const rubricTotal = sum(rubric);

  const problem =
    title.trim().length < 2
      ? "Give the task a title."
      : (subTasks.length > 0 || rubric.length > 0) && total === 0
        ? "Set the task's marks first."
        : subTasks.some((r) => !r.text.trim())
          ? "Every sub-task needs a title."
          : rubric.some((r) => !r.text.trim())
            ? "Every rubric rule needs a description of what it is marked on."
            : subTotal > total
              ? `The sub-tasks add up to ${subTotal}, more than the task's ${total} marks.`
              : rubricTotal > total
                ? `The rubric adds up to ${rubricTotal}, more than the task's ${total} marks.`
                : null;

  const save = () =>
    onSave({
      title: title.trim(),
      marks: total,
      description: showDescription && description.trim() ? description.trim() : null,
      sub_tasks: subTasks.map((r) => ({ id: r.id, title: r.text.trim(), points: toPoints(r.points) })),
      rubric: rubric.map((r) => ({ id: r.id, criterion: r.text.trim(), points: toPoints(r.points) })),
    });

  return (
    <div className="space-y-5 rounded-md border bg-muted/30 p-4">
      <div className="grid gap-4 sm:grid-cols-[1fr_9rem]">
        <div className="space-y-2">
          <Label htmlFor="task-title">Task title</Label>
          <Input
            id="task-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Provision the server"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="task-marks">Task marks</Label>
          <Input
            id="task-marks"
            type="number"
            min={0}
            step={1}
            value={marks}
            onChange={(e) => setMarks(e.target.value)}
            placeholder="e.g. 20"
          />
        </div>
      </div>

      {/* The meters: how much of the task's marks the sub-tasks and the rubric account for. */}
      <div className="grid gap-4 rounded-md border bg-background p-3 sm:grid-cols-2">
        <PointsMeter label="Sub-tasks" value={subTotal} total={total} />
        <PointsMeter label="Rubric" value={rubricTotal} total={total} />
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={showDescription} onChange={(e) => setShowDescription(e.target.checked)} />
        Add a description
      </label>
      {showDescription && (
        <Textarea
          rows={6}
          aria-label="Task description"
          placeholder="Explain the task: what teams should do, what to submit, any constraints."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      )}

      <div className="space-y-2">
        <div>
          <h4 className="text-sm font-semibold">Sub-tasks</h4>
          <p className="text-xs text-muted-foreground">
            The parts of the task and what each one is worth. Students see these.
          </p>
        </div>
        <PointsRows
          rows={subTasks}
          onChange={setSubTasks}
          textLabel="Sub-task"
          textPlaceholder="Sub-task title"
          addLabel="Add sub-task"
        />
      </div>

      <div className="space-y-2">
        <div>
          <h4 className="text-sm font-semibold">Rubric</h4>
          <p className="text-xs text-muted-foreground">
            What you mark a submission on, and the most each rule can earn. Students see the rubric once they have
            submitted, and their marks against each rule after you score it.
          </p>
        </div>
        <PointsRows
          rows={rubric}
          onChange={setRubric}
          textLabel="Rubric rule"
          textPlaceholder="What it is marked on, e.g. Security group allows only what is needed"
          addLabel="Add rubric rule"
        />
      </div>

      {(problem || error) && <p className="text-sm text-destructive">{error ?? problem}</p>}
      <div className="flex gap-2">
        <Button disabled={!!problem || busy} onClick={save}>
          {busy ? "Saving..." : initial ? "Save changes" : "Add task"}
        </Button>
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

/** The tasks teams work through. Participants see each one as soon as it is added. */
export function ProblemStatementsAdminCard({ hackathonId }: { hackathonId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["hackathons", hackathonId, "problem-statements"];
  const { data: tasks } = useQuery({
    queryKey,
    queryFn: () => hackathonsApi.listProblemStatements(hackathonId),
  });
  const [editing, setEditing] = useState<ProblemStatement | "new" | null>(null);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey });
    queryClient.invalidateQueries({ queryKey: ["hackathons", hackathonId] });
  };
  const save = useMutation({
    mutationFn: (input: ProblemStatementInput) =>
      editing && editing !== "new"
        ? hackathonsApi.updateProblemStatement(hackathonId, editing.id, input)
        : hackathonsApi.addProblemStatement(hackathonId, input),
    onSuccess: () => {
      setEditing(null);
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => hackathonsApi.deleteProblemStatement(hackathonId, id),
    onSuccess: refresh,
  });

  const grandTotal = (tasks ?? []).reduce((total, task) => total + task.marks, 0);
  const startEditing = (value: ProblemStatement | "new") => {
    save.reset();
    setEditing(value);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Tasks</CardTitle>
        <CardDescription>
          The tasks teams work through. Each has its own marks, optional sub-tasks and a rubric you score against, and
          its own submission (a report and a registry / repository URL). Participants can see a task as soon as you add
          it, so add them when you want them released.
          {grandTotal > 0 && (
            <>
              {" "}
              All tasks together are worth <strong>{grandTotal}</strong> marks.
            </>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {tasks?.map((task, index) =>
          editing !== "new" && editing?.id === task.id ? (
            <TaskEditor
              key={task.id}
              initial={task}
              busy={save.isPending}
              error={save.isError ? errorMessage(save.error, "Could not save the task.") : null}
              onSave={(input) => save.mutate(input)}
              onCancel={() => setEditing(null)}
            />
          ) : (
            <div key={task.id} className="rounded-md border p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium">
                    {index + 1}. {task.title}
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
                    <Badge variant="secondary">{task.marks > 0 ? `${task.marks} marks` : "No marks set"}</Badge>
                    {task.sub_tasks.length > 0 && (
                      <Badge variant="outline">
                        {task.sub_tasks.length} sub-task{task.sub_tasks.length === 1 ? "" : "s"}
                      </Badge>
                    )}
                    {task.rubric.length > 0 ? (
                      <Badge variant="outline">
                        Rubric {task.rubric.reduce((t, r) => t + r.points, 0)} / {task.marks}
                      </Badge>
                    ) : (
                      <Badge variant="outline">No rubric</Badge>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button size="sm" variant="ghost" onClick={() => startEditing(task)}>
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive"
                    disabled={remove.isPending}
                    onClick={() => {
                      if (window.confirm("Delete this task? Any submissions teams made for it are deleted too.")) {
                        remove.mutate(task.id);
                      }
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </div>
              {task.description && (
                <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-sm text-muted-foreground">{task.description}</p>
              )}
            </div>
          )
        )}
        {(tasks?.length ?? 0) === 0 && !editing && <p className="text-sm text-muted-foreground">No tasks yet.</p>}

        {editing === "new" ? (
          <TaskEditor
            initial={null}
            busy={save.isPending}
            error={save.isError ? errorMessage(save.error, "Could not save the task.") : null}
            onSave={(input) => save.mutate(input)}
            onCancel={() => setEditing(null)}
          />
        ) : (
          editing === null && (
            <Button variant="outline" onClick={() => startEditing("new")}>
              <Plus className="h-4 w-4" />
              Add task
            </Button>
          )
        )}
        {remove.isError && <p className="text-sm text-destructive">{errorMessage(remove.error, "Could not delete.")}</p>}
      </CardContent>
    </Card>
  );
}
