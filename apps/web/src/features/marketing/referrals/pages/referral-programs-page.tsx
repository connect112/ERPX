import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCreateReferralProgram, useReferralPrograms } from "@/features/marketing/referrals/api/referrals-hooks";
import {
  type ReferralProgramFormValues,
  referralProgramFormSchema,
} from "@/features/marketing/referrals/schemas/referral-schemas";

export function ReferralProgramsPage() {
  const { data: programs, isLoading, isError } = useReferralPrograms();
  const createProgram = useCreateReferralProgram();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ReferralProgramFormValues>({
    resolver: zodResolver(referralProgramFormSchema),
    defaultValues: { name: "", code: "", referrerRewardAmount: 0, refereeDiscountAmount: 0 },
  });

  const onSubmit = (values: ReferralProgramFormValues) => {
    createProgram.mutate(
      {
        name: values.name,
        code: values.code,
        referrer_reward_amount: values.referrerRewardAmount,
        referee_discount_amount: values.refereeDiscountAmount,
        max_referrals_per_referrer: values.maxReferralsPerReferrer,
        valid_from: values.validFrom,
        valid_until: values.validUntil || undefined,
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
          <h1 className="text-2xl font-semibold tracking-tight">Referral Programs</h1>
          <p className="mt-1 text-muted-foreground">
            Configure referral rewards and eligibility rules.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New program
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All programs</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && <p className="text-sm text-destructive">Failed to load referral programs.</p>}
          {!isLoading && !isError && (programs?.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No referral programs yet.</p>
          )}
          {!isLoading && !isError && (programs?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Referrer reward</TableHead>
                  <TableHead>Referee discount</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {programs?.map((program) => (
                  <TableRow key={program.id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">{program.code}</TableCell>
                    <TableCell className="font-medium">{program.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {program.referrer_reward_amount.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {program.referee_discount_amount.toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant={program.is_active ? "success" : "secondary"}>
                        {program.is_active ? "Active" : "Inactive"}
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
            <DialogTitle>New referral program</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" {...register("name")} />
                {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="code">Code</Label>
                <Input id="code" {...register("code")} />
                {errors.code && <p className="text-sm text-destructive">{errors.code.message}</p>}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="referrerRewardAmount">Referrer reward</Label>
                <Input id="referrerRewardAmount" type="number" step="0.01" {...register("referrerRewardAmount")} />
                {errors.referrerRewardAmount && (
                  <p className="text-sm text-destructive">{errors.referrerRewardAmount.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="refereeDiscountAmount">Referee discount</Label>
                <Input id="refereeDiscountAmount" type="number" step="0.01" {...register("refereeDiscountAmount")} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="maxReferralsPerReferrer">Max referrals per referrer</Label>
              <Input id="maxReferralsPerReferrer" type="number" {...register("maxReferralsPerReferrer")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="validFrom">Valid from</Label>
                <Input id="validFrom" type="date" {...register("validFrom")} />
                {errors.validFrom && (
                  <p className="text-sm text-destructive">{errors.validFrom.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="validUntil">Valid until</Label>
                <Input id="validUntil" type="date" {...register("validUntil")} />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createProgram.isPending}>
                {createProgram.isPending ? "Saving..." : "Create program"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
