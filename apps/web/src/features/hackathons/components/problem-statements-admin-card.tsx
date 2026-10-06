import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { type ProblemStatement, hackathonsApi } from "@/features/hackathons/api/hackathons-api";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

/** The challenges teams can choose from. Participants see each one as soon as it is added. */
export function ProblemStatementsAdminCard({ hackathonId }: { hackathonId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["hackathons", hackathonId, "problem-statements"];
  const { data: statements } = useQuery({
    queryKey,
    queryFn: () => hackathonsApi.listProblemStatements(hackathonId),
  });
  const [editing, setEditing] = useState<ProblemStatement | "new" | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const open = (statement: ProblemStatement | "new") => {
    setEditing(statement);
    setTitle(statement === "new" ? "" : statement.title);
    setDescription(statement === "new" ? "" : statement.description);
  };

  const save = useMutation({
    mutationFn: () =>
      editing && editing !== "new"
        ? hackathonsApi.updateProblemStatement(hackathonId, editing.id, title.trim(), description.trim())
        : hackathonsApi.addProblemStatement(hackathonId, title.trim(), description.trim()),
    onSuccess: () => {
      setEditing(null);
      queryClient.invalidateQueries({ queryKey });
      queryClient.invalidateQueries({ queryKey: ["hackathons", hackathonId, "teams"] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => hackathonsApi.deleteProblemStatement(hackathonId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      queryClient.invalidateQueries({ queryKey: ["hackathons", hackathonId, "teams"] });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Tasks</CardTitle>
        <CardDescription>
          The tasks teams work through. Each task has its own submission (a report and a registry / repository URL) that
          you score. Participants can read a task as soon as you add it, so add them when you want them released.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {statements?.map((statement, index) => (
          <div key={statement.id} className="rounded-md border p-3">
            <div className="flex items-start justify-between gap-2">
              <p className="font-medium">
                {index + 1}. {statement.title}
              </p>
              <div className="flex shrink-0 gap-1">
                <Button size="sm" variant="ghost" onClick={() => open(statement)}>
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-destructive"
                  disabled={remove.isPending}
                  onClick={() => {
                    if (window.confirm("Delete this task? Any submissions teams made for it are deleted too.")) {
                      remove.mutate(statement.id);
                    }
                  }}
                >
                  Delete
                </Button>
              </div>
            </div>
            <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-sm text-muted-foreground">{statement.description}</p>
          </div>
        ))}
        {(statements?.length ?? 0) === 0 && !editing && (
          <p className="text-sm text-muted-foreground">No tasks yet.</p>
        )}

        {editing ? (
          <div className="space-y-3 rounded-md border bg-muted/30 p-3">
            <Input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
            <Textarea
              rows={8}
              placeholder="Describe the problem, what teams should build, constraints, and how it will be judged."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <div className="flex gap-2">
              <Button
                disabled={title.trim().length < 2 || !description.trim() || save.isPending}
                onClick={() => save.mutate()}
              >
                {save.isPending ? "Saving..." : editing === "new" ? "Add task" : "Save changes"}
              </Button>
              <Button variant="outline" onClick={() => setEditing(null)}>
                Cancel
              </Button>
            </div>
            {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save.")}</p>}
          </div>
        ) : (
          <Button variant="outline" onClick={() => open("new")}>
            Add task
          </Button>
        )}
        {remove.isError && <p className="text-sm text-destructive">{errorMessage(remove.error, "Could not delete.")}</p>}
      </CardContent>
    </Card>
  );
}
