import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TableCell, TableRow } from "@/components/ui/table";
import type { ApplicationPublic } from "@/features/placements/api/placements-api";
import { useChangeApplicationStatus } from "@/features/placements/api/placements-hooks";
import {
  type ApplicationStatus,
  applicationStatusLabels,
  applicationStatusValues,
} from "@/features/placements/schemas/posting-schemas";

interface ApplicationRowProps {
  postingId: string;
  application: ApplicationPublic;
}

export function ApplicationRow({ postingId, application }: ApplicationRowProps) {
  const changeStatus = useChangeApplicationStatus(postingId);

  return (
    <TableRow>
      <TableCell className="font-mono text-xs text-muted-foreground">
        {application.student_id}
      </TableCell>
      <TableCell className="text-muted-foreground">
        {new Date(application.applied_at).toLocaleDateString()}
      </TableCell>
      <TableCell className="max-w-xs truncate text-sm">{application.cover_letter || "—"}</TableCell>
      <TableCell>
        <Select
          value={application.status}
          onValueChange={(value) =>
            changeStatus.mutate({ applicationId: application.id, status: value as ApplicationStatus })
          }
        >
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {applicationStatusValues.map((s) => (
              <SelectItem key={s} value={s}>
                {applicationStatusLabels[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
    </TableRow>
  );
}
