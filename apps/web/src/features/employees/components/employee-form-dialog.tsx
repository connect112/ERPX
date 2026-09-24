import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, type ReactNode } from "react";
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
  type Gender,
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

// Marks a field as required inline on its own Label, rather than a
// separate legend — every field below is mandatory except
// reportingManagerId and notes (see employeeFormSchema's own docstring
// for why), so the asterisk only needs to appear on the fields that can
// actually reject an empty submission. Employment type is exempted too:
// its Select always carries a real value (defaulted, no blank/placeholder
// state), so it can never surface as empty in the first place.
function RequiredLabel({ htmlFor, children }: { htmlFor?: string; children: ReactNode }) {
  return (
    <Label htmlFor={htmlFor}>
      {children} <span className="text-destructive">*</span>
    </Label>
  );
}

const emptyValues: EmployeeFormValues = {
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
      // Cast, not a validation bypass: employeeFormSchema's own .refine
      // already limits this to a genderValues member before onSubmit can
      // ever run — see that schema for why gender is typed as a plain
      // string in the form (matching departmentId/designationId's
      // "starts blank" Select pattern) rather than z.enum(genderValues).
      gender: (values.gender || undefined) as Gender | undefined,
      date_of_birth: values.dateOfBirth || undefined,
      address_line1: values.addressLine1 || undefined,
      city: values.city || undefined,
      state: values.state || undefined,
      country: values.country || undefined,
      postal_code: values.postalCode || undefined,
      emergency_contact_name: values.emergencyContactName || undefined,
      emergency_contact_phone: values.emergencyContactPhone || undefined,
      employment_type: values.employmentType,
      date_of_joining: values.dateOfJoining || undefined,
      notes: values.notes || undefined,
    };

    if (isEditing) {
      updateEmployee.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createEmployee.mutate({ ...shared, date_of_joining: values.dateOfJoining }, {
        onSuccess: () => onOpenChange(false),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit employee" : "New employee"}</DialogTitle>
        </DialogHeader>
        <p className="text-xs text-muted-foreground">
          <span className="text-destructive">*</span> Required
          {!isEditing &&
            " — that's it. Phone, address, and the rest of their profile get filled in by the employee themselves when they accept the invite."}
        </p>

        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Personal details
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <RequiredLabel htmlFor="fullName">Full name</RequiredLabel>
                <Input id="fullName" {...register("fullName")} />
                {errors.fullName && (
                  <p className="text-sm text-destructive">{errors.fullName.message}</p>
                )}
              </div>
              <div className="space-y-2">
                {/* Not a form field — EmployeeRepository.create assigns the
                    next sequential code (EMP-00001, EMP-00002, ...) itself;
                    there's nothing here for an admin to type or edit, so
                    this is plain text rather than a Label (nothing to
                    associate it with). */}
                <p className="text-sm font-medium leading-none">Employee code</p>
                <p className="flex h-10 items-center text-sm text-muted-foreground">
                  {isEditing ? employee.employee_code : "Assigned automatically on save"}
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <RequiredLabel htmlFor="email">Email</RequiredLabel>
              <Input id="email" type="email" {...register("email")} />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>

            {/* Phone/gender/DOB are the employee's own to fill in via the
                complete-registration page they land on from their invite
                email (see employeeFormSchema's docstring) — shown here
                only once that's happened, so an admin can view or correct
                them, never as something to fill in at creation. */}
            {isEditing && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="phone">Phone</Label>
                  <Input id="phone" {...register("phone")} />
                  {errors.phone && <p className="text-sm text-destructive">{errors.phone.message}</p>}
                </div>
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
                  {errors.gender && <p className="text-sm text-destructive">{errors.gender.message}</p>}
                </div>
              </div>
            )}
            {isEditing && (
              <div className="space-y-2">
                <Label htmlFor="dateOfBirth">Date of birth</Label>
                <Input id="dateOfBirth" type="date" {...register("dateOfBirth")} />
                {errors.dateOfBirth && (
                  <p className="text-sm text-destructive">{errors.dateOfBirth.message}</p>
                )}
              </div>
            )}
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Employment
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <RequiredLabel htmlFor="departmentId">Department</RequiredLabel>
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
                {errors.departmentId && (
                  <p className="text-sm text-destructive">{errors.departmentId.message}</p>
                )}
                {departments?.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    No departments yet — create one under HR settings first.
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <RequiredLabel htmlFor="designationId">Designation</RequiredLabel>
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
                {errors.designationId && (
                  <p className="text-sm text-destructive">{errors.designationId.message}</p>
                )}
                {designations?.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    No designations yet — create one under HR settings first.
                  </p>
                )}
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
                <Label htmlFor="employmentType">Employment type</Label>
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
                <RequiredLabel htmlFor="dateOfJoining">Date of joining</RequiredLabel>
                <Input id="dateOfJoining" type="date" {...register("dateOfJoining")} />
                {errors.dateOfJoining && (
                  <p className="text-sm text-destructive">{errors.dateOfJoining.message}</p>
                )}
              </div>
            )}
          </div>

          {/* Address and emergency contact, like phone/gender/DOB above,
              are the employee's own to fill in via complete-registration
              — only shown here once there's something to show or correct. */}
          {isEditing && (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Address
              </p>
              <div className="space-y-2">
                <Label htmlFor="addressLine1">Address line 1</Label>
                <Input id="addressLine1" {...register("addressLine1")} />
                {errors.addressLine1 && (
                  <p className="text-sm text-destructive">{errors.addressLine1.message}</p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="city">City</Label>
                  <Input id="city" {...register("city")} />
                  {errors.city && <p className="text-sm text-destructive">{errors.city.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="state">State</Label>
                  <Input id="state" {...register("state")} />
                  {errors.state && <p className="text-sm text-destructive">{errors.state.message}</p>}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="country">Country</Label>
                  <Input id="country" {...register("country")} />
                  {errors.country && (
                    <p className="text-sm text-destructive">{errors.country.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="postalCode">Postal code</Label>
                  <Input id="postalCode" {...register("postalCode")} />
                  {errors.postalCode && (
                    <p className="text-sm text-destructive">{errors.postalCode.message}</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {isEditing && (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Emergency contact
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="emergencyContactName">Contact name</Label>
                  <Input id="emergencyContactName" {...register("emergencyContactName")} />
                  {errors.emergencyContactName && (
                    <p className="text-sm text-destructive">{errors.emergencyContactName.message}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="emergencyContactPhone">Contact phone</Label>
                  <Input id="emergencyContactPhone" {...register("emergencyContactPhone")} />
                  {errors.emergencyContactPhone && (
                    <p className="text-sm text-destructive">{errors.emergencyContactPhone.message}</p>
                  )}
                </div>
              </div>
            </div>
          )}

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
