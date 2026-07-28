import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useVAPTEngagementsByProject } from "@/features/corporate/vapt/api/vapt-hooks";
import { VAPTEngagementStatusBadge } from "@/features/corporate/vapt/components/vapt-badges";
import { VAPTEngagementFormDialog } from "@/features/corporate/vapt/components/vapt-engagement-form-dialog";
import { VAPTFindingsDialog } from "@/features/corporate/vapt/components/vapt-findings-dialog";
import { vaptEngagementTypeLabels } from "@/features/corporate/vapt/schemas/vapt-schemas";

export function VAPTPanel({ projectId }: { projectId: string }) {
  const { data: engagements, isLoading } = useVAPTEngagementsByProject(projectId);
  const [formOpen, setFormOpen] = useState(false);
  const [findingsTarget, setFindingsTarget] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">VAPT engagements</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New engagement
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-32 w-full" />}
        {!isLoading && (engagements?.length ?? 0) === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">No VAPT engagements yet.</p>
        )}
        {!isLoading && (engagements?.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Start date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {engagements?.map((engagement) => (
                <TableRow key={engagement.id}>
                  <TableCell className="font-medium">
                    {vaptEngagementTypeLabels[engagement.engagement_type]}
                  </TableCell>
                  <TableCell className="max-w-[200px] truncate text-muted-foreground">
                    {engagement.scope_description}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(engagement.start_date).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <VAPTEngagementStatusBadge status={engagement.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" onClick={() => setFindingsTarget(engagement.id)}>
                      Findings
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <VAPTEngagementFormDialog open={formOpen} onOpenChange={setFormOpen} projectId={projectId} />
      <VAPTFindingsDialog
        open={!!findingsTarget}
        onOpenChange={(open) => !open && setFindingsTarget(null)}
        engagementId={findingsTarget}
      />
    </Card>
  );
}
