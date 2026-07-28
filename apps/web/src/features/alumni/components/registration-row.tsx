import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TableCell, TableRow } from "@/components/ui/table";
import type { EventRegistrationPublic } from "@/features/alumni/api/alumni-api";
import { useMarkAttendance } from "@/features/alumni/api/alumni-hooks";
import {
  type RegistrationStatus,
  registrationStatusLabels,
  registrationStatusValues,
} from "@/features/alumni/schemas/event-schemas";

interface RegistrationRowProps {
  eventId: string;
  registration: EventRegistrationPublic;
}

export function RegistrationRow({ eventId, registration }: RegistrationRowProps) {
  const markAttendance = useMarkAttendance(eventId);

  return (
    <TableRow>
      <TableCell className="font-mono text-xs text-muted-foreground">{registration.alumni_id}</TableCell>
      <TableCell className="text-muted-foreground">
        {new Date(registration.registered_at).toLocaleDateString()}
      </TableCell>
      <TableCell>
        <Select
          value={registration.status}
          onValueChange={(value) =>
            markAttendance.mutate({
              registrationId: registration.id,
              status: value as RegistrationStatus,
            })
          }
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {registrationStatusValues.map((s) => (
              <SelectItem key={s} value={s}>
                {registrationStatusLabels[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
    </TableRow>
  );
}
