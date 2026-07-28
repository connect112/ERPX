import { zodResolver } from "@hookform/resolvers/zod";
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
import { useRenewContract } from "@/features/corporate/contracts/api/contracts-hooks";
import {
  type RenewContractFormValues,
  renewContractFormSchema,
} from "@/features/corporate/contracts/schemas/contract-schemas";

interface RenewContractDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  contractId: string | null;
}

export function RenewContractDialog({ open, onOpenChange, contractId }: RenewContractDialogProps) {
  const renewContract = useRenewContract(contractId ?? "");

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RenewContractFormValues>({
    resolver: zodResolver(renewContractFormSchema),
    defaultValues: { newEndDate: "", newContractValue: undefined },
  });

  const onSubmit = (values: RenewContractFormValues) => {
    renewContract.mutate(
      { newEndDate: values.newEndDate, newContractValue: values.newContractValue },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Renew contract</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="newEndDate">New end date</Label>
            <Input id="newEndDate" type="date" {...register("newEndDate")} />
            {errors.newEndDate && (
              <p className="text-sm text-destructive">{errors.newEndDate.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="newContractValue">New contract value (optional)</Label>
            <Input id="newContractValue" type="number" step="0.01" {...register("newContractValue")} />
          </div>

          {renewContract.isError && (
            <p className="text-sm text-destructive">
              {(renewContract.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={renewContract.isPending}>
              {renewContract.isPending ? "Renewing..." : "Renew"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
