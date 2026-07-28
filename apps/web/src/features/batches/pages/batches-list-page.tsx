import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useBatchesList } from "@/features/batches/api/batches-hooks";
import { BatchFormDialog } from "@/features/batches/components/batch-form-dialog";
import { BatchStatusBadge } from "@/features/batches/components/batch-status-badge";

export function BatchesListPage() {
  const navigate = useNavigate();
  const [formOpen, setFormOpen] = useState(false);
  const { data, isLoading } = useBatchesList({ limit: 100 });

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Batches</h1>
          <p className="mt-1 text-muted-foreground">
            Cohorts of students taking a course together on a shared schedule.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New batch
        </Button>
      </div>

      <Card>
        <CardContent className="p-6">
          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {!isLoading && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No batches yet. Create one to start scheduling classes.
            </p>
          )}

          {!isLoading && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Start date</TableHead>
                  <TableHead>End date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((batch) => (
                  <TableRow
                    key={batch.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/batches/${batch.id}`)}
                  >
                    <TableCell className="font-medium">{batch.name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {batch.code}
                    </TableCell>
                    <TableCell>
                      <BatchStatusBadge status={batch.status} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(batch.start_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {batch.end_date ? new Date(batch.end_date).toLocaleDateString() : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <BatchFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
