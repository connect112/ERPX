import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

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
import { Textarea } from "@/components/ui/textarea";
import type { VendorPublic } from "@/features/accounting/vendors/api/vendors-api";
import { useCreateVendor, useUpdateVendor } from "@/features/accounting/vendors/api/vendors-hooks";
import { type VendorFormValues, vendorFormSchema } from "@/features/accounting/vendors/schemas/vendor-schemas";

interface VendorFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  vendor?: VendorPublic;
}

const emptyValues: VendorFormValues = {
  vendorCode: "",
  name: "",
  email: "",
  phone: "",
  gstin: "",
  panNumber: "",
  addressLine1: "",
  addressLine2: "",
  city: "",
  state: "",
  country: "",
  postalCode: "",
  bankAccountNumber: "",
  bankIfscCode: "",
  bankName: "",
  notes: "",
};

export function VendorFormDialog({ open, onOpenChange, vendor }: VendorFormDialogProps) {
  const isEditing = !!vendor;
  const createVendor = useCreateVendor();
  const updateVendor = useUpdateVendor(vendor?.id ?? "");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<VendorFormValues>({ resolver: zodResolver(vendorFormSchema), defaultValues: emptyValues });

  useEffect(() => {
    if (open) {
      reset(
        vendor
          ? {
              vendorCode: vendor.vendor_code,
              name: vendor.name,
              email: vendor.email ?? "",
              phone: vendor.phone ?? "",
              gstin: vendor.gstin ?? "",
              panNumber: vendor.pan_number ?? "",
              addressLine1: vendor.address_line1 ?? "",
              addressLine2: vendor.address_line2 ?? "",
              city: vendor.city ?? "",
              state: vendor.state ?? "",
              country: vendor.country ?? "",
              postalCode: vendor.postal_code ?? "",
              bankAccountNumber: vendor.bank_account_number ?? "",
              bankIfscCode: vendor.bank_ifsc_code ?? "",
              bankName: vendor.bank_name ?? "",
              notes: vendor.notes ?? "",
            }
          : emptyValues
      );
    }
  }, [open, vendor, reset]);

  const onSubmit = (values: VendorFormValues) => {
    const shared = {
      name: values.name,
      email: values.email || undefined,
      phone: values.phone || undefined,
      gstin: values.gstin || undefined,
      pan_number: values.panNumber || undefined,
      address_line1: values.addressLine1 || undefined,
      address_line2: values.addressLine2 || undefined,
      city: values.city || undefined,
      state: values.state || undefined,
      country: values.country || undefined,
      postal_code: values.postalCode || undefined,
      bank_account_number: values.bankAccountNumber || undefined,
      bank_ifsc_code: values.bankIfscCode || undefined,
      bank_name: values.bankName || undefined,
      notes: values.notes || undefined,
    };

    if (isEditing) {
      updateVendor.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createVendor.mutate(
        { ...shared, vendor_code: values.vendorCode },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  const mutation = isEditing ? updateVendor : createVendor;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit vendor" : "New vendor"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="vendorCode" required>Code</Label>
              <Input id="vendorCode" disabled={isEditing} {...register("vendorCode")} />
              {errors.vendorCode && (
                <p className="text-sm text-destructive">{errors.vendorCode.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="name" required>Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
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
              <Label htmlFor="gstin">GSTIN</Label>
              <Input id="gstin" {...register("gstin")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="panNumber">PAN</Label>
              <Input id="panNumber" {...register("panNumber")} />
            </div>
          </div>
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
          <div className="grid grid-cols-3 gap-4">
            <Input placeholder="Bank name" {...register("bankName")} />
            <Input placeholder="Bank account number" {...register("bankAccountNumber")} />
            <Input placeholder="IFSC code" {...register("bankIfscCode")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create vendor"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
