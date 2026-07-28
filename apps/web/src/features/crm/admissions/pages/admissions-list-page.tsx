import { useNavigate } from "react-router-dom";

import { Badge, type BadgeProps } from "@/components/ui/badge";
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
import { useAdmissions } from "@/features/crm/admissions/api/admissions-hooks";
import {
  type AdmissionStatus,
  admissionStatusLabels,
} from "@/features/crm/admissions/schemas/admission-schemas";

const statusVariant: Record<AdmissionStatus, BadgeProps["variant"]> = {
  on_hold: "warning",
  confirmed: "success",
  cancelled: "destructive",
};

export function AdmissionsListPage() {
  const navigate = useNavigate();
  const { data: admissions, isLoading, isError } = useAdmissions();

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Admissions</h1>
        <p className="mt-1 text-muted-foreground">
          Every lead that has converted into a paid admission.
        </p>
      </div>

      <Card>
        <CardContent className="p-6">
          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load admissions. Please try again.
            </p>
          )}

          {!isLoading && !isError && (admissions?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No admissions recorded yet.
            </p>
          )}

          {!isLoading && !isError && (admissions?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Course</TableHead>
                  <TableHead>Batch</TableHead>
                  <TableHead>Fee</TableHead>
                  <TableHead>Admission date</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {admissions?.map((admission) => (
                  <TableRow
                    key={admission.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/crm/leads/${admission.lead_id}`)}
                  >
                    <TableCell className="font-medium">{admission.course_name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {admission.batch_name || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      ₹{admission.fee_amount - admission.discount_amount}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(admission.admission_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[admission.status]}>
                        {admissionStatusLabels[admission.status]}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
