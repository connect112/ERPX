import { zodResolver } from "@hookform/resolvers/zod";
import type { AxiosError } from "axios";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAdmissionForLead,
  useCancelAdmission,
  useCreateAdmission,
} from "@/features/crm/admissions/api/admissions-hooks";
import {
  type AdmissionFormValues,
  type AdmissionStatus,
  admissionFormSchema,
  admissionStatusLabels,
} from "@/features/crm/admissions/schemas/admission-schemas";
import { useCreateStudentFromAdmission } from "@/features/students/api/students-hooks";

const statusVariant: Record<AdmissionStatus, BadgeProps["variant"]> = {
  on_hold: "warning",
  confirmed: "success",
  cancelled: "destructive",
};

export function AdmissionTab({ leadId }: { leadId: string }) {
  const navigate = useNavigate();
  const { data: admission, isLoading, isError, error } = useAdmissionForLead(leadId);
  const createAdmission = useCreateAdmission(leadId);
  const cancelAdmission = useCancelAdmission(leadId);
  const createStudent = useCreateStudentFromAdmission();

  const notFound = isError && (error as AxiosError)?.response?.status === 404;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AdmissionFormValues>({ resolver: zodResolver(admissionFormSchema) });

  const onSubmit = (values: AdmissionFormValues) => {
    createAdmission.mutate({
      course_name: values.courseName,
      batch_name: values.batchName || undefined,
      fee_amount: Number(values.feeAmount),
      discount_amount: values.discountAmount ? Number(values.discountAmount) : undefined,
      admission_date: values.admissionDate,
    });
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6">
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (admission) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Admission</CardTitle>
          <Badge variant={statusVariant[admission.status]}>
            {admissionStatusLabels[admission.status]}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Course</p>
              <p className="font-medium">{admission.course_name}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Batch</p>
              <p className="font-medium">{admission.batch_name || "—"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Fee amount</p>
              <p className="font-medium">₹{admission.fee_amount}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Discount</p>
              <p className="font-medium">₹{admission.discount_amount}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Admission date</p>
              <p className="font-medium">
                {new Date(admission.admission_date).toLocaleDateString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {admission.status === "confirmed" && (
              <Button
                size="sm"
                onClick={() =>
                  createStudent.mutate(
                    { admissionId: admission.id, payload: {} },
                    { onSuccess: (student) => navigate(`/students/${student.id}`) }
                  )
                }
                disabled={createStudent.isPending}
              >
                {createStudent.isPending ? "Creating..." : "Create student"}
              </Button>
            )}
            {admission.status !== "cancelled" && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => cancelAdmission.mutate(admission.id)}
                disabled={cancelAdmission.isPending}
              >
                {cancelAdmission.isPending ? "Cancelling..." : "Cancel admission"}
              </Button>
            )}
          </div>
          {createStudent.isError && (
            <p className="text-sm text-destructive">
              {(createStudent.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Failed to create student record."}
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  if (!notFound && isError) {
    return (
      <Card>
        <CardContent className="p-6">
          <p className="text-sm text-destructive">Failed to load admission details.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Convert to admission</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="courseName">Course name</Label>
            <Input id="courseName" {...register("courseName")} />
            {errors.courseName && (
              <p className="text-sm text-destructive">{errors.courseName.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="batchName">Batch name</Label>
              <Input id="batchName" {...register("batchName")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admissionDate">Admission date</Label>
              <Input id="admissionDate" type="date" {...register("admissionDate")} />
              {errors.admissionDate && (
                <p className="text-sm text-destructive">{errors.admissionDate.message}</p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="feeAmount">Fee amount</Label>
              <Input id="feeAmount" type="number" step="0.01" {...register("feeAmount")} />
              {errors.feeAmount && (
                <p className="text-sm text-destructive">{errors.feeAmount.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="discountAmount">Discount amount</Label>
              <Input id="discountAmount" type="number" step="0.01" {...register("discountAmount")} />
            </div>
          </div>
          {createAdmission.isError && (
            <p className="text-sm text-destructive">
              {(createAdmission.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}
          <Button type="submit" disabled={createAdmission.isPending}>
            {createAdmission.isPending ? "Saving..." : "Create admission"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
