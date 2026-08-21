import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { StudentPublic } from "@/features/students/api/students-api";
import { useCreateStudent, useUpdateStudent } from "@/features/students/api/students-hooks";
import {
  type StudentFormValues,
  genderLabels,
  genderValues,
  studentFormSchema,
} from "@/features/students/schemas/student-schemas";

interface StudentFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  student?: StudentPublic;
}

const emptyValues: StudentFormValues = {
  fullName: "",
  email: "",
  phone: "",
  gender: "",
  dateOfBirth: "",
  guardianName: "",
  guardianPhone: "",
  addressLine1: "",
  addressLine2: "",
  city: "",
  state: "",
  country: "",
  postalCode: "",
  courseName: "",
  batchName: "",
  enrollmentDate: "",
  notes: "",
};

export function StudentFormDialog({ open, onOpenChange, student }: StudentFormDialogProps) {
  const isEditing = !!student;
  const createStudent = useCreateStudent();
  const updateStudent = useUpdateStudent(student?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<StudentFormValues>({
    resolver: zodResolver(studentFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        student
          ? {
              fullName: student.full_name,
              email: student.email ?? "",
              phone: student.phone ?? "",
              gender: student.gender ?? "",
              dateOfBirth: student.date_of_birth ?? "",
              guardianName: student.guardian_name ?? "",
              guardianPhone: student.guardian_phone ?? "",
              addressLine1: student.address_line1 ?? "",
              addressLine2: student.address_line2 ?? "",
              city: student.city ?? "",
              state: student.state ?? "",
              country: student.country ?? "",
              postalCode: student.postal_code ?? "",
              courseName: student.course_name,
              batchName: student.batch_name ?? "",
              enrollmentDate: student.enrollment_date,
              notes: student.notes ?? "",
            }
          : emptyValues
      );
    }
  }, [open, student, reset]);

  const mutation = isEditing ? updateStudent : createStudent;

  const onSubmit = (values: StudentFormValues) => {
    const shared = {
      full_name: values.fullName,
      email: values.email || undefined,
      phone: values.phone || undefined,
      gender: values.gender || undefined,
      date_of_birth: values.dateOfBirth || undefined,
      guardian_name: values.guardianName || undefined,
      guardian_phone: values.guardianPhone || undefined,
      address_line1: values.addressLine1 || undefined,
      address_line2: values.addressLine2 || undefined,
      city: values.city || undefined,
      state: values.state || undefined,
      country: values.country || undefined,
      postal_code: values.postalCode || undefined,
      batch_name: values.batchName || undefined,
      notes: values.notes || undefined,
    };

    if (isEditing) {
      updateStudent.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createStudent.mutate(
        { ...shared, course_name: values.courseName, enrollment_date: values.enrollmentDate },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit student" : "New student"}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Personal details
            </p>
            <div className="space-y-2">
              <Label htmlFor="fullName" required>Full name</Label>
              <Input id="fullName" {...register("fullName")} />
              {errors.fullName && (
                <p className="text-sm text-destructive">{errors.fullName.message}</p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" {...register("email")} />
                {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Phone</Label>
                <Input id="phone" {...register("phone")} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="gender">Gender</Label>
                <Controller
                  control={control}
                  name="gender"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="gender">
                        <SelectValue placeholder="Select gender" />
                      </SelectTrigger>
                      <SelectContent>
                        {genderValues.map((g) => (
                          <SelectItem key={g} value={g}>
                            {genderLabels[g]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="dateOfBirth">Date of birth</Label>
                <Input id="dateOfBirth" type="date" {...register("dateOfBirth")} />
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Guardian
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="guardianName">Guardian name</Label>
                <Input id="guardianName" {...register("guardianName")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="guardianPhone">Guardian phone</Label>
                <Input id="guardianPhone" {...register("guardianPhone")} />
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Address
            </p>
            <div className="space-y-2">
              <Input placeholder="Address line 1" {...register("addressLine1")} />
              <Input placeholder="Address line 2" {...register("addressLine2")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input placeholder="City" {...register("city")} />
              <Input placeholder="State" {...register("state")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input placeholder="Country" {...register("country")} />
              <Input placeholder="Postal code" {...register("postalCode")} />
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Course
            </p>
            {isEditing ? (
              <p className="text-sm text-muted-foreground">
                {student.course_name}
                {student.batch_name ? ` · ${student.batch_name}` : ""} (enrolled{" "}
                {new Date(student.enrollment_date).toLocaleDateString()})
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="courseName" required>Course name</Label>
                  <Input id="courseName" {...register("courseName")} />
                  {errors.courseName && (
                    <p className="text-sm text-destructive">{errors.courseName.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="enrollmentDate" required>Enrollment date</Label>
                  <Input id="enrollmentDate" type="date" {...register("enrollmentDate")} />
                  {errors.enrollmentDate && (
                    <p className="text-sm text-destructive">{errors.enrollmentDate.message}</p>
                  )}
                </div>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="batchName">Batch name</Label>
              <Input id="batchName" {...register("batchName")} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={3} {...register("notes")} />
          </div>

          {mutation.isError && (
            <p className="text-sm text-destructive">
              {(mutation.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create student"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
