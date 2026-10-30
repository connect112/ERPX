import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDeletionLog } from "@/features/storage-manager/api/storage-hooks";
import { formatBytes, formatDate } from "@/features/storage-manager/lib/format";

const PAGE = 25;
const ACTION_LABEL = { trash: "Moved to Trash", restore: "Restored", purge: "Permanently deleted" } as const;
const ACTION_VARIANT = { trash: "warning", restore: "success", purge: "destructive" } as const;

/** The append-only history of everything done to a stored file: who, when, why, and the evidence at the time. */
export function LogPanel() {
  const [skip, setSkip] = useState(0);
  const { data, isLoading, isError } = useDeletionLog(skip, PAGE);

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">Every move to Trash, restore and permanent deletion. Entries cannot be edited or removed.</p>
      <Card>
        <CardContent className="p-0">
          {isLoading && <Skeleton className="m-6 h-24" />}
          {isError && <p className="p-8 text-center text-sm text-destructive">The log could not be loaded.</p>}
          {data && data.items.length === 0 && <p className="py-10 text-center text-sm text-muted-foreground">Nothing has been deleted yet.</p>}
          {data && data.items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>File</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>By</TableHead>
                  <TableHead>Reason and evidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{formatDate(row.created_at)}</TableCell>
                    <TableCell>
                      <Badge variant={ACTION_VARIANT[row.action]}>{ACTION_LABEL[row.action]}</Badge>
                    </TableCell>
                    <TableCell className="max-w-xs break-all">
                      {row.filename ?? row.object_key}
                      <div className="text-xs text-muted-foreground">{row.object_key}</div>
                    </TableCell>
                    <TableCell>{formatBytes(row.size_bytes)}</TableCell>
                    <TableCell>
                      {row.user_email ?? "—"}
                      {row.ip_address && <div className="text-xs text-muted-foreground">{row.ip_address}</div>}
                    </TableCell>
                    <TableCell className="max-w-sm text-sm">
                      {row.reason}
                      {row.evidence.map((evidence, index) => (
                        <div key={index} className="text-xs text-muted-foreground">
                          {evidence.text}
                        </div>
                      ))}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      {data && data.total > PAGE && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {skip + 1}–{Math.min(skip + PAGE, data.total)} of {data.total}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE))}>
              Newer
            </Button>
            <Button variant="outline" size="sm" disabled={skip + PAGE >= data.total} onClick={() => setSkip(skip + PAGE)}>
              Older
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
