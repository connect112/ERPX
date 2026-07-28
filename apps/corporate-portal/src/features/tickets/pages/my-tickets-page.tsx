import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { NewTicketDialog } from "@/features/tickets/components/new-ticket-dialog";
import { useMyTickets } from "@/features/tickets/api/tickets-hooks";

export function MyTicketsPage() {
  const { data: tickets, isLoading } = useMyTickets();

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">My Tickets</h1>
          <p className="text-sm text-muted-foreground">Support tickets raised by your organization.</p>
        </div>
        <NewTicketDialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All tickets</CardTitle>
          <CardDescription>Click a ticket to view details and reply.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : tickets && tickets.length > 0 ? (
            <ul className="divide-y">
              {tickets.map((ticket) => (
                <li key={ticket.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">{ticket.subject}</p>
                    <p className="text-xs text-muted-foreground">
                      {ticket.ticket_number} &middot; {ticket.priority}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="capitalize">
                      {ticket.status.replace("_", " ")}
                    </Badge>
                    <Link
                      to={`/tickets/${ticket.id}`}
                      className="text-sm font-medium text-primary hover:underline"
                    >
                      View
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              You have not raised any support tickets yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
