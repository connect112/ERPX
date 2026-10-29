import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { type PentrixBooking, type Scope, useMyBookings } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { BookingDialog } from "@/features/pentrix-ops/components/booking-dialog";
import { STATUS_TONE, istDate, istTime } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";

/** The appointments assigned to the signed-in team member, and nothing else: no other candidate's details and no administration. */
export function MyBookingsPage() {
  const [scope, setScope] = useState<Scope>("upcoming");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<PentrixBooking | null>(null);
  const mine = useMyBookings(scope, page);
  const data = mine.data;
  const pages = data ? Math.max(Math.ceil(data.total / data.page_size), 1) : 1;

  return (
    <div className="space-y-5 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">My Assigned Bookings</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          The Pentrix appointments assigned to you. Times are in India Standard Time. You will get an email 30 minutes and 5 minutes before each one, and when it starts.
        </p>
      </div>
      <div role="tablist" aria-label="Which appointments" className="flex gap-1">
        {(["upcoming", "past"] as Scope[]).map((s) => (
          <Button key={s} role="tab" aria-selected={scope === s} size="sm" variant={scope === s ? "default" : "ghost"} onClick={() => { setScope(s); setPage(1); }}>
            {s === "upcoming" ? "Upcoming" : "Past and closed"}
          </Button>
        ))}
      </div>
      {mine.isLoading && <Skeleton className="h-40" />}
      {mine.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(mine.error, "Could not load your appointments.")}</p>}
      {data && data.items.length === 0 && <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">Nothing is assigned to you{scope === "upcoming" ? " right now" : ""}.</p>}
      <ul className="grid gap-3 md:grid-cols-2" aria-label="Assigned appointments">
        {data?.items.map((b) => (
          <li key={b.id}>
            <Card>
              <CardContent className="space-y-3 p-5">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{b.candidate_name || "Candidate"}</p>
                    <p className="truncate text-xs text-muted-foreground">{b.candidate_email}</p>
                  </div>
                  <Badge variant={STATUS_TONE[b.status]}>{b.status_label}</Badge>
                </div>
                <p className="text-sm">
                  <span className="font-medium">{istDate(b.slot_start)}</span> · {istTime(b.slot_start)} IST · {b.duration_minutes} min
                </p>
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  {b.meeting_url ? (
                    <a className="text-primary hover:underline" href={b.meeting_url} target="_blank" rel="noopener noreferrer">Join meeting</a>
                  ) : (
                    <span className="text-muted-foreground">No meeting link yet</span>
                  )}
                  <Button size="sm" variant="outline" className="ml-auto" aria-label={`Open the appointment with ${b.candidate_name}`} onClick={() => setOpen(b)}>Open</Button>
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
      {data && data.total > data.page_size && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Page {data.page} of {pages}</span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      )}
      {open && <BookingDialog booking={open} mode="mine" onClose={() => setOpen(null)} />}
    </div>
  );
}
