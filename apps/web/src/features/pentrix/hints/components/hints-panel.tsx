import { zodResolver } from "@hookform/resolvers/zod";
import { Lock, Plus, Unlock } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

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
import { Textarea } from "@/components/ui/textarea";
import { useStudentsList } from "@/features/students/api/students-hooks";
import {
  useCreateHint,
  useHintsForStudent,
  useUnlockHint,
} from "@/features/pentrix/hints/api/hints-hooks";
import { type HintFormValues, hintFormSchema } from "@/features/pentrix/hints/schemas/hint-schemas";

export function HintsPanel({ challengeId }: { challengeId: string }) {
  const { data: students } = useStudentsList({ limit: 200 });
  const [studentId, setStudentId] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [revealed, setRevealed] = useState<Record<string, string>>({});

  const { data: hints, isLoading } = useHintsForStudent(challengeId, studentId);
  const createHint = useCreateHint(challengeId);
  const unlockHint = useUnlockHint(challengeId, studentId);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<HintFormValues>({
    resolver: zodResolver(hintFormSchema),
    defaultValues: { hintText: "", pointCost: "10", orderIndex: String((hints?.length ?? 0) + 1) },
  });

  const onSubmit = (values: HintFormValues) => {
    createHint.mutate(
      { hint_text: values.hintText, point_cost: Number(values.pointCost), order_index: Number(values.orderIndex) },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset();
        },
      }
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Hints</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Add hint
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <Select value={studentId || undefined} onValueChange={setStudentId}>
          <SelectTrigger className="sm:w-56">
            <SelectValue placeholder="View unlock status for..." />
          </SelectTrigger>
          <SelectContent>
            {students?.items.map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {s.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {!studentId && (
          <p className="text-sm text-muted-foreground">
            Select a student to see which hints they've unlocked.
          </p>
        )}

        {studentId && isLoading && <Skeleton className="h-16 w-full" />}
        {studentId && !isLoading && (hints?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No hints created yet.</p>
        )}
        {studentId &&
          hints?.map((hint) => (
            <div key={hint.id} className="rounded-md border p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {hint.unlocked ? (
                    <Unlock className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <Lock className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="text-sm font-medium">Hint {hint.order_index}</span>
                  <span className="text-xs text-muted-foreground">{hint.point_cost} pts</span>
                </div>
                {!hint.unlocked && (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={unlockHint.isPending}
                    onClick={() =>
                      unlockHint.mutate(hint.id, {
                        onSuccess: (data) =>
                          setRevealed((prev) => ({ ...prev, [hint.id]: data.hint_text })),
                      })
                    }
                  >
                    Unlock
                  </Button>
                )}
              </div>
              {hint.unlocked && (
                <p className="mt-2 text-sm text-muted-foreground">
                  {revealed[hint.id] ?? "Unlocked previously — text shown at time of unlock only."}
                </p>
              )}
            </div>
          ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add hint</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="hintText" required>Hint text</Label>
              <Textarea id="hintText" rows={3} {...register("hintText")} />
              {errors.hintText && (
                <p className="text-sm text-destructive">{errors.hintText.message}</p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pointCost" required>Point cost</Label>
                <Input id="pointCost" type="number" {...register("pointCost")} />
                {errors.pointCost && (
                  <p className="text-sm text-destructive">{errors.pointCost.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="orderIndex" required>Order</Label>
                <Input id="orderIndex" type="number" {...register("orderIndex")} />
                {errors.orderIndex && (
                  <p className="text-sm text-destructive">{errors.orderIndex.message}</p>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createHint.isPending}>
                {createHint.isPending ? "Saving..." : "Add hint"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
