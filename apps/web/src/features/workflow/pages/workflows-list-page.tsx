import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
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
import { useWorkflowsList } from "@/features/workflow/api/workflow-hooks";
import { WorkflowFormDialog } from "@/features/workflow/components/workflow-form-dialog";

const PAGE_SIZE = 20;

export function WorkflowsListPage() {
  const navigate = useNavigate();
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useWorkflowsList({ skip, limit: PAGE_SIZE });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Approval Workflows</h1>
          <p className="mt-1 text-muted-foreground">
            Configurable multi-step approval chains other modules (leave, expenses, purchase
            orders, ...) can plug into by entity type.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Workflow
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load workflows. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No approval workflows configured yet. Create one to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Entity type</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((workflow) => (
                  <TableRow
                    key={workflow.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/workflow/workflows/${workflow.id}`)}
                  >
                    <TableCell className="font-medium">{workflow.name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {workflow.entity_type}
                    </TableCell>
                    <TableCell>
                      <Badge variant={workflow.is_active ? "success" : "secondary"}>
                        {workflow.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} workflows)
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

      <WorkflowFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
