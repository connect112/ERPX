import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyClientProfile } from "@/features/dashboard/api/client-hooks";
import { useMyTickets } from "@/features/tickets/api/tickets-hooks";
import { useMyContracts } from "@/features/contracts/api/contracts-hooks";

export function DashboardPage() {
  const { data: corpClient, isLoading: clientLoading } = useMyClientProfile();
  const { data: tickets, isLoading: ticketsLoading } = useMyTickets();
  const { data: contracts, isLoading: contractsLoading } = useMyContracts();

  const openTickets = tickets?.filter((t) => !["resolved", "closed"].includes(t.status)).length ?? 0;
  const activeContracts = contracts?.filter((c) => c.status === "active").length ?? 0;

  return (
    <div className="space-y-6 p-6">
      <div>
        {clientLoading ? (
          <Skeleton className="h-8 w-64" />
        ) : (
          <h1 className="text-2xl font-semibold">Welcome, {corpClient?.name}</h1>
        )}
        <p className="text-sm text-muted-foreground">Here's an overview of your account with us.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Open tickets</CardDescription>
            <CardTitle className="text-lg">{ticketsLoading ? "…" : openTickets}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Active contracts</CardDescription>
            <CardTitle className="text-lg">{contractsLoading ? "…" : activeContracts}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Account status</CardDescription>
            <CardTitle className="text-lg capitalize">{corpClient?.status ?? "—"}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Tickets</CardTitle>
          <CardDescription>Your most recently raised support tickets.</CardDescription>
        </CardHeader>
        <CardContent>
          {ticketsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : tickets && tickets.length > 0 ? (
            <ul className="divide-y">
              {tickets.slice(0, 5).map((ticket) => (
                <li key={ticket.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">{ticket.subject}</p>
                    <p className="text-xs text-muted-foreground">{ticket.ticket_number}</p>
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
