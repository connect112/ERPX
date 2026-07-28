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
import { useBranches } from "@/features/branches/api/branches-hooks";
import type { UserProfilePublic } from "@/features/users/api/users-api";
import { useUpdateUserProfile } from "@/features/users/api/users-hooks";
import {
  type UserProfileFormValues,
  genderLabels,
  genderValues,
  userProfileFormSchema,
} from "@/features/users/schemas/user-schemas";

interface UserProfileFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  profile: UserProfilePublic;
}

export function UserProfileFormDialog({ open, onOpenChange, profile }: UserProfileFormDialogProps) {
  const updateProfile = useUpdateUserProfile(profile.user_id);
  const { data: branches } = useBranches(profile.organization_id);

  const { register, control, handleSubmit, reset } = useForm<UserProfileFormValues>({
    resolver: zodResolver(userProfileFormSchema),
  });

  useEffect(() => {
    if (open) {
      reset({
        branchId: profile.branch_id ?? "",
        employeeCode: profile.employee_code ?? "",
        designation: profile.designation ?? "",
        department: profile.department ?? "",
        gender: profile.gender ?? "",
        dateOfBirth: profile.date_of_birth ?? "",
        dateOfJoining: profile.date_of_joining ?? "",
        addressLine1: profile.address_line1 ?? "",
        city: profile.city ?? "",
        state: profile.state ?? "",
        country: profile.country ?? "",
        postalCode: profile.postal_code ?? "",
      });
    }
  }, [open, profile, reset]);

  const onSubmit = (values: UserProfileFormValues) => {
    updateProfile.mutate(
      {
        branch_id: values.branchId || undefined,
        employee_code: values.employeeCode || undefined,
        designation: values.designation || undefined,
        department: values.department || undefined,
        gender: values.gender || undefined,
        date_of_birth: values.dateOfBirth || undefined,
        date_of_joining: values.dateOfJoining || undefined,
        address_line1: values.addressLine1 || undefined,
        city: values.city || undefined,
        state: values.state || undefined,
        country: values.country || undefined,
        postal_code: values.postalCode || undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Edit profile</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
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
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="dateOfBirth">Date of birth</Label>
              <Input id="dateOfBirth" type="date" {...register("dateOfBirth")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="dateOfJoining">Date of joining</Label>
              <Input id="dateOfJoining" type="date" {...register("dateOfJoining")} />
            </div>
          </div>
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Address
            </p>
            <Input placeholder="Address line 1" {...register("addressLine1")} />
            <div className="grid grid-cols-2 gap-4">
              <Input placeholder="City" {...register("city")} />
              <Input placeholder="State" {...register("state")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input placeholder="Country" {...register("country")} />
              <Input placeholder="Postal code" {...register("postalCode")} />
            </div>
          </div>

          {updateProfile.isError && (
            <p className="text-sm text-destructive">
              {(updateProfile.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateProfile.isPending}>
              {updateProfile.isPending ? "Saving..." : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
