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
import { useCustomersList } from "@/features/accounting/customers/api/customers-hooks";
import type { ClientPublic } from "@/features/corporate/clients/api/clients-api";
import { useCreateClient, useUpdateClient } from "@/features/corporate/clients/api/clients-hooks";
import { type ClientFormValues, clientFormSchema } from "@/features/corporate/clients/schemas/client-schemas";

interface ClientFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  client?: ClientPublic;
}

const emptyValues: ClientFormValues = {
  clientCode: "",
  name: "",
  accountingCustomerId: "",
  accountManagerUserId: "",
  industry: "",
  website: "",
  gstin: "",
  contactPersonName: "",
  contactEmail: "",
  contactPhone: "",
  addressLine1: "",
  city: "",
  state: "",
  country: "",
  postalCode: "",
  notes: "",
};

export function ClientFormDialog({ open, onOpenChange, client }: ClientFormDialogProps) {
  const isEditing = !!client;
  const createClient = useCreateClient();
  const updateClient = useUpdateClient(client?.id ?? "");
  const { data: customers } = useCustomersList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ClientFormValues>({
    resolver: zodResolver(clientFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        client
          ? {
              clientCode: client.client_code,
              name: client.name,
              accountingCustomerId: client.accounting_customer_id ?? "",
              accountManagerUserId: client.account_manager_user_id ?? "",
              industry: client.industry ?? "",
              website: client.website ?? "",
              gstin: client.gstin ?? "",
              contactPersonName: client.contact_person_name ?? "",
              contactEmail: client.contact_email ?? "",
              contactPhone: client.contact_phone ?? "",
              addressLine1: client.address_line1 ?? "",
              city: client.city ?? "",
              state: client.state ?? "",
              country: client.country ?? "",
              postalCode: client.postal_code ?? "",
              notes: client.notes ?? "",
            }
          : emptyValues
      );
    }
  }, [open, client, reset]);

  const mutation = isEditing ? updateClient : createClient;

  const onSubmit = (values: ClientFormValues) => {
    const shared = {
      name: values.name,
      accounting_customer_id: values.accountingCustomerId || undefined,
      industry: values.industry || undefined,
      website: values.website || undefined,
      gstin: values.gstin || undefined,
      contact_person_name: values.contactPersonName || undefined,
      contact_email: values.contactEmail || undefined,
      contact_phone: values.contactPhone || undefined,
      address_line1: values.addressLine1 || undefined,
      city: values.city || undefined,
      state: values.state || undefined,
      country: values.country || undefined,
      postal_code: values.postalCode || undefined,
      notes: values.notes || undefined,
    };

    if (isEditing) {
      updateClient.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createClient.mutate(
        { ...shared, client_code: values.clientCode },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit client" : "New client"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="clientCode">Client code</Label>
              <Input id="clientCode" disabled={isEditing} {...register("clientCode")} />
              {errors.clientCode && (
                <p className="text-sm text-destructive">{errors.clientCode.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="industry">Industry</Label>
              <Input id="industry" {...register("industry")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="website">Website</Label>
              <Input id="website" {...register("website")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="gstin">GSTIN</Label>
              <Input id="gstin" {...register("gstin")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="accountingCustomerId">Linked accounting customer</Label>
              <Controller
                control={control}
                name="accountingCustomerId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="accountingCustomerId">
                      <SelectValue placeholder="Select customer" />
                    </SelectTrigger>
                    <SelectContent>
                      {customers?.items.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Contact
            </p>
            <div className="grid grid-cols-2 gap-4">
              <Input placeholder="Contact person name" {...register("contactPersonName")} />
              <Input placeholder="Contact email" type="email" {...register("contactEmail")} />
            </div>
            <Input placeholder="Contact phone" {...register("contactPhone")} />
            {errors.contactEmail && (
              <p className="text-sm text-destructive">{errors.contactEmail.message}</p>
            )}
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create client"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
