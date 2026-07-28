import { zodResolver } from "@hookform/resolvers/zod";
import { Award, Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

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
import { useStudentsList } from "@/features/students/api/students-hooks";
import { useAwardBadge, useBadges, useCreateBadge } from "@/features/lms/badges/api/badges-hooks";
import { type BadgeFormValues, badgeFormSchema } from "@/features/lms/badges/schemas/badge-schemas";

export function BadgesListPage() {
  const { data: badges, isLoading, isError } = useBadges();
  const { data: students } = useStudentsList({ limit: 200 });
  const createBadge = useCreateBadge();
  const awardBadge = useAwardBadge();

  const [formOpen, setFormOpen] = useState(false);
  const [awardOpen, setAwardOpen] = useState(false);
  const [awardStudentId, setAwardStudentId] = useState("");
  const [awardBadgeId, setAwardBadgeId] = useState("");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BadgeFormValues>({ resolver: zodResolver(badgeFormSchema) });

  const onSubmit = (values: BadgeFormValues) => {
    createBadge.mutate(
      { name: values.name, description: values.description || undefined, icon_url: values.iconUrl || undefined },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset();
        },
      }
    );
  };

  const onAward = () => {
    if (!awardStudentId || !awardBadgeId) return;
    awardBadge.mutate(
      { studentId: awardStudentId, badgeId: awardBadgeId },
      {
        onSuccess: () => {
          setAwardOpen(false);
          setAwardStudentId("");
          setAwardBadgeId("");
        },
      }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Badges</h1>
          <p className="mt-1 text-muted-foreground">
            Recognize student achievements with awardable badges.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setAwardOpen(true)}>
            <Award className="h-4 w-4" />
            Award badge
          </Button>
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" />
            New Badge
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-6 sm:grid-cols-2 lg:grid-cols-3">
          {isLoading && <Skeleton className="h-24 w-full sm:col-span-2 lg:col-span-3" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive sm:col-span-2 lg:col-span-3">
              Failed to load badges.
            </p>
          )}
          {!isLoading && !isError && (badges?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground sm:col-span-2 lg:col-span-3">
              No badges yet. Create one to start recognizing students.
            </p>
          )}
          {badges?.map((badge) => (
            <div key={badge.id} className="flex items-start gap-3 rounded-md border p-3">
              <Award className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <div>
                <p className="text-sm font-medium">{badge.name}</p>
                {badge.description && (
                  <p className="mt-1 text-xs text-muted-foreground">{badge.description}</p>
                )}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New badge</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea id="description" rows={3} {...register("description")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="iconUrl">Icon URL</Label>
              <Input id="iconUrl" {...register("iconUrl")} />
            </div>
            {createBadge.isError && (
              <p className="text-sm text-destructive">
                {(createBadge.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createBadge.isPending}>
                {createBadge.isPending ? "Saving..." : "Create badge"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={awardOpen} onOpenChange={setAwardOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Award badge</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="student">Student</Label>
              <Select value={awardStudentId || undefined} onValueChange={setAwardStudentId}>
                <SelectTrigger id="student">
                  <SelectValue placeholder="Select a student" />
                </SelectTrigger>
                <SelectContent>
                  {students?.items.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.full_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="badge">Badge</Label>
              <Select value={awardBadgeId || undefined} onValueChange={setAwardBadgeId}>
                <SelectTrigger id="badge">
                  <SelectValue placeholder="Select a badge" />
                </SelectTrigger>
                <SelectContent>
                  {badges?.map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {awardBadge.isError && (
              <p className="text-sm text-destructive">
                {(awardBadge.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAwardOpen(false)}>
              Cancel
            </Button>
            <Button onClick={onAward} disabled={!awardStudentId || !awardBadgeId || awardBadge.isPending}>
              {awardBadge.isPending ? "Awarding..." : "Award"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
