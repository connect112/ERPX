import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useBookings } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { STATUS_TONE, istDate, istTime } from "@/features/pentrix-ops/lib/format";

const FILTERS = { scope: "upcoming", status: "", staff: "", q: "", page: 1, pageSize: 6 } as const;

/** The next appointments candidates have booked on Pentrix. Used on the Pentrix overview and on the main dashboard. Shows nothing if Pentrix is not set up. */
export function UpcomingBookingsWidget({ title = "Upcoming Pentrix bookings" }: { title?: string }) {
  const bookings = useBookings(FILTERS);
  if (bookings.isError) return null; // not set up for this organisation, or not reachable: the dashboard is not the place for that error
  const data = bookings.data;

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-base">{title}</CardTitle>
          <CardDescription>{data ? (data.total === 0 ? "Nothing booked" : `${data.total} upcoming`) : "Times are in India Standard Time."}</CardDescription>
        </div>
        <Link to="/pentrix-ops/bookings" className="text-sm text-primary hover:underline">View All Pentrix Bookings</Link>
      </CardHeader>
      <CardContent className="p-0">
        {bookings.isLoading && <Skeleton className="m-6 h-24" />}
        {data && data.items.length === 0 && <p className="px-6 pb-6 text-sm text-muted-foreground">No appointments are booked right now.</p>}
        {data && data.items.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Candidate</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Time</TableHead>
                <TableHead>Assigned to</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((b) => (
                <TableRow key={b.id}>
                  <TableCell className="font-medium">{b.candidate_name || "Candidate"}</TableCell>
                  <TableCell>{istDate(b.slot_start)}</TableCell>
                  <TableCell>{istTime(b.slot_start)}</TableCell>
                  <TableCell>{b.assigned_staff_name ?? <span className="text-muted-foreground">Not assigned</span>}</TableCell>
                  <TableCell><Badge variant={STATUS_TONE[b.status]}>{b.status_label}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
