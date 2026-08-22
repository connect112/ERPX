import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useState } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import {
  useAMCVisits,
  useCancelAMCVisit,
  useCompleteAMCVisit,
  useCreateAMCVisit,
} from "@/features/corporate/amc/api/amc-hooks";
import {
  type AMCVisitFormValues,
  amcVisitFormSchema,
  amcVisitStatusLabels,
} from "@/features/corporate/amc/schemas/amc-schemas";

interface AMCVisitsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  contractId: string | null;
}

export function AMCVisitsDialog({ open, onOpenChange, contractId }: AMCVisitsDialogProps) {
  const { data: visits, isLoading } = useAMCVisits(contractId ?? undefined);
  const { data: employees } = useEmployeesList({ limit: 200 });
  const createVisit = useCreateAMCVisit(contractId ?? "");
  const completeVisit = useCompleteAMCVisit();
  const cancelVisit = useCancelAMCVisit();
  const [formOpen, setFormOpen] = useState(false);
  const [findingsFor, setFindingsFor] = useState<string | null>(null);
  const [findings, setFindings] = useState("");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AMCVisitFormValues>({
    resolver: zodResolver(amcVisitFormSchema),
    defaultValues: { visitDate: "", purpose: "", engineerEmployeeId: "" },
  });

  const engineerName = (id: string | null) => employees?.items.find((e) => e.id === id)?.full_name ?? "—";

  const onSubmit = (values: AMCVisitFormValues) => {
    createVisit.mutate(
      {
        visit_date: values.visitDate,
        purpose: values.purpose,
        engineer_employee_id: values.engineerEmployeeId || undefined,
      },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset();
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>AMC visits</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button size="sm" onClick={() => setFormOpen(true)}>
              <Plus className="h-4 w-4" />
              Schedule visit
            </Button>
          </div>
          {isLoading && <Skeleton className="h-24 w-full" />}
          {!isLoading && (visits?.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No visits scheduled.</p>
          )}
          {!isLoading && (visits?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Purpose</TableHead>
                  <TableHead>Engineer</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {visits?.map((visit) => (
                  <TableRow key={visit.id}>
                    <TableCell className="text-muted-foreground">
                      {new Date(visit.visit_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="max-w-[140px] truncate">{visit.purpose}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {engineerName(visit.engineer_employee_id)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {amcVisitStatusLabels[visit.status]}
                    </TableCell>
                    <TableCell className="text-right">
                      {visit.status === "scheduled" && (
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => setFindingsFor(visit.id)}>
                            Complete
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => cancelVisit.mutate(visit.id)}
                            disabled={cancelVisit.isPending}
                          >
                            Cancel
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </DialogContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule AMC visit</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="visitDate" required>Visit date</Label>
              <Input id="visitDate" type="date" {...register("visitDate")} />
              {errors.visitDate && (
                <p className="text-sm text-destructive">{errors.visitDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="purpose" required>Purpose</Label>
              <Textarea id="purpose" rows={2} {...register("purpose")} />
              {errors.purpose && <p className="text-sm text-destructive">{errors.purpose.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="engineerEmployeeId">Engineer</Label>
              <Controller
                control={control}
                name="engineerEmployeeId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="engineerEmployeeId">
                      <SelectValue placeholder="Select employee" />
                    </SelectTrigger>
                    <SelectContent>
                      {employees?.items.map((e) => (
                        <SelectItem key={e.id} value={e.id}>
                          {e.full_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createVisit.isPending}>
                {createVisit.isPending ? "Saving..." : "Schedule visit"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!findingsFor} onOpenChange={(o) => !o && setFindingsFor(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Complete visit</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="findings">Findings</Label>
            <Textarea id="findings" rows={3} value={findings} onChange={(e) => setFindings(e.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFindingsFor(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (!findingsFor) return;
                completeVisit.mutate(
                  { visitId: findingsFor, findings },
                  {
                    onSuccess: () => {
                      setFindingsFor(null);
                      setFindings("");
                    },
                  }
                );
              }}
              disabled={!findings.trim() || completeVisit.isPending}
            >
              {completeVisit.isPending ? "Saving..." : "Mark completed"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Dialog>
  );
}
