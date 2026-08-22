import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { useEffect, useId } from "react";

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
import type { BranchPublic } from "@/features/branches/api/branches-api";
import { useCreateBranch, useUpdateBranch } from "@/features/branches/api/branches-hooks";
import { type BranchFormValues, branchFormSchema } from "@/features/branches/schemas/branch-schemas";

interface BranchFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  organizationId: string;
  branch?: BranchPublic;
}

const emptyValues: BranchFormValues = {
  name: "",
  code: "",
  addressLine1: "",
  city: "",
  state: "",
  country: "",
  postalCode: "",
  phone: "",
  email: "",
  isHeadOffice: false,
};

export function BranchFormDialog({ open, onOpenChange, organizationId, branch }: BranchFormDialogProps) {
  const isEditing = !!branch;
  const createBranch = useCreateBranch(organizationId);
  const updateBranch = useUpdateBranch(organizationId);
  const isHeadOfficeId = useId();

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BranchFormValues>({
    resolver: zodResolver(branchFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        branch
          ? {
              name: branch.name,
              code: branch.code,
              addressLine1: branch.address_line1 ?? "",
              city: branch.city ?? "",
              state: branch.state ?? "",
              country: branch.country ?? "",
              postalCode: branch.postal_code ?? "",
              phone: branch.phone ?? "",
              email: branch.email ?? "",
              isHeadOffice: branch.is_head_office,
            }
          : emptyValues
      );
    }
  }, [open, branch, reset]);

  const mutation = isEditing ? updateBranch : createBranch;

  const onSubmit = (values: BranchFormValues) => {
    const shared = {
      name: values.name,
      address_line1: values.addressLine1 || undefined,
      city: values.city || undefined,
      state: values.state || undefined,
      country: values.country || undefined,
      postal_code: values.postalCode || undefined,
      phone: values.phone || undefined,
      email: values.email || undefined,
      is_head_office: values.isHeadOffice,
    };

    if (isEditing) {
      updateBranch.mutate({ id: branch.id, payload: shared }, { onSuccess: () => onOpenChange(false) });
    } else {
      createBranch.mutate(
        { ...shared, organization_id: organizationId, code: values.code },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit branch" : "New branch"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name" required>Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="code" required>Code</Label>
              <Input id="code" disabled={isEditing} {...register("code")} />
              {errors.code && <p className="text-sm text-destructive">{errors.code.message}</p>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input placeholder="Phone" {...register("phone")} />
            <div>
              <Input placeholder="Email" type="email" {...register("email")} />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>
          </div>
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
          <label htmlFor={isHeadOfficeId} className="flex items-center gap-2 text-sm">
            <Controller
              control={control}
              name="isHeadOffice"
              render={({ field }) => (
                <input
                  id={isHeadOfficeId}
                  type="checkbox"
                  className="h-4 w-4 rounded border-input"
                  checked={field.value}
                  onChange={(e) => field.onChange(e.target.checked)}
                />
              )}
            />
            Head office
          </label>

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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create branch"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
