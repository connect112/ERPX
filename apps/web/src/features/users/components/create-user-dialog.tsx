import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
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
import { useBranches } from "@/features/branches/api/branches-hooks";
import { useCreateUserProfile, useRegisterUser } from "@/features/users/api/users-hooks";
import {
  type CreateUserFormValues,
  createUserFormSchema,
  genderLabels,
  genderValues,
} from "@/features/users/schemas/user-schemas";

interface CreateUserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  organizationId: string;
}

const emptyValues: CreateUserFormValues = {
  email: "",
  password: "",
  fullName: "",
  phoneNumber: "",
  branchId: "",
  employeeCode: "",
  designation: "",
  department: "",
  gender: "",
};

export function CreateUserDialog({ open, onOpenChange, organizationId }: CreateUserDialogProps) {
  const registerUser = useRegisterUser();
  const createProfile = useCreateUserProfile();
  const { data: branches } = useBranches(organizationId);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateUserFormValues>({
    resolver: zodResolver(createUserFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(emptyValues);
      setSubmitError(null);
    }
  }, [open, reset]);

  const isPending = registerUser.isPending || createProfile.isPending;

  const onSubmit = async (values: CreateUserFormValues) => {
    setSubmitError(null);
    try {
      const newUser = await registerUser.mutateAsync({
        email: values.email,
        password: values.password,
        full_name: values.fullName,
        phone_number: values.phoneNumber || undefined,
      });
      await createProfile.mutateAsync({
        user_id: newUser.id,
        organization_id: organizationId,
        branch_id: values.branchId || undefined,
        employee_code: values.employeeCode || undefined,
        designation: values.designation || undefined,
        department: values.department || undefined,
        gender: values.gender || undefined,
      });
      onOpenChange(false);
    } catch (error) {
      const message =
        (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
          ?.message ?? "Something went wrong. Please try again.";
      setSubmitError(message);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New user</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="fullName" required>Full name</Label>
              <Input id="fullName" {...register("fullName")} />
              {errors.fullName && (
                <p className="text-sm text-destructive">{errors.fullName.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="email" required>Email</Label>
              <Input id="email" type="email" {...register("email")} />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="password" required>Temporary password</Label>
              <Input id="password" type="password" {...register("password")} />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="phoneNumber">Phone</Label>
              <Input id="phoneNumber" {...register("phoneNumber")} />
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Profile
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="branchId">Branch</Label>
                <Controller
                  control={control}
                  name="branchId"
                  render={({ field }) => (
                    <Select value={field.value || undefined} onValueChange={field.onChange}>
                      <SelectTrigger id="branchId">
                        <SelectValue placeholder="Select branch" />
                      </SelectTrigger>
                      <SelectContent>
                        {branches?.map((b) => (
                          <SelectItem key={b.id} value={b.id}>
                            {b.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
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
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input placeholder="Employee code" {...register("employeeCode")} />
              <Input placeholder="Designation" {...register("designation")} />
            </div>
            <Input placeholder="Department" {...register("department")} />
          </div>

          {submitError && <p className="text-sm text-destructive">{submitError}</p>}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Creating..." : "Create user"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
