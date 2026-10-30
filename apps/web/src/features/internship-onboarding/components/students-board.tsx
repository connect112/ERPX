import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Mail, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/features/institutions/lib/format";
import { onboardingFlowApi } from "@/features/internship-onboarding/api";
import { StudentDetailDialog } from "@/features/internship-onboarding/components/student-detail-dialog";
import { fromLocalInput, inZone, money, statusLabel, statusTone } from "@/features/internship-onboarding/lib/format";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";
const METRICS: [string, string][] = [
  ["selected", "Selected"], ["accepted", "Accepted"], ["declined", "Declined"], ["not_started", "Not started"],
  ["in_progress", "In progress"], ["documents_to_review", "Documents to review"], ["payments_to_verify", "Payments to verify"],
  ["payments_confirmed", "Paid"], ["payments_failed", "Payment failed"], ["reopened", "Reopened"], ["completed", "Completed"],
  ["lms_granted", "LMS access"],
];  // prettier-ignore

export function StudentsBoard({ internshipId, timezone, canManage }: { internshipId: string; timezone: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const board = useQuery({ queryKey: ["onboarding-flow", internshipId, "board"], queryFn: () => onboardingFlowApi.board(internshipId) });
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [overall, setOverall] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<"invite" | "reopen" | null>(null);
  const [reopen, setReopen] = useState({ until: "", reason: "", late_fee: "none", amount: "" });
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["onboarding-flow", internshipId] });

  const rows = useMemo(
    () =>
      (board.data?.rows ?? []).filter(
        (r) =>
          (!overall || r.overall_status === overall) &&
          (!search || `${r.name} ${r.email} ${r.reference ?? ""}`.toLowerCase().includes(search.toLowerCase()))
      ),
    [board.data, overall, search]
  );
  const statuses = useMemo(() => [...new Set((board.data?.rows ?? []).map((r) => r.overall_status))].sort(), [board.data]);

  const done = (text: string) => {
    setNotice({ ok: true, text });
    setConfirm(null);
    setPicked(new Set());
    refresh();
  };
  const invite = useMutation({
    mutationFn: () => onboardingFlowApi.invite(internshipId, [...picked]),
    onSuccess: (r) => done(`Queued ${r.queued} invitation(s).${r.skipped.length ? ` Skipped: ${r.skipped.map((s) => `${s.name} (${s.reason})`).join("; ")}` : ""}`),
    onError: (e) => setNotice({ ok: false, text: errorMessage(e, "The invitations could not be queued.") }),
  });
  const doReopen = useMutation({
    mutationFn: () =>
      onboardingFlowApi.reopen(internshipId, {
        student_ids: [...picked],
        until: fromLocalInput(reopen.until) ?? "",
        reason: reopen.reason,
        late_fee: reopen.late_fee,
        late_fee_amount: reopen.late_fee === "custom" ? reopen.amount : null,
      }),
    onSuccess: (r) => done(`Reopened ${r.reopened}.${r.skipped.length ? ` Skipped: ${r.skipped.map((s) => `${s.name} (${s.reason})`).join("; ")}` : ""}`),
    onError: (e) => setNotice({ ok: false, text: errorMessage(e, "Could not reopen.") }),
  });

  const toggle = (id: string, on: boolean) => {
    const next = new Set(picked);
    if (on) next.add(id);
    else next.delete(id);
    setPicked(next);
  };
  const m = board.data?.metrics ?? {};

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
        {METRICS.map(([key, label]) => (
          <div key={key} className="rounded-md border p-2">
            <div className="text-xs text-muted-foreground">{label}</div>
            <div className="text-lg font-semibold">{m[key] ?? 0}</div>
          </div>
        ))}
      </div>
      {board.data && (
        <p className="text-sm text-muted-foreground">
          Payable {money(board.data.money.payable)} · received {money(board.data.money.received)} · outstanding{" "}
          {money(board.data.money.outstanding)}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input aria-label="Search students" className="pl-8" placeholder="Name, email or reference" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select aria-label="Filter by status" className={selectClass} value={overall} onChange={(e) => setOverall(e.target.value)}>
          <option value="">All statuses</option>
          {statuses.map((s) => (
            <option key={s} value={s}>
              {statusLabel(s)}
            </option>
          ))}
        </select>
        {canManage && (
          <>
            <Button size="sm" variant="outline" disabled={picked.size === 0} onClick={() => setConfirm("invite")}>
              <Mail className="h-4 w-4" />
              Send invitation{picked.size > 1 ? "s" : ""}
            </Button>
            <Button size="sm" variant="outline" disabled={picked.size === 0} onClick={() => setConfirm("reopen")}>
              <CalendarClock className="h-4 w-4" />
              Reopen / extend
            </Button>
          </>
        )}
      </div>
      {notice && <p className={`text-sm ${notice.ok ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`}>{notice.text}</p>}

      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8">
                <input
                  type="checkbox"
                  aria-label="Choose every student shown"
                  checked={rows.length > 0 && rows.every((r) => picked.has(r.student_id))}
                  onChange={(e) => setPicked(e.target.checked ? new Set(rows.map((r) => r.student_id)) : new Set())}
                />
              </TableHead>
              <TableHead>Student</TableHead>
              <TableHead>Offer</TableHead>
              <TableHead>Documents</TableHead>
              <TableHead>Payment</TableHead>
              <TableHead>Received / due</TableHead>
              <TableHead>Overall</TableHead>
              <TableHead>Deadline</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.student_id} className="cursor-pointer" onClick={() => setOpen(r.student_id)}>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" aria-label={`Choose ${r.name}`} checked={picked.has(r.student_id)} onChange={(e) => toggle(r.student_id, e.target.checked)} />
                </TableCell>
                <TableCell>
                  <div className="font-medium">{r.name}</div>
                  <div className="text-xs text-muted-foreground">{r.reference ?? r.email}</div>
                </TableCell>
                {[r.offer_status, r.document_status, r.payment_status].map((s, i) => (
                  <TableCell key={i}>
                    <Badge variant={statusTone(s)}>{statusLabel(s)}</Badge>
                    {i === 1 && r.documents_awaiting_review > 0 && <span className="ml-1 text-xs text-amber-700">({r.documents_awaiting_review} to review)</span>}
                  </TableCell>
                ))}
                <TableCell className="whitespace-nowrap text-sm">
                  {money(r.received)} / {money(r.payable)}
                </TableCell>
                <TableCell>
                  <Badge variant={statusTone(r.overall_status)}>{statusLabel(r.overall_status)}</Badge>
                  {r.reopened && <span className="ml-1 text-xs text-muted-foreground">reopened</span>}
                </TableCell>
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{inZone(r.deadline, timezone)}</TableCell>
              </TableRow>
            ))}
            {!board.isLoading && rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">
                  {board.isError ? errorMessage(board.error, "Could not load the students.") : "No students match."}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{confirm === "invite" ? "Send onboarding invitations" : "Reopen onboarding"}</DialogTitle>
            <DialogDescription>
              {picked.size} student{picked.size === 1 ? "" : "s"} selected.{" "}
              {confirm === "invite"
                ? "Each gets a new personal link by email; any link sent before stops working."
                : "Only these students get the new deadline; the internship itself stays closed for everyone else."}
            </DialogDescription>
          </DialogHeader>
          {confirm === "reopen" && (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="reopen-until">New deadline</Label>
                <Input id="reopen-until" type="datetime-local" value={reopen.until} onChange={(e) => setReopen({ ...reopen, until: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reopen-reason">Reason</Label>
                <Input id="reopen-reason" value={reopen.reason} onChange={(e) => setReopen({ ...reopen, reason: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reopen-fee">Late fee (needs the finance permission)</Label>
                <select id="reopen-fee" className={`${selectClass} w-full`} value={reopen.late_fee} onChange={(e) => setReopen({ ...reopen, late_fee: e.target.value })}>
                  <option value="none">No late fee</option>
                  <option value="config">The internship's late fee</option>
                  <option value="custom">A custom amount</option>
                  <option value="waive">Waive a late fee charged earlier</option>
                </select>
              </div>
              {reopen.late_fee === "custom" && (
                <Input aria-label="Late fee amount" inputMode="decimal" placeholder="500.00" value={reopen.amount} onChange={(e) => setReopen({ ...reopen, amount: e.target.value })} />
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirm(null)}>
              Cancel
            </Button>
            {confirm === "invite" ? (
              <Button disabled={invite.isPending} onClick={() => invite.mutate()}>
                Send {picked.size}
              </Button>
            ) : (
              <Button disabled={doReopen.isPending || !reopen.until || !reopen.reason.trim()} onClick={() => doReopen.mutate()}>
                Reopen {picked.size}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {open && <StudentDetailDialog internshipId={internshipId} studentId={open} timezone={timezone} canManage={canManage} onClose={() => setOpen(null)} />}
    </div>
  );
}
