import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SupportTicketPublic } from "@/features/corporate/tickets/api/tickets-api";
import { useTicketsList } from "@/features/corporate/tickets/api/tickets-hooks";
import { TicketDetailDialog } from "@/features/corporate/tickets/components/ticket-detail-dialog";
import { TicketFormDialog } from "@/features/corporate/tickets/components/ticket-form-dialog";
import { TicketStatusBadge } from "@/features/corporate/tickets/components/ticket-status-badge";
import { ticketPriorityLabels } from "@/features/corporate/tickets/schemas/ticket-schemas";

export function TicketsPanel({ clientId }: { clientId: string }) {
  const { data, isLoading } = useTicketsList({ client_id: clientId, limit: 50 });
  const [formOpen, setFormOpen] = useState(false);
  const [selected, setSelected] = useState<SupportTicketPublic | null>(null);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Tickets</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New ticket
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-32 w-full" />}
        {!isLoading && (data?.items.length ?? 0) === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">No tickets yet.</p>
        )}
        {!isLoading && (data?.items.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Number</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((ticket) => (
                <TableRow key={ticket.id} className="cursor-pointer" onClick={() => setSelected(ticket)}>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {ticket.ticket_number}
                  </TableCell>
                  <TableCell className="font-medium">{ticket.subject}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {ticketPriorityLabels[ticket.priority]}
                  </TableCell>
                  <TableCell>
                    <TicketStatusBadge status={ticket.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <TicketFormDialog open={formOpen} onOpenChange={setFormOpen} clientId={clientId} />
      <TicketDetailDialog
        open={!!selected}
        onOpenChange={(open) => !open && setSelected(null)}
        ticket={selected}
      />
    </Card>
  );
}
