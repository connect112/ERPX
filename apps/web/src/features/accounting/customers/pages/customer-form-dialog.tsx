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
import type { CustomerPublic } from "@/features/accounting/customers/api/customers-api";
import { useCreateCustomer, useUpdateCustomer } from "@/features/accounting/customers/api/customers-hooks";
import {
  type CustomerFormValues,
  customerFormSchema,
  customerTypeLabels,
  customerTypeValues,
} from "@/features/accounting/customers/schemas/customer-schemas";

interface CustomerFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  customer?: CustomerPublic;
}

const emptyValues: CustomerFormValues = {
  customerCode: "",
  name: "",
  customerType: "individual",
  email: "",
  phone: "",
  gstin: "",
  billingAddressLine1: "",
  billingAddressLine2: "",
  city: "",
  state: "",
  country: "",
  postalCode: "",
  creditLimit: "0",
  notes: "",
};

export function CustomerFormDialog({ open, onOpenChange, customer }: CustomerFormDialogProps) {
  const isEditing = !!customer;
  const createCustomer = useCreateCustomer();
  const updateCustomer = useUpdateCustomer(customer?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CustomerFormValues>({ resolver: zodResolver(customerFormSchema), defaultValues: emptyValues });

  useEffect(() => {
    if (open) {
      reset(
        customer
          ? {
              customerCode: customer.customer_code,
              name: customer.name,
              customerType: customer.customer_type,
              email: customer.email ?? "",
              phone: customer.phone ?? "",
              gstin: customer.gstin ?? "",
              billingAddressLine1: customer.billing_address_line1 ?? "",
              billingAddressLine2: customer.billing_address_line2 ?? "",
              city: customer.city ?? "",
              state: customer.state ?? "",
              country: customer.country ?? "",
              postalCode: customer.postal_code ?? "",
              creditLimit: String(customer.credit_limit),
              notes: customer.notes ?? "",
            }
          : emptyValues
      );
    }
  }, [open, customer, reset]);

  const onSubmit = (values: CustomerFormValues) => {
    const shared = {
      name: values.name,
      email: values.email || undefined,
      phone: values.phone || undefined,
      gstin: values.gstin || undefined,
      billing_address_line1: values.billingAddressLine1 || undefined,
      billing_address_line2: values.billingAddressLine2 || undefined,
      city: values.city || undefined,
      state: values.state || undefined,
      country: values.country || undefined,
      postal_code: values.postalCode || undefined,
      credit_limit: values.creditLimit ? Number(values.creditLimit) : undefined,
      notes: values.notes || undefined,
    };

    if (isEditing) {
      updateCustomer.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createCustomer.mutate(
        { ...shared, customer_code: values.customerCode, customer_type: values.customerType },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  const mutation = isEditing ? updateCustomer : createCustomer;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit customer" : "New customer"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="customerCode">Code</Label>
              <Input id="customerCode" disabled={isEditing} {...register("customerCode")} />
              {errors.customerCode && (
                <p className="text-sm text-destructive">{errors.customerCode.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="customerType">Type</Label>
              <Controller
                control={control}
                name="customerType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange} disabled={isEditing}>
                    <SelectTrigger id="customerType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {customerTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {customerTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input id="name" {...register("name")} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
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
              <Label htmlFor="creditLimit">Credit limit</Label>
              <Input id="creditLimit" type="number" step="0.01" {...register("creditLimit")} />
            </div>
          </div>
          <div className="space-y-2">
            <Input placeholder="Billing address line 1" {...register("billingAddressLine1")} />
            <Input placeholder="Billing address line 2" {...register("billingAddressLine2")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input placeholder="City" {...register("city")} />
            <Input placeholder="State" {...register("state")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input placeholder="Country" {...register("country")} />
            <Input placeholder="Postal code" {...register("postalCode")} />
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create customer"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
