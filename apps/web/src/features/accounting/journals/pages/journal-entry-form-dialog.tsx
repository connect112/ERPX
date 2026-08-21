import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { Controller, useFieldArray, useForm } from "react-hook-form";

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
import { useCreateJournalEntry } from "@/features/accounting/journals/api/journals-hooks";
import {
  type JournalEntryFormValues,
  journalEntryFormSchema,
} from "@/features/accounting/journals/schemas/journal-schemas";

interface JournalEntryFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function JournalEntryFormDialog({ open, onOpenChange }: JournalEntryFormDialogProps) {
  const { data: accounts } = useAccountsList({ limit: 500, is_active: true });
  const createEntry = useCreateJournalEntry();

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<JournalEntryFormValues>({
    resolver: zodResolver(journalEntryFormSchema),
    defaultValues: {
      entryDate: new Date().toISOString().slice(0, 16),
      memo: "",
      lines: [
        { accountId: "", description: "", debit: "", credit: "" },
        { accountId: "", description: "", debit: "", credit: "" },
      ],
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "lines" });
  const lines = watch("lines");

  const totalDebit = lines.reduce((sum, l) => sum + (Number(l.debit) || 0), 0);
  const totalCredit = lines.reduce((sum, l) => sum + (Number(l.credit) || 0), 0);
  const isBalanced = totalDebit > 0 && totalDebit === totalCredit;

  const onSubmit = (values: JournalEntryFormValues) => {
    createEntry.mutate(
      {
        entry_date: new Date(values.entryDate).toISOString(),
        memo: values.memo || undefined,
        lines: values.lines.map((l) => ({
          account_id: l.accountId,
          description: l.description || undefined,
          debit: l.debit ? Number(l.debit) : 0,
          credit: l.credit ? Number(l.credit) : 0,
        })),
      },
      {
        onSuccess: () => {
          onOpenChange(false);
          reset();
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New manual journal entry</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="entryDate" required>Entry date</Label>
              <Input id="entryDate" type="datetime-local" {...register("entryDate")} />
              {errors.entryDate && (
                <p className="text-sm text-destructive">{errors.entryDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="memo">Memo</Label>
              <Input id="memo" {...register("memo")} />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium leading-none">Lines</p>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => append({ accountId: "", description: "", debit: "", credit: "" })}
              >
                <Plus className="h-3 w-3" />
                Add line
              </Button>
            </div>
            {errors.lines?.message && (
              <p className="text-sm text-destructive">{errors.lines.message}</p>
            )}
            <div className="space-y-2">
              {fields.map((field, index) => (
                <div key={field.id} className="grid grid-cols-12 items-start gap-2">
                  <div className="col-span-4">
                    <Controller
                      control={control}
                      name={`lines.${index}.accountId`}
                      render={({ field: selectField }) => (
                        <Select value={selectField.value || undefined} onValueChange={selectField.onChange}>
                          <SelectTrigger>
                            <SelectValue placeholder="Account" />
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
                    {errors.lines?.[index]?.accountId && (
                      <p className="mt-1 text-xs text-destructive">
                        {errors.lines[index]?.accountId?.message}
                      </p>
                    )}
                  </div>
                  <div className="col-span-3">
                    <Input placeholder="Description" {...register(`lines.${index}.description`)} />
                  </div>
                  <div className="col-span-2">
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="Debit"
                      {...register(`lines.${index}.debit`)}
                    />
                  </div>
                  <div className="col-span-2">
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="Credit"
                      {...register(`lines.${index}.credit`)}
                    />
                  </div>
                  <div className="col-span-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      disabled={fields.length <= 2}
                      onClick={() => remove(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-end gap-4 border-t pt-2 text-sm">
              <span className="text-muted-foreground">
                Debit: <span className="font-medium text-foreground">{totalDebit.toFixed(2)}</span>
              </span>
              <span className="text-muted-foreground">
                Credit: <span className="font-medium text-foreground">{totalCredit.toFixed(2)}</span>
              </span>
              <span className={isBalanced ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"}>
                {isBalanced ? "Balanced" : "Not balanced"}
              </span>
            </div>
          </div>

          {createEntry.isError && (
            <p className="text-sm text-destructive">
              {(createEntry.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!isBalanced || createEntry.isPending}>
              {createEntry.isPending ? "Saving..." : "Create draft entry"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
