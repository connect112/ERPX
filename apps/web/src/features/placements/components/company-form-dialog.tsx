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
import type { CompanyPublic } from "@/features/placements/api/placements-api";
import { useCreateCompany, useUpdateCompany } from "@/features/placements/api/placements-hooks";
import {
  type CompanyFormValues,
  companyFormSchema,
} from "@/features/placements/schemas/company-schemas";

interface CompanyFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  company?: CompanyPublic;
}

const emptyValues: CompanyFormValues = {
  name: "",
  industry: "",
  website: "",
  contactPersonName: "",
  contactEmail: "",
  contactPhone: "",
  notes: "",
};

export function CompanyFormDialog({ open, onOpenChange, company }: CompanyFormDialogProps) {
  const isEditing = !!company;
  const createCompany = useCreateCompany();
  const updateCompany = useUpdateCompany(company?.id ?? "");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CompanyFormValues>({
    resolver: zodResolver(companyFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        company
          ? {
              name: company.name,
              industry: company.industry ?? "",
              website: company.website ?? "",
              contactPersonName: company.contact_person_name ?? "",
              contactEmail: company.contact_email ?? "",
              contactPhone: company.contact_phone ?? "",
              notes: company.notes ?? "",
            }
          : emptyValues
      );
    }
  }, [open, company, reset]);

  const mutation = isEditing ? updateCompany : createCompany;

  const onSubmit = (values: CompanyFormValues) => {
    const payload = {
      name: values.name,
      industry: values.industry || undefined,
      website: values.website || undefined,
      contact_person_name: values.contactPersonName || undefined,
      contact_email: values.contactEmail || undefined,
      contact_phone: values.contactPhone || undefined,
      notes: values.notes || undefined,
    };
    mutation.mutate(payload, { onSuccess: () => onOpenChange(false) });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit company" : "New company"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="industry">Industry</Label>
              <Input id="industry" {...register("industry")} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="website">Website</Label>
            <Input id="website" {...register("website")} />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="contactPersonName">Contact person</Label>
              <Input id="contactPersonName" {...register("contactPersonName")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contactEmail">Contact email</Label>
              <Input id="contactEmail" type="email" {...register("contactEmail")} />
              {errors.contactEmail && (
                <p className="text-sm text-destructive">{errors.contactEmail.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="contactPhone">Contact phone</Label>
              <Input id="contactPhone" {...register("contactPhone")} />
            </div>
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create company"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
