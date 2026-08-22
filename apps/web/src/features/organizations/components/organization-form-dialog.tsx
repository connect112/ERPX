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
import type { OrganizationPublic } from "@/features/organizations/api/organizations-api";
import { useCreateOrganization, useUpdateOrganization } from "@/features/organizations/api/organizations-hooks";
import {
  type OrganizationFormValues,
  organizationFormSchema,
  subscriptionPlanLabels,
  subscriptionPlanValues,
} from "@/features/organizations/schemas/organization-schemas";

interface OrganizationFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  organization?: OrganizationPublic;
}

const emptyValues: OrganizationFormValues = {
  name: "",
  slug: "",
  legalName: "",
  industry: "",
  email: "",
  phone: "",
  website: "",
  addressLine1: "",
  city: "",
  state: "",
  country: "",
  postalCode: "",
  subscriptionPlan: "trial",
};

export function OrganizationFormDialog({ open, onOpenChange, organization }: OrganizationFormDialogProps) {
  const isEditing = !!organization;
  const createOrganization = useCreateOrganization();
  const updateOrganization = useUpdateOrganization(organization?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<OrganizationFormValues>({
    resolver: zodResolver(organizationFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        organization
          ? {
              name: organization.name,
              slug: organization.slug,
              legalName: organization.legal_name ?? "",
              industry: organization.industry ?? "",
              email: organization.email ?? "",
              phone: organization.phone ?? "",
              website: organization.website ?? "",
              addressLine1: organization.address_line1 ?? "",
              city: organization.city ?? "",
              state: organization.state ?? "",
              country: organization.country ?? "",
              postalCode: organization.postal_code ?? "",
              subscriptionPlan: organization.subscription_plan,
            }
          : emptyValues
      );
    }
  }, [open, organization, reset]);

  const mutation = isEditing ? updateOrganization : createOrganization;

  const onSubmit = (values: OrganizationFormValues) => {
    const shared = {
      name: values.name,
      legal_name: values.legalName || undefined,
      industry: values.industry || undefined,
      email: values.email || undefined,
      phone: values.phone || undefined,
      website: values.website || undefined,
      address_line1: values.addressLine1 || undefined,
      city: values.city || undefined,
      state: values.state || undefined,
      country: values.country || undefined,
      postal_code: values.postalCode || undefined,
      subscription_plan: values.subscriptionPlan,
    };

    if (isEditing) {
      updateOrganization.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createOrganization.mutate({ ...shared, slug: values.slug }, { onSuccess: () => onOpenChange(false) });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit organization" : "New organization"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name" required>Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="slug" required>Slug</Label>
              <Input id="slug" disabled={isEditing} placeholder="e.g. gir-technologies" {...register("slug")} />
              {errors.slug && <p className="text-sm text-destructive">{errors.slug.message}</p>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="legalName">Legal name</Label>
              <Input id="legalName" {...register("legalName")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="industry">Industry</Label>
              <Input id="industry" {...register("industry")} />
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
              <Label htmlFor="website">Website</Label>
              <Input id="website" {...register("website")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="subscriptionPlan" required>Subscription plan</Label>
              <Controller
                control={control}
                name="subscriptionPlan"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="subscriptionPlan">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {subscriptionPlanValues.map((p) => (
                        <SelectItem key={p} value={p}>
                          {subscriptionPlanLabels[p]}
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create organization"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
