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
import { useLabs } from "@/features/pentrix/labs/api/labs-hooks";
import { LabFormDialog } from "@/features/pentrix/labs/pages/lab-form-dialog";
import { labDifficultyLabels } from "@/features/pentrix/labs/schemas/lab-schemas";

export function LabsListPage() {
  const navigate = useNavigate();
  const { data: labs, isLoading, isError } = useLabs();
  const [formOpen, setFormOpen] = useState(false);

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pentrix Labs</h1>
          <p className="mt-1 text-muted-foreground">
            Isolated hands-on environments students launch to practice offensive security.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Lab
        </Button>
      </div>

      <Card>
        <CardContent className="p-6">
          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load labs.</p>
          )}
          {!isLoading && !isError && (labs?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No labs yet. Create one to get started.
            </p>
          )}
          {!isLoading && !isError && (labs?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Difficulty</TableHead>
                  <TableHead>Points</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {labs?.map((lab) => (
                  <TableRow
                    key={lab.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/pentrix/labs/${lab.id}`)}
                  >
                    <TableCell className="font-medium">{lab.title}</TableCell>
                    <TableCell className="text-muted-foreground">{lab.category}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {labDifficultyLabels[lab.difficulty]}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{lab.points}</TableCell>
                    <TableCell>
                      <Badge variant={lab.is_active ? "success" : "secondary"}>
                        {lab.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <LabFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
