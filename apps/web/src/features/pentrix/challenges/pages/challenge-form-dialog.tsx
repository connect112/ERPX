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
import { Textarea } from "@/components/ui/textarea";
import { useLabs } from "@/features/pentrix/labs/api/labs-hooks";
import { labDifficultyLabels, labDifficultyValues } from "@/features/pentrix/labs/schemas/lab-schemas";
import type { ChallengePublic } from "@/features/pentrix/challenges/api/challenges-api";
import { useCreateChallenge, useUpdateChallenge } from "@/features/pentrix/challenges/api/challenges-hooks";
import {
  type ChallengeFormValues,
  challengeFormSchema,
} from "@/features/pentrix/challenges/schemas/challenge-schemas";

interface ChallengeFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  challenge?: ChallengePublic;
}

const emptyValues: ChallengeFormValues = {
  labId: "",
  title: "",
  description: "",
  category: "",
  difficulty: "easy",
  points: "100",
};

export function ChallengeFormDialog({ open, onOpenChange, challenge }: ChallengeFormDialogProps) {
  const isEditing = !!challenge;
  const { data: labs } = useLabs();
  const createChallenge = useCreateChallenge();
  const updateChallenge = useUpdateChallenge(challenge?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ChallengeFormValues>({
    resolver: zodResolver(challengeFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        challenge
          ? {
              labId: challenge.lab_id ?? "",
              title: challenge.title,
              description: challenge.description,
              category: challenge.category,
              difficulty: challenge.difficulty,
              points: String(challenge.points),
            }
          : emptyValues
      );
    }
  }, [open, challenge, reset]);

  const onSubmit = (values: ChallengeFormValues) => {
    const shared = {
      title: values.title,
      description: values.description,
      category: values.category,
      difficulty: values.difficulty,
      points: Number(values.points),
    };

    if (isEditing) {
      updateChallenge.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createChallenge.mutate(
        { ...shared, lab_id: values.labId || undefined },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  const mutation = isEditing ? updateChallenge : createChallenge;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit challenge" : "New challenge"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" {...register("title")} />
            {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={3} {...register("description")} />
            {errors.description && (
              <p className="text-sm text-destructive">{errors.description.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="category">Category</Label>
              <Input id="category" placeholder="e.g. Web, Crypto, Forensics" {...register("category")} />
              {errors.category && (
                <p className="text-sm text-destructive">{errors.category.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="difficulty">Difficulty</Label>
              <Controller
                control={control}
                name="difficulty"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="difficulty">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {labDifficultyValues.map((d) => (
                        <SelectItem key={d} value={d}>
                          {labDifficultyLabels[d]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          {!isEditing && (
            <div className="space-y-2">
              <Label htmlFor="labId">Linked lab (optional)</Label>
              <Controller
                control={control}
                name="labId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="labId">
                      <SelectValue placeholder="Standalone (no lab)" />
                    </SelectTrigger>
                    <SelectContent>
                      {labs?.map((l) => (
                        <SelectItem key={l.id} value={l.id}>
                          {l.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="points">Points</Label>
            <Input id="points" type="number" {...register("points")} />
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create challenge"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
