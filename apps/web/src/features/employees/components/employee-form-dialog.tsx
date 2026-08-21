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
import type { EmployeePublic } from "@/features/employees/api/employees-api";
import { useCreateEmployee, useEmployeesList, useUpdateEmployee } from "@/features/employees/api/employees-hooks";
import {
  type EmployeeFormValues,
  employeeFormSchema,
  employmentTypeLabels,
  employmentTypeValues,
  genderLabels,
  genderValues,
} from "@/features/employees/schemas/employee-schemas";
import { useDepartments, useDesignations } from "@/features/hr/api/hr-hooks";

interface EmployeeFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employee?: EmployeePublic;
}

const emptyValues: EmployeeFormValues = {
  employeeCode: "",
  fullName: "",
  departmentId: "",
  designationId: "",
  reportingManagerId: "",
  email: "",
  phone: "",
  gender: "",
  dateOfBirth: "",
  addressLine1: "",
  city: "",
  state: "",
  country: "",
  postalCode: "",
  emergencyContactName: "",
  emergencyContactPhone: "",
  employmentType: "full_time",
  dateOfJoining: "",
  notes: "",
};

export function EmployeeFormDialog({ open, onOpenChange, employee }: EmployeeFormDialogProps) {
  const isEditing = !!employee;
  const createEmployee = useCreateEmployee();
  const updateEmployee = useUpdateEmployee(employee?.id ?? "");
  const { data: departments } = useDepartments(true);
  const { data: designations } = useDesignations(true);
  const { data: managers } = useEmployeesList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EmployeeFormValues>({
    resolver: zodResolver(employeeFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        employee
          ? {
              employeeCode: employee.employee_code,
              fullName: employee.full_name,
              departmentId: employee.department_id ?? "",
              designationId: employee.designation_id ?? "",
              reportingManagerId: employee.reporting_manager_id ?? "",
              email: employee.email ?? "",
              phone: employee.phone ?? "",
              gender: employee.gender ?? "",
              dateOfBirth: employee.date_of_birth ?? "",
              addressLine1: employee.address_line1 ?? "",
              city: employee.city ?? "",
              state: employee.state ?? "",
              country: employee.country ?? "",
              postalCode: employee.postal_code ?? "",
              emergencyContactName: employee.emergency_contact_name ?? "",
              emergencyContactPhone: employee.emergency_contact_phone ?? "",
              employmentType: employee.employment_type,
              dateOfJoining: employee.date_of_joining,
              notes: employee.notes ?? "",
            }
          : emptyValues
      );
    }
  }, [open, employee, reset]);

  const mutation = isEditing ? updateEmployee : createEmployee;
  const managerOptions = (managers?.items ?? []).filter((m) => m.id !== employee?.id);

  const onSubmit = (values: EmployeeFormValues) => {
    const shared = {
      full_name: values.fullName,
      department_id: values.departmentId || undefined,
      designation_id: values.designationId || undefined,
      reporting_manager_id: values.reportingManagerId || undefined,
      email: values.email || undefined,
      phone: values.phone || undefined,
      gender: values.gender || undefined,
      date_of_birth: values.dateOfBirth || undefined,
      address_line1: values.addressLine1 || undefined,
      city: values.city || undefined,
      state: values.state || undefined,
      country: values.country || undefined,
      postal_code: values.postalCode || undefined,
      emergency_contact_name: values.emergencyContactName || undefined,
      emergency_contact_phone: values.emergencyContactPhone || undefined,
      employment_type: values.employmentType,
      notes: values.notes || undefined,
    };

    if (isEditing) {
      updateEmployee.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createEmployee.mutate(
        { ...shared, employee_code: values.employeeCode, date_of_joining: values.dateOfJoining },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit employee" : "New employee"}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Personal details
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="employeeCode" required>Employee code</Label>
                <Input id="employeeCode" disabled={isEditing} {...register("employeeCode")} />
                {errors.employeeCode && (
                  <p className="text-sm text-destructive">{errors.employeeCode.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="fullName" required>Full name</Label>
                <Input id="fullName" {...register("fullName")} />
                {errors.fullName && (
                  <p className="text-sm text-destructive">{errors.fullName.message}</p>
                )}
              </div>
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
              Employment
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="departmentId">Department</Label>
                <Controller
                  control={control}
                  name="departmentId"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="departmentId">
                        <SelectValue placeholder="Select department" />
                      </SelectTrigger>
                      <SelectContent>
                        {departments?.map((d) => (
                          <SelectItem key={d.id} value={d.id}>
                            {d.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="designationId">Designation</Label>
                <Controller
                  control={control}
                  name="designationId"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="designationId">
                        <SelectValue placeholder="Select designation" />
                      </SelectTrigger>
                      <SelectContent>
                        {designations?.map((d) => (
                          <SelectItem key={d.id} value={d.id}>
                            {d.title}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="reportingManagerId">Reporting manager</Label>
                <Controller
                  control={control}
                  name="reportingManagerId"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="reportingManagerId">
                        <SelectValue placeholder="Select manager" />
                      </SelectTrigger>
                      <SelectContent>
                        {managerOptions.map((m) => (
                          <SelectItem key={m.id} value={m.id}>
                            {m.full_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="employmentType" required>Employment type</Label>
                <Controller
                  control={control}
                  name="employmentType"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="employmentType">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {employmentTypeValues.map((t) => (
                          <SelectItem key={t} value={t}>
                            {employmentTypeLabels[t]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            </div>
            {!isEditing && (
              <div className="space-y-2">
                <Label htmlFor="dateOfJoining" required>Date of joining</Label>
                <Input id="dateOfJoining" type="date" {...register("dateOfJoining")} />
                {errors.dateOfJoining && (
                  <p className="text-sm text-destructive">{errors.dateOfJoining.message}</p>
                )}
              </div>
            )}
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Address
            </p>
            <div className="space-y-2">
              <Input placeholder="Address line 1" {...register("addressLine1")} />
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
              Emergency contact
            </p>
            <div className="grid grid-cols-2 gap-4">
              <Input placeholder="Contact name" {...register("emergencyContactName")} />
              <Input placeholder="Contact phone" {...register("emergencyContactPhone")} />
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create employee"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
