import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useId, useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAccountsList } from "@/features/accounting/ledger/api/accounts-hooks";
import { useCreateSalaryComponent, useSalaryComponents } from "@/features/payroll/api/payroll-hooks";
import {
  type SalaryComponentFormValues,
  salaryComponentFormSchema,
  salaryComponentTypeLabels,
  salaryComponentTypeValues,
} from "@/features/payroll/schemas/payroll-schemas";

const emptyValues: SalaryComponentFormValues = {
  name: "",
  code: "",
  glAccountId: "",
  componentType: "earning",
  isTaxable: true,
};

export function SalaryComponentsPage() {
  const { data: components, isLoading, isError } = useSalaryComponents();
  const { data: accounts } = useAccountsList({ limit: 200 });
  const createComponent = useCreateSalaryComponent();
  const isTaxableId = useId();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<SalaryComponentFormValues>({
    resolver: zodResolver(salaryComponentFormSchema),
    defaultValues: emptyValues,
  });

  const accountName = (id: string) => {
    const account = accounts?.items.find((a) => a.id === id);
    return account ? `${account.code} — ${account.name}` : id;
  };

  const onSubmit = (values: SalaryComponentFormValues) => {
    createComponent.mutate(
      {
        name: values.name,
        code: values.code,
        gl_account_id: values.glAccountId,
        component_type: values.componentType,
        is_taxable: values.isTaxable,
      },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset(emptyValues);
        },
      }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Salary Components</h1>
          <p className="mt-1 text-muted-foreground">
            Configure the earnings and deductions used in salary structures.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New component
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All components</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && <p className="text-sm text-destructive">Failed to load salary components.</p>}
          {!isLoading && !isError && (components?.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No salary components yet.</p>
          )}
          {!isLoading && !isError && (components?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>GL account</TableHead>
                  <TableHead>Taxable</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {components?.map((component) => (
                  <TableRow key={component.id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {component.code}
                    </TableCell>
                    <TableCell className="font-medium">{component.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {salaryComponentTypeLabels[component.component_type]}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {accountName(component.gl_account_id)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {component.is_taxable ? "Yes" : "No"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={component.is_active ? "success" : "secondary"}>
                        {component.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New salary component</DialogTitle>
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
                <Input id="code" {...register("code")} />
                {errors.code && <p className="text-sm text-destructive">{errors.code.message}</p>}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="glAccountId" required>GL account</Label>
              <Controller
                control={control}
                name="glAccountId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="glAccountId">
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
              {errors.glAccountId && (
                <p className="text-sm text-destructive">{errors.glAccountId.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="componentType" required>Type</Label>
              <Controller
                control={control}
                name="componentType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="componentType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {salaryComponentTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {salaryComponentTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <label htmlFor={isTaxableId} className="flex items-center gap-2 text-sm">
              <Controller
                control={control}
                name="isTaxable"
                render={({ field }) => (
                  <input
                    id={isTaxableId}
                    type="checkbox"
                    className="h-4 w-4 rounded border-input"
                    checked={field.value}
                    onChange={(e) => field.onChange(e.target.checked)}
                  />
                )}
              />
              Taxable
            </label>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createComponent.isPending}>
                {createComponent.isPending ? "Saving..." : "Create component"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
