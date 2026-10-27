import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { CandidateItem, CandidatesAddResult, CandidatesResult } from "@/features/institutions/api/institutions-api";
import { errorMessage } from "@/features/institutions/lib/format";
import { STATUS_LABELS, addable, buildItems, sourceLine } from "@/features/institutions/lib/validation";

/**
 * Validate the people of an event's linked exams and hackathons before they become students.
 *
 * Everyone who appears more than once (in several exams, an exam and a hackathon, or written twice) arrives combined into
 * one entry per email. Check the entries, correct a name or phone where needed, tick the ones you verify, and add them to
 * the institution and the event. Nobody is added until you confirm; people with no email cannot be matched and are only listed.
 */
export function ValidateStudentsDialog({
  eventName,
  queryKey,
  load,
  add,
  onAdded,
  onClose,
}: {
  eventName: string;
  queryKey: readonly unknown[];
  load: () => Promise<CandidatesResult>;
  add: (items: CandidateItem[]) => Promise<CandidatesAddResult>;
  onAdded: () => void;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const found = useQuery({ queryKey, queryFn: load, gcTime: 0 });
  const [verified, setVerified] = useState<Set<string>>(new Set());
  const [edits, setEdits] = useState<Record<string, { name?: string; phone?: string }>>({});
  const [done, setDone] = useState<CandidatesAddResult | null>(null);

  const candidates = useMemo(() => found.data?.candidates ?? [], [found.data]);
  const ticked = useMemo(() => buildItems(candidates, verified, edits), [candidates, verified, edits]);
  const addableEmails = useMemo(() => addable(candidates), [candidates]);

  const save = useMutation({
    mutationFn: () => add(ticked),
    onSuccess: (result) => {
      setDone(result);
      setVerified(new Set());
      onAdded();
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  const toggle = (email: string, on: boolean) => {
    const next = new Set(verified);
    if (on) next.add(email);
    else next.delete(email);
    setVerified(next);
  };
  const edit = (email: string, patch: { name?: string; phone?: string }) => setEdits({ ...edits, [email]: { ...edits[email], ...patch } });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-6xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Validate students: {eventName}</DialogTitle>
          <DialogDescription>
            People found in the exams and hackathons linked to this event, combined by email. Verify them, correct a name or phone if needed, and add them to the
            institution. Nothing is added until you confirm.
          </DialogDescription>
        </DialogHeader>

        {done && (
          <p className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200">{done.message}</p>
        )}

        {found.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : found.isError || !found.data ? (
          <p className="text-sm text-destructive">{errorMessage(found.error, "Could not load the people to validate.")}</p>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{found.data.message}</p>

            {candidates.length > 0 && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" size="sm" variant="outline" disabled={addableEmails.length === 0} onClick={() => setVerified(new Set(addableEmails))}>
                      Verify all that can be added ({addableEmails.length})
                    </Button>
                    <Button type="button" size="sm" variant="ghost" disabled={verified.size === 0} onClick={() => setVerified(new Set())}>
                      Clear
                    </Button>
                  </div>
                  <Button disabled={ticked.length === 0 || save.isPending} onClick={() => save.mutate()}>
                    {save.isPending ? "Adding..." : `Add ${ticked.length || ""} verified to the institution`}
                  </Button>
                </div>
                {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not add them.")}</p>}

                <div className="overflow-x-auto rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-10" />
                        <TableHead>Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Phone</TableHead>
                        <TableHead>Found in</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {candidates.map((c) => {
                        const status = STATUS_LABELS[c.status];
                        const edited = edits[c.email] ?? {};
                        return (
                          <TableRow key={c.email} className={c.addable ? undefined : "opacity-70"}>
                            <TableCell>
                              <input
                                type="checkbox"
                                aria-label={`Verify ${c.name}`}
                                disabled={!c.addable}
                                checked={verified.has(c.email)}
                                onChange={(e) => toggle(c.email, e.target.checked)}
                              />
                            </TableCell>
                            <TableCell className="min-w-48">
                              {c.status === "new" ? (
                                <Input aria-label={`Name for ${c.email}`} value={edited.name ?? c.name} maxLength={255} onChange={(e) => edit(c.email, { name: e.target.value })} />
                              ) : (
                                <span className="font-medium">{c.existing_name ?? c.name}</span>
                              )}
                              {c.name_variants.length > 0 && <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">Also written: {c.name_variants.join(", ")}</p>}
                              {c.issues.includes("name_differs") && c.existing_name && <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">Found as "{c.name}"; the institution has "{c.existing_name}".</p>}
                            </TableCell>
                            <TableCell className="text-sm">
                              {c.email}
                              {c.issues.includes("invalid_email") && <p className="text-xs text-destructive">Not a valid email address, so this person cannot be added.</p>}
                            </TableCell>
                            <TableCell className="w-36">
                              {c.status === "new" ? (
                                <Input aria-label={`Phone for ${c.email}`} value={edited.phone ?? c.phone ?? ""} maxLength={50} onChange={(e) => edit(c.email, { phone: e.target.value })} />
                              ) : (
                                <span className="text-sm text-muted-foreground">{c.phone ?? "-"}</span>
                              )}
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              {sourceLine(c.sources)}
                              {c.entries > 1 && <p className="mt-0.5 font-medium text-foreground">Combined from {c.entries} entries</p>}
                            </TableCell>
                            <TableCell>
                              <Badge variant={status.variant}>{status.label}</Badge>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </>
            )}

            {found.data.without_email.length > 0 && (
              <div className="rounded-md border p-3 text-sm">
                <p className="font-medium">{found.data.without_email.length} without an email (cannot be matched, so not added)</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {found.data.without_email.map((n) => `${n.name} (${n.source.kind === "exam" ? "exam" : "hackathon"}: ${n.source.title})`).join(" · ")}
                </p>
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
