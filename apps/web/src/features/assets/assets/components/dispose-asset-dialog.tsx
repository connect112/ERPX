import { zodResolver } from "@hookform/resolvers/zod";
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
import { useAccountsList } from "@/features/accounting/ledger/api/accounts-hooks";
import { useDisposeAsset } from "@/features/assets/assets/api/assets-hooks";
import {
  type DisposeAssetFormValues,
  disposeAssetFormSchema,
} from "@/features/assets/assets/schemas/asset-schemas";

interface DisposeAssetDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assetId: string;
}

export function DisposeAssetDialog({ open, onOpenChange, assetId }: DisposeAssetDialogProps) {
  const disposeAsset = useDisposeAsset(assetId);
  const { data: accounts } = useAccountsList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<DisposeAssetFormValues>({
    resolver: zodResolver(disposeAssetFormSchema),
    defaultValues: { disposalDate: "", disposalAmount: 0, cashAccountId: "", gainLossAccountId: "" },
  });

  const onSubmit = (values: DisposeAssetFormValues) => {
    disposeAsset.mutate(
      {
        disposal_date: values.disposalDate,
        disposal_amount: values.disposalAmount,
        cash_account_id: values.cashAccountId,
        gain_loss_account_id: values.gainLossAccountId,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Dispose asset</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="disposalDate">Disposal date</Label>
              <Input id="disposalDate" type="date" {...register("disposalDate")} />
              {errors.disposalDate && (
                <p className="text-sm text-destructive">{errors.disposalDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="disposalAmount">Disposal amount</Label>
              <Input id="disposalAmount" type="number" step="0.01" {...register("disposalAmount")} />
              {errors.disposalAmount && (
                <p className="text-sm text-destructive">{errors.disposalAmount.message}</p>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="cashAccountId">Cash / bank account</Label>
            <Controller
              control={control}
              name="cashAccountId"
              render={({ field }) => (
                <Select value={field.value || undefined} onValueChange={field.onChange}>
                  <SelectTrigger id="cashAccountId">
                    <SelectValue placeholder="Select GL account" />
                  </SelectTrigger>
                  <SelectContent>
                    {accounts?.items.map((a) => (
                      <SelectItem key={a.id} value={a.id}>
                        {a.code} — {a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.cashAccountId && (
              <p className="text-sm text-destructive">{errors.cashAccountId.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="gainLossAccountId">Gain / loss account</Label>
            <Controller
              control={control}
              name="gainLossAccountId"
              render={({ field }) => (
                <Select value={field.value || undefined} onValueChange={field.onChange}>
                  <SelectTrigger id="gainLossAccountId">
                    <SelectValue placeholder="Select GL account" />
                  </SelectTrigger>
                  <SelectContent>
                    {accounts?.items.map((a) => (
                      <SelectItem key={a.id} value={a.id}>
                        {a.code} — {a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.gainLossAccountId && (
              <p className="text-sm text-destructive">{errors.gainLossAccountId.message}</p>
            )}
          </div>

          {disposeAsset.isError && (
            <p className="text-sm text-destructive">
              {(disposeAsset.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive" disabled={disposeAsset.isPending}>
              {disposeAsset.isPending ? "Disposing..." : "Dispose asset"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
