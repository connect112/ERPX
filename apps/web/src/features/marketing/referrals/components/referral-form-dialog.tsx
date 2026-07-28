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
import { useStudentsList } from "@/features/students/api/students-hooks";
import { useCreateReferral, useReferralPrograms } from "@/features/marketing/referrals/api/referrals-hooks";
import {
  type ReferralFormValues,
  referralFormSchema,
} from "@/features/marketing/referrals/schemas/referral-schemas";

interface ReferralFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const emptyValues: ReferralFormValues = {
  referralProgramId: "",
  referrerStudentId: "",
  refereeName: "",
  refereeEmail: "",
  refereePhone: "",
};

export function ReferralFormDialog({ open, onOpenChange }: ReferralFormDialogProps) {
  const createReferral = useCreateReferral();
  const { data: programs } = useReferralPrograms(true);
  const { data: students } = useStudentsList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ReferralFormValues>({
    resolver: zodResolver(referralFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: ReferralFormValues) => {
    createReferral.mutate(
      {
        referral_program_id: values.referralProgramId,
        referrer_student_id: values.referrerStudentId || undefined,
        referee_name: values.refereeName,
        referee_email: values.refereeEmail || undefined,
        referee_phone: values.refereePhone || undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New referral</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="referralProgramId">Referral program</Label>
            <Controller
              control={control}
              name="referralProgramId"
              render={({ field }) => (
                <Select value={field.value || undefined} onValueChange={field.onChange}>
                  <SelectTrigger id="referralProgramId">
                    <SelectValue placeholder="Select program" />
                  </SelectTrigger>
                  <SelectContent>
                    {programs?.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.referralProgramId && (
              <p className="text-sm text-destructive">{errors.referralProgramId.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="referrerStudentId">Referrer (student)</Label>
            <Controller
              control={control}
              name="referrerStudentId"
              render={({ field }) => (
                <Select value={field.value || undefined} onValueChange={field.onChange}>
                  <SelectTrigger id="referrerStudentId">
                    <SelectValue placeholder="Select student" />
                  </SelectTrigger>
                  <SelectContent>
                    {students?.items.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.full_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="refereeName">Referee name</Label>
            <Input id="refereeName" {...register("refereeName")} />
            {errors.refereeName && (
              <p className="text-sm text-destructive">{errors.refereeName.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="refereeEmail">Referee email</Label>
              <Input id="refereeEmail" type="email" {...register("refereeEmail")} />
              {errors.refereeEmail && (
                <p className="text-sm text-destructive">{errors.refereeEmail.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="refereePhone">Referee phone</Label>
              <Input id="refereePhone" {...register("refereePhone")} />
            </div>
          </div>

          {createReferral.isError && (
            <p className="text-sm text-destructive">
              {(createReferral.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createReferral.isPending}>
              {createReferral.isPending ? "Saving..." : "Create referral"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
