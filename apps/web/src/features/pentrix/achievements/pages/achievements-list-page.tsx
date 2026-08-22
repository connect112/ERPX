import { zodResolver } from "@hookform/resolvers/zod";
import { Trophy, Plus } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { useAchievements, useCreateAchievement } from "@/features/pentrix/achievements/api/achievements-hooks";
import {
  type AchievementFormValues,
  achievementCriteriaTypeLabels,
  achievementCriteriaTypeValues,
  achievementFormSchema,
} from "@/features/pentrix/achievements/schemas/achievement-schemas";

export function AchievementsListPage() {
  const { data: achievements, isLoading, isError } = useAchievements();
  const createAchievement = useCreateAchievement();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AchievementFormValues>({
    resolver: zodResolver(achievementFormSchema),
    defaultValues: { name: "", description: "", criteriaType: "challenges_solved", criteriaValue: "5" },
  });

  const onSubmit = (values: AchievementFormValues) => {
    createAchievement.mutate(
      {
        name: values.name,
        description: values.description || undefined,
        criteria_type: values.criteriaType,
        criteria_value: Number(values.criteriaValue),
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
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Achievements</h1>
          <p className="mt-1 text-muted-foreground">
            Automatically awarded to students when they meet a criteria threshold.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Achievement
        </Button>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-6 sm:grid-cols-2 lg:grid-cols-3">
          {isLoading && <Skeleton className="h-24 w-full sm:col-span-2 lg:col-span-3" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive sm:col-span-2 lg:col-span-3">
              Failed to load achievements.
            </p>
          )}
          {!isLoading && !isError && (achievements?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground sm:col-span-2 lg:col-span-3">
              No achievements yet. Create one to start recognizing students.
            </p>
          )}
          {achievements?.map((achievement) => (
            <div key={achievement.id} className="flex items-start gap-3 rounded-md border p-3">
              <Trophy className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <div>
                <p className="text-sm font-medium">{achievement.name}</p>
                {achievement.description && (
                  <p className="mt-1 text-xs text-muted-foreground">{achievement.description}</p>
                )}
                <Badge variant="outline" className="mt-2">
                  {achievementCriteriaTypeLabels[achievement.criteria_type]} ≥{" "}
                  {achievement.criteria_value}
                </Badge>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New achievement</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name" required>Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={3} {...register("description")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="criteriaType" required>Criteria</Label>
                <Controller
                  control={control}
                  name="criteriaType"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="criteriaType">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {achievementCriteriaTypeValues.map((c) => (
                          <SelectItem key={c} value={c}>
                            {achievementCriteriaTypeLabels[c]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="criteriaValue" required>Threshold</Label>
                <Input id="criteriaValue" type="number" {...register("criteriaValue")} />
                {errors.criteriaValue && (
                  <p className="text-sm text-destructive">{errors.criteriaValue.message}</p>
                )}
              </div>
            </div>
            {createAchievement.isError && (
              <p className="text-sm text-destructive">
                {(createAchievement.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createAchievement.isPending}>
                {createAchievement.isPending ? "Saving..." : "Create achievement"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
