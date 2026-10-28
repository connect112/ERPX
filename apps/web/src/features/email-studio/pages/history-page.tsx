import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { studioApi, studioKeys } from "@/features/email-studio/api/studio-api";
import { SEND_STATUS, SOURCE_LABEL } from "@/features/email-studio/lib/studio";
import { selectClass } from "@/features/our-internships/components/letter-fields";

/** What was sent and what failed. A mail server accepting a message is not proof it reached an inbox, so "Sent" is not shown as "Delivered". */
export function HistoryPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const params = { q: q.trim() || undefined, status: status || undefined };
  const history = useQuery({ queryKey: studioKeys.history(JSON.stringify(params)), queryFn: () => studioApi.history(params), refetchInterval: 15_000 });

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-muted-foreground">
        Every email ERPX sends is listed with the template and version that made it. Message text and links (such as password-reset links) are never kept here.
        &quot;Sent&quot; means the mail server accepted the message; delivery to the inbox is only shown when the mail provider reports it.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="h-q">Recipient or subject</Label>
          <Input id="h-q" className="w-64" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="h-status">Status</Label>
          <select id="h-status" className={`${selectClass} w-40`} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any</option>
            {Object.entries(SEND_STATUS).map(([value, s]) => (
              <option key={value} value={value}>{s.label}</option>
            ))}
          </select>
        </div>
      </div>
      {history.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : history.data && history.data.length > 0 ? (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Recipient</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>Email type</TableHead>
                <TableHead>Template</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {history.data.map((h) => {
                const s = SEND_STATUS[h.status];
                return (
                  <TableRow key={h.id}>
                    <TableCell className="whitespace-nowrap text-xs">{new Date(h.created_at).toLocaleString()}</TableCell>
                    <TableCell>{h.recipient}</TableCell>
                    <TableCell className="max-w-xs truncate">{h.subject}</TableCell>
                    <TableCell className="text-xs">
                      {h.key ?? "-"}
                      {h.module && <div className="text-muted-foreground">{h.module}</div>}
                    </TableCell>
                    <TableCell className="text-xs">
                      {h.template_name ? `${h.template_name} v${h.version_number ?? "?"}` : SOURCE_LABEL[h.source ?? ""] ?? "-"}
                      {h.attachments > 0 && <div className="text-muted-foreground">{h.attachments} attachment{h.attachments === 1 ? "" : "s"}</div>}
                    </TableCell>
                    <TableCell>
                      <Badge variant={s.variant}>{s.label}</Badge>
                      {h.is_test && <Badge variant="outline" className="ml-1">Test</Badge>}
                      {h.error && <p className="mt-1 max-w-xs text-xs text-destructive">{h.error}</p>}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      ) : (
        <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">No emails recorded yet. Emails sent from now on will appear here.</p>
      )}
    </div>
  );
}
