import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/features/institutions/lib/format";
import { type Instructor, instructorKeys, instructorsApi } from "@/features/our-internships/api/instructors-api";
import { STATUS, dayEnd, dayStart, periodOk, periodText, toDay } from "@/features/our-internships/lib/instructors";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

/**
 * The instructors of the internship: trainers who work on it with their own login, for a period. One or many; each with
 * their own dates. They can do everything except delete. Outside their dates the internship is invisible to them.
 */
export function InstructorsTab({ internshipId }: { internshipId: string }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Instructor | "new" | null>(null);
  const list = useQuery({ queryKey: instructorKeys.list(internshipId), queryFn: () => instructorsApi.list(internshipId) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["our-internships", "instructors", internshipId] });
  const remove = useMutation({ mutationFn: (id: string) => instructorsApi.remove(internshipId, id), onSuccess: refresh });

  if (list.isLoading) return <Skeleton className="h-40 w-full" />;
  if (list.isError) return <p className="text-sm text-destructive">Could not load the instructors.</p>;
  const items = list.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Give trainers access to this internship. They sign in with their trainer account, see only this internship, and can add, edit, view, mark and validate
          everything in it, but cannot delete anything. Give each a period, and the internship disappears for them when it ends.
        </p>
        <Button onClick={() => setEditing("new")}>
          <Plus className="h-4 w-4" />
          Add instructor
        </Button>
      </div>
      {remove.isError && <p className="text-sm text-destructive">{errorMessage(remove.error, "Could not remove the instructor.")}</p>}

      {items.length === 0 ? (
        <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">No instructors yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Instructor</TableHead>
                <TableHead>Access</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Note</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((i) => {
                const status = STATUS[i.status];
                return (
                  <TableRow key={i.id}>
                    <TableCell>
                      <div className="font-medium">{i.name}</div>
                      <div className="text-xs text-muted-foreground">{i.email}</div>
                    </TableCell>
                    <TableCell>{periodText(i.access_from, i.access_until)}</TableCell>
                    <TableCell>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-sm text-muted-foreground">{i.note ?? "-"}</TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button size="icon" variant="ghost" aria-label={`Change access for ${i.name}`} onClick={() => setEditing(i)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Remove ${i.name}`}
                          disabled={remove.isPending}
                          onClick={() => {
                            if (window.confirm(`Take ${i.name}'s access to this internship away now?`)) remove.mutate(i.id);
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {editing && <InstructorDialog internshipId={internshipId} instructor={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={() => void refresh()} />}
    </div>
  );
}

function InstructorDialog({ internshipId, instructor, onClose, onSaved }: { internshipId: string; instructor: Instructor | null; onClose: () => void; onSaved: () => void }) {
  const options = useQuery({ queryKey: instructorKeys.options(internshipId), queryFn: () => instructorsApi.options(internshipId), enabled: !instructor });
  const [trainerId, setTrainerId] = useState("");
  const [from, setFrom] = useState(toDay(instructor?.access_from ?? null));
  const [until, setUntil] = useState(toDay(instructor?.access_until ?? null));
  const [note, setNote] = useState(instructor?.note ?? "");

  const save = useMutation({
    mutationFn: () => {
      const body = { access_from: dayStart(from), access_until: dayEnd(until), note: note.trim() || null };
      return instructor ? instructorsApi.update(internshipId, instructor.id, body) : instructorsApi.add(internshipId, { trainer_id: trainerId, ...body });
    },
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });
  const ok = periodOk(from, until) && (!!instructor || !!trainerId);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{instructor ? `Access for ${instructor.name}` : "Add an instructor"}</DialogTitle>
          <DialogDescription>
            {instructor ? "Change the dates to extend, shorten or end the access." : "Choose a trainer and when they may work on this internship. Leave the end empty to give access until you remove it."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {!instructor && (
            <div className="space-y-1.5">
              <Label htmlFor="ins-trainer">Trainer</Label>
              <select id="ins-trainer" className={selectClass} value={trainerId} onChange={(e) => setTrainerId(e.target.value)}>
                <option value="">Choose a trainer...</option>
                {options.data?.map((o) => (
                  <option key={o.trainer_id} value={o.trainer_id}>
                    {o.name}
                    {o.email ? ` (${o.email})` : ""}
                  </option>
                ))}
              </select>
              {options.isSuccess && options.data.length === 0 && <p className="text-xs text-muted-foreground">Every active trainer with a login already has access, or there are none yet.</p>}
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="ins-from">From (optional)</Label>
              <Input id="ins-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ins-until">Until (optional)</Label>
              <Input id="ins-until" type="date" value={until} onChange={(e) => setUntil(e.target.value)} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">The last day is included. With no start, access begins now.</p>
          {!periodOk(from, until) && <p className="text-sm text-destructive">The end must not be before the start.</p>}
          <div className="space-y-1.5">
            <Label htmlFor="ins-note">Note (optional)</Label>
            <Input id="ins-note" value={note} maxLength={255} placeholder="Guest mentor for the October batch" onChange={(e) => setNote(e.target.value)} />
          </div>
          {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save.")}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={!ok || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Saving..." : instructor ? "Save access" : "Give access"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
