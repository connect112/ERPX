import { Plus } from "lucide-react";
import { useState } from "react";

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
import { TrainerFormDialog } from "@/features/trainers/components/trainer-form-dialog";
import { useTrainersList } from "@/features/trainers/api/trainers-hooks";

export function TrainersListPage() {
  const [formOpen, setFormOpen] = useState(false);
  const { data, isLoading } = useTrainersList({ limit: 100 });

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Trainers</h1>
          <p className="mt-1 text-muted-foreground">
            Teaching-specific profiles for staff who deliver courses and live sessions.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New trainer
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
              No trainer profiles yet. Create one from an existing employee.
            </p>
          )}

          {!isLoading && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Specializations</TableHead>
                  <TableHead>Max weekly hours</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((trainer) => (
                  <TableRow key={trainer.id}>
                    <TableCell className="font-medium">{trainer.employee_name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {trainer.employee_email ?? "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {trainer.specializations ?? "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {trainer.max_weekly_hours ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={trainer.is_active ? "success" : "secondary"}>
                        {trainer.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <TrainerFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
