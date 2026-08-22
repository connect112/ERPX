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
import {
  useCreateVAPTFinding,
  useUpdateVAPTFinding,
  useVAPTFindings,
  useVAPTFindingsSummary,
} from "@/features/corporate/vapt/api/vapt-hooks";
import { FindingSeverityBadge } from "@/features/corporate/vapt/components/vapt-badges";
import {
  type VAPTFindingFormValues,
  findingSeverityLabels,
  findingSeverityValues,
  findingStatusLabels,
  findingStatusValues,
  vaptFindingFormSchema,
} from "@/features/corporate/vapt/schemas/vapt-schemas";

interface VAPTFindingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  engagementId: string | null;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function VAPTFindingsDialog({ open, onOpenChange, engagementId }: VAPTFindingsDialogProps) {
  const { data: summary } = useVAPTFindingsSummary(engagementId ?? undefined);
  const { data: findings, isLoading } = useVAPTFindings(engagementId ?? undefined);
  const createFinding = useCreateVAPTFinding(engagementId ?? "");
  const updateFinding = useUpdateVAPTFinding();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<VAPTFindingFormValues>({
    resolver: zodResolver(vaptFindingFormSchema),
    defaultValues: {
      title: "",
      severity: "medium",
      cvssScore: undefined,
      description: "",
      recommendation: "",
      reportedDate: todayIso(),
    },
  });

  const onSubmit = (values: VAPTFindingFormValues) => {
    createFinding.mutate(
      {
        title: values.title,
        severity: values.severity,
        cvss_score: values.cvssScore,
        description: values.description,
        recommendation: values.recommendation,
        reported_date: values.reportedDate,
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
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>VAPT findings</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {summary && (
            <div className="grid grid-cols-3 gap-4 text-sm sm:grid-cols-6">
              <div>
                <p className="text-xs text-muted-foreground">Total</p>
                <p className="font-semibold">{summary.total_findings}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Open</p>
                <p className="font-semibold">{summary.open_findings}</p>
              </div>
              {Object.entries(summary.by_severity).map(([severity, count]) => (
                <div key={severity}>
                  <p className="text-xs capitalize text-muted-foreground">{severity}</p>
                  <p className="font-semibold">{count}</p>
                </div>
              ))}
            </div>
          )}
          <div className="flex justify-end">
            <Button size="sm" onClick={() => setFormOpen(true)}>
              <Plus className="h-4 w-4" />
              Add finding
            </Button>
          </div>
          {isLoading && <Skeleton className="h-24 w-full" />}
          {!isLoading && (findings?.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No findings recorded.</p>
          )}
          {!isLoading && (findings?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>CVSS</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {findings?.map((finding) => (
                  <TableRow key={finding.id}>
                    <TableCell className="max-w-[180px] truncate font-medium">{finding.title}</TableCell>
                    <TableCell>
                      <FindingSeverityBadge severity={finding.severity} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">{finding.cvss_score ?? "—"}</TableCell>
                    <TableCell>
                      <Select
                        value={finding.status}
                        onValueChange={(value) =>
                          updateFinding.mutate({
                            findingId: finding.id,
                            payload: { status: value as typeof finding.status },
                          })
                        }
                      >
                        <SelectTrigger className="h-8 w-36">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {findingStatusValues.map((s) => (
                            <SelectItem key={s} value={s}>
                              {findingStatusLabels[s]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
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
            <DialogTitle>Add finding</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title" required>Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="severity" required>Severity</Label>
                <Controller
                  control={control}
                  name="severity"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="severity">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {findingSeverityValues.map((s) => (
                          <SelectItem key={s} value={s}>
                            {findingSeverityLabels[s]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cvssScore">CVSS score</Label>
                <Input id="cvssScore" type="number" step="0.1" min={0} max={10} {...register("cvssScore")} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description" required>Description</Label>
              <Textarea id="description" rows={2} {...register("description")} />
              {errors.description && (
                <p className="text-sm text-destructive">{errors.description.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="recommendation" required>Recommendation</Label>
              <Textarea id="recommendation" rows={2} {...register("recommendation")} />
              {errors.recommendation && (
                <p className="text-sm text-destructive">{errors.recommendation.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="reportedDate" required>Reported date</Label>
              <Input id="reportedDate" type="date" {...register("reportedDate")} />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createFinding.isPending}>
                {createFinding.isPending ? "Saving..." : "Add finding"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Dialog>
  );
}
