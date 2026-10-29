import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type BookingFilters, type PentrixBooking, type Scope, pentrixApi, pentrixKeys, useBookings, useStaff } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { BookingDialog } from "@/features/pentrix-ops/components/booking-dialog";
import { STATUS_TONE, istDate, istTime, usePentrixPermissions } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";
import { selectClass } from "@/features/our-internships/components/letter-fields";

const SCOPES: { id: Scope; label: string }[] = [
  { id: "upcoming", label: "Upcoming" },
  { id: "past", label: "Past and closed" },
  { id: "all", label: "All" },
];
const STATUSES = [
  ["", "Any status"], ["confirmed", "Confirmed"], ["requested", "Scheduled"], ["in_progress", "In progress"], ["completed", "Completed"], ["cancelled", "Cancelled"], ["no_show", "No show"],
];

/** Every Pentrix appointment, with who it is with, who it is assigned to, and what state it is in. Pentrix owns the data; this is a live copy. */
export function BookingsPage() {
  const perms = usePentrixPermissions();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<BookingFilters>({ scope: "upcoming", status: "", staff: "", q: "", page: 1 });
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<PentrixBooking | null>(null);
  const bookings = useBookings(filters);
  const staff = useStaff();
  const sync = useMutation({ mutationFn: pentrixApi.sync, onSuccess: () => void queryClient.invalidateQueries({ queryKey: pentrixKeys.all }) });
  const set = (patch: Partial<BookingFilters>) => setFilters((f) => ({ ...f, ...patch, page: patch.page ?? 1 }));
  const data = bookings.data;
  const pages = data ? Math.max(Math.ceil(data.total / data.page_size), 1) : 1;

  return (
    <div className="space-y-5 p-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pentrix Bookings</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Appointments candidates book on the Pentrix portal. Times are in India Standard Time. Assigning, rescheduling and the other actions are carried out in
            Pentrix, so the candidate sees them straight away.
          </p>
        </div>
        {perms.canManage && (
          <Button variant="outline" disabled={sync.isPending} onClick={() => sync.mutate()}>
            <RefreshCw className={`h-4 w-4 ${sync.isPending ? "animate-spin" : ""}`} /> Refresh from Pentrix
          </Button>
        )}
      </div>
      {sync.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(sync.error, "Could not reach Pentrix.")}</p>}

      <Card>
        <CardHeader className="space-y-4">
          <div role="tablist" aria-label="Which appointments" className="flex flex-wrap gap-1">
            {SCOPES.map((s) => (
              <Button key={s.id} role="tab" aria-selected={filters.scope === s.id} size="sm" variant={filters.scope === s.id ? "default" : "ghost"} onClick={() => set({ scope: s.id })}>
                {s.label}
              </Button>
            ))}
          </div>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              set({ q: search.trim() });
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="pb-search">Search</Label>
              <Input id="pb-search" className="w-56" placeholder="Name, email or reference" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="pb-status">Status</Label>
              <select id="pb-status" className={`${selectClass} w-40`} value={filters.status} onChange={(e) => set({ status: e.target.value })}>
                {STATUSES.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="pb-assigned">Assigned to</Label>
              <select id="pb-assigned" className={`${selectClass} w-48`} value={filters.staff} onChange={(e) => set({ staff: e.target.value })}>
                <option value="">Anyone</option>
                <option value="unassigned">Not assigned</option>
                {staff.data?.map((s) => (
                  <option key={s.id} value={s.id}>{s.full_name}</option>
                ))}
              </select>
            </div>
            <Button type="submit" variant="outline">Search</Button>
          </form>
          <CardDescription>{data ? `${data.total} appointment${data.total === 1 ? "" : "s"}` : ""}</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {bookings.isLoading && <Skeleton className="m-6 h-40" />}
          {bookings.isError && <p role="alert" className="p-6 text-sm text-destructive">{errorMessage(bookings.error, "Could not load the appointments.")}</p>}
          {data && data.items.length === 0 && <p className="p-8 text-center text-sm text-muted-foreground">No appointments match.</p>}
          {data && data.items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidate</TableHead>
                  <TableHead>When (IST)</TableHead>
                  <TableHead>Assigned to</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Meeting</TableHead>
                  <TableHead className="text-right"><span className="sr-only">Open</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((b) => (
                  <TableRow key={b.id}>
                    <TableCell>
                      <div className="font-medium">{b.candidate_name || "Candidate"}</div>
                      <div className="text-xs text-muted-foreground">{b.candidate_email}</div>
                    </TableCell>
                    <TableCell>
                      <div>{istDate(b.slot_start)}</div>
                      <div className="text-xs text-muted-foreground">{istTime(b.slot_start)} · {b.duration_minutes} min</div>
                    </TableCell>
                    <TableCell>{b.assigned_staff_name ?? <span className="text-muted-foreground">Not assigned</span>}</TableCell>
                    <TableCell><Badge variant={STATUS_TONE[b.status]}>{b.status_label}</Badge></TableCell>
                    <TableCell>
                      {b.meeting_url ? (
                        <a className="text-primary hover:underline" href={b.meeting_url} target="_blank" rel="noopener noreferrer">Link</a>
                      ) : (
                        <span className="text-muted-foreground">None</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" aria-label={`Open the appointment of ${b.candidate_name}`} onClick={() => setOpen(b)}>
                        {perms.canManage ? "Manage" : "View"}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {data && data.total > data.page_size && (
            <div className="flex items-center justify-between border-t px-6 py-3 text-sm">
              <span className="text-muted-foreground">Page {data.page} of {pages}</span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={filters.page <= 1} onClick={() => set({ page: filters.page - 1 })}>Previous</Button>
                <Button size="sm" variant="outline" disabled={filters.page >= pages} onClick={() => set({ page: filters.page + 1 })}>Next</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      {open && <BookingDialog booking={open} mode={perms.canManage ? "admin" : "view"} onClose={() => setOpen(null)} />}
    </div>
  );
}
