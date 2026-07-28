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
import { ClassroomFormDialog } from "@/features/classrooms/components/classroom-form-dialog";
import { useClassroomsList } from "@/features/classrooms/api/classrooms-hooks";

export function ClassroomsListPage() {
  const [formOpen, setFormOpen] = useState(false);
  const { data, isLoading } = useClassroomsList({ limit: 100 });

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Classrooms</h1>
          <p className="mt-1 text-muted-foreground">
            Physical rooms and virtual meeting spaces bookable for batches and live classes.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New classroom
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
              No classrooms yet. Create one to start scheduling sessions.
            </p>
          )}

          {!isLoading && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Capacity</TableHead>
                  <TableHead>Location / Link</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((room) => (
                  <TableRow key={room.id}>
                    <TableCell className="font-medium">{room.name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{room.code}</TableCell>
                    <TableCell className="text-muted-foreground capitalize">
                      {room.classroom_type}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{room.capacity ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {room.location ?? room.meeting_link ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={room.is_active ? "success" : "secondary"}>
                        {room.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ClassroomFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
