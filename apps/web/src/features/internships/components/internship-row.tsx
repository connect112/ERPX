import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TableCell, TableRow } from "@/components/ui/table";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import type { InternshipPublic } from "@/features/internships/api/internships-api";
import {
  useChangeInternshipStatus,
  useUpdateInternship,
} from "@/features/internships/api/internships-hooks";
import { InternshipStatusBadge } from "@/features/internships/components/internship-status-badge";
import {
  type InternshipStatus,
  internshipStatusLabels,
  internshipStatusValues,
} from "@/features/internships/schemas/posting-schemas";

const NO_MENTOR = "__none__";

interface InternshipRowProps {
  internship: InternshipPublic;
}

export function InternshipRow({ internship }: InternshipRowProps) {
  const { data: employees } = useEmployeesList({ limit: 200 });
  const updateInternship = useUpdateInternship();
  const changeStatus = useChangeInternshipStatus();

  return (
    <TableRow>
      <TableCell className="font-mono text-xs text-muted-foreground">{internship.student_id}</TableCell>
      <TableCell className="text-muted-foreground">
        {new Date(internship.start_date).toLocaleDateString()}
      </TableCell>
      <TableCell className="text-muted-foreground">
        {internship.stipend != null ? internship.stipend.toLocaleString() : "—"}
      </TableCell>
      <TableCell>
        <Select
          value={internship.mentor_employee_id ?? NO_MENTOR}
          onValueChange={(value) =>
            updateInternship.mutate({
              id: internship.id,
              payload: { mentor_employee_id: value === NO_MENTOR ? undefined : value },
            })
          }
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Assign mentor" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NO_MENTOR}>No mentor assigned</SelectItem>
            {employees?.items.map((e) => (
              <SelectItem key={e.id} value={e.id}>
                {e.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell>
        <Select
          value={internship.status}
          onValueChange={(value) =>
            changeStatus.mutate({ id: internship.id, status: value as InternshipStatus })
          }
        >
          <SelectTrigger className="w-40">
            <SelectValue>
              <InternshipStatusBadge status={internship.status} />
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {internshipStatusValues.map((s) => (
              <SelectItem key={s} value={s}>
                {internshipStatusLabels[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
    </TableRow>
  );
}
