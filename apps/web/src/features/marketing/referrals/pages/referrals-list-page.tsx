import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { useReferralPrograms, useReferralsList, useRewardReferral, useRejectReferral } from "@/features/marketing/referrals/api/referrals-hooks";
import { ConvertReferralDialog } from "@/features/marketing/referrals/components/convert-referral-dialog";
import { ReferralFormDialog } from "@/features/marketing/referrals/components/referral-form-dialog";
import { ReferralStatusBadge } from "@/features/marketing/referrals/components/referral-status-badge";
import {
  type ReferralStatus,
  referralStatusLabels,
  referralStatusValues,
} from "@/features/marketing/referrals/schemas/referral-schemas";

const PAGE_SIZE = 20;

export function ReferralsListPage() {
  const [status, setStatus] = useState<ReferralStatus | "all">("all");
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [convertTarget, setConvertTarget] = useState<string | null>(null);

  const { data, isLoading, isError } = useReferralsList({
    status: status === "all" ? undefined : status,
    skip,
    limit: PAGE_SIZE,
  });
  const { data: programs } = useReferralPrograms();
  const rewardReferral = useRewardReferral();
  const rejectReferral = useRejectReferral();

  const programName = (id: string) => programs?.find((p) => p.id === id)?.name ?? id;

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Referrals</h1>
          <p className="mt-1 text-muted-foreground">
            Track referrals from submission through conversion and reward.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New referral
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value as ReferralStatus | "all");
              setSkip(0);
            }}
          >
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {referralStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {referralStatusLabels[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load referrals. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No referrals found for this filter.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Referee</TableHead>
                  <TableHead>Program</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((referral) => (
                  <TableRow key={referral.id}>
                    <TableCell className="font-medium">{referral.referee_name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {programName(referral.referral_program_id)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {referral.referee_email || referral.referee_phone || "—"}
                    </TableCell>
                    <TableCell>
                      <ReferralStatusBadge status={referral.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      {referral.status === "pending" && (
                        <div className="flex justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={() => setConvertTarget(referral.id)}>
                            Convert
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => rejectReferral.mutate(referral.id)}
                            disabled={rejectReferral.isPending}
                          >
                            Reject
                          </Button>
                        </div>
                      )}
                      {referral.status === "converted" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => rewardReferral.mutate(referral.id)}
                          disabled={rewardReferral.isPending}
                        >
                          Mark rewarded
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} referrals)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip + PAGE_SIZE >= total}
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <ReferralFormDialog open={formOpen} onOpenChange={setFormOpen} />
      <ConvertReferralDialog
        open={!!convertTarget}
        onOpenChange={(open) => !open && setConvertTarget(null)}
        referralId={convertTarget}
      />
    </div>
  );
}
