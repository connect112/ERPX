import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

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
import { useWorkshopsList } from "@/features/workshops/api/workshops-hooks";
import { WorkshopFormDialog } from "@/features/workshops/components/workshop-form-dialog";
import { WorkshopStatusBadge } from "@/features/workshops/components/workshop-status-badge";
import {
  type WorkshopStatus,
  workshopStatusLabels,
  workshopStatusValues,
} from "@/features/workshops/schemas/workshop-schemas";

const PAGE_SIZE = 20;

export function WorkshopsListPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<WorkshopStatus | "all">("all");
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useWorkshopsList({
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
          <h1 className="text-2xl font-semibold tracking-tight">Workshops</h1>
          <p className="mt-1 text-muted-foreground">
            Short training events open to students and the public.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Workshop
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value as WorkshopStatus | "all");
              setSkip(0);
            }}
          >
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {workshopStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {workshopStatusLabels[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load workshops. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No workshops found. Create your first workshop to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((workshop) => (
                  <TableRow
                    key={workshop.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/workshops/${workshop.id}`)}
                  >
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {workshop.code}
                    </TableCell>
                    <TableCell className="font-medium">{workshop.title}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(workshop.workshop_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground capitalize">{workshop.mode}</TableCell>
                    <TableCell>
                      <WorkshopStatusBadge status={workshop.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} workshops)
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

      <WorkshopFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
