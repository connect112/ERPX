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
import { AuditActionBadge } from "@/features/audit/components/audit-action-badge";
import { AuditChangesDialog } from "@/features/audit/components/audit-changes-dialog";
import { useAuditEntityTypes, useAuditLogsList } from "@/features/audit/api/audit-hooks";
import type { AuditAction, AuditLogPublic } from "@/features/audit/api/audit-api";

const PAGE_SIZE = 25;

export function AuditLogListPage() {
  const [entityType, setEntityType] = useState<string | "all">("all");
  const [action, setAction] = useState<AuditAction | "all">("all");
  const [skip, setSkip] = useState(0);
  const [selectedLog, setSelectedLog] = useState<AuditLogPublic | null>(null);

  const { data: entityTypes } = useAuditEntityTypes();
  const { data, isLoading, isError } = useAuditLogsList({
    entity_type: entityType === "all" ? undefined : entityType,
    action: action === "all" ? undefined : action,
    skip,
    limit: PAGE_SIZE,
  });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Audit Logs</h1>
        <p className="mt-1 text-muted-foreground">
          A record of every create, update, and delete across the organization — who did it, when,
          and exactly what changed.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Select
              value={entityType}
              onValueChange={(value) => {
                setEntityType(value);
                setSkip(0);
              }}
            >
              <SelectTrigger className="sm:w-56">
                <SelectValue placeholder="All entity types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All entity types</SelectItem>
                {entityTypes?.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={action}
              onValueChange={(value) => {
                setAction(value as AuditAction | "all");
                setSkip(0);
              }}
            >
              <SelectTrigger className="sm:w-48">
                <SelectValue placeholder="All actions" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All actions</SelectItem>
                <SelectItem value="create">Created</SelectItem>
                <SelectItem value="update">Updated</SelectItem>
                <SelectItem value="delete">Deleted</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load audit logs. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No audit activity found for these filters.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>IP Address</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((log) => (
                  <TableRow key={log.id} className="cursor-pointer" onClick={() => setSelectedLog(log)}>
                    <TableCell className="text-muted-foreground">
                      {new Date(log.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="font-medium">
                      {log.user_full_name ?? log.user_email ?? "System"}
                    </TableCell>
                    <TableCell>
                      <AuditActionBadge action={log.action} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {log.entity_type}
                      {log.entity_id ? ` #${log.entity_id.slice(0, 8)}` : ""}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{log.ip_address ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm">
                        View
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} entries)
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

      <AuditChangesDialog log={selectedLog} onOpenChange={(open) => !open && setSelectedLog(null)} />
    </div>
  );
}
