import { Send } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCommunicationLogs } from "@/features/communication/api/communication-hooks";
import { CommunicationStatusBadge } from "@/features/communication/components/status-badge";
import { SendFormDialog } from "@/features/communication/components/send-form-dialog";
import {
  type Channel,
  type CommunicationStatus,
  channelLabels,
  channelValues,
  statusLabels,
  statusValues,
} from "@/features/communication/schemas/communication-schemas";

const PAGE_SIZE = 20;

export function CommunicationLogPage() {
  const [channel, setChannel] = useState<Channel | "all">("all");
  const [status, setStatus] = useState<CommunicationStatus | "all">("all");
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useCommunicationLogs({
    channel: channel === "all" ? undefined : channel,
    status: status === "all" ? undefined : status,
    skip,
    limit: PAGE_SIZE,
  });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Communication Log</h1>
          <p className="mt-1 text-muted-foreground">
            Every email, SMS, and WhatsApp message the platform has sent, in one place.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Send className="h-4 w-4" />
          Send Communication
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <div className="flex flex-wrap gap-3">
            <Select
              value={channel}
              onValueChange={(value) => {
                setChannel(value as Channel | "all");
                setSkip(0);
              }}
            >
              <SelectTrigger className="sm:w-48">
                <SelectValue placeholder="All channels" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All channels</SelectItem>
                {channelValues.map((c) => (
                  <SelectItem key={c} value={c}>
                    {channelLabels[c]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={status}
              onValueChange={(value) => {
                setStatus(value as CommunicationStatus | "all");
                setSkip(0);
              }}
            >
              <SelectTrigger className="sm:w-48">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {statusValues.map((s) => (
                  <SelectItem key={s} value={s}>
                    {statusLabels[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load the communication log. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No communications sent yet.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Channel</TableHead>
                  <TableHead>Recipient</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Sent</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="capitalize">{channelLabels[log.channel]}</TableCell>
                    <TableCell className="font-medium">{log.recipient}</TableCell>
                    <TableCell className="max-w-xs truncate text-muted-foreground">
                      {log.subject || log.body}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(log.sent_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <CommunicationStatusBadge status={log.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} communications)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip + PAGE_SIZE >= total}
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <SendFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
