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
import { useAllReferrals } from "@/features/alumni/api/alumni-hooks";
import { ReferralStatusBadge } from "@/features/alumni/components/referral-status-badge";
import {
  type ReferralStatus,
  referralStatusLabels,
  referralStatusValues,
} from "@/features/alumni/schemas/event-schemas";

const PAGE_SIZE = 20;

export function ReferralsListPage() {
  const [status, setStatus] = useState<ReferralStatus | "all">("all");
  const [skip, setSkip] = useState(0);

  const { data, isLoading, isError } = useAllReferrals({
    status: status === "all" ? undefined : status,
    skip,
    limit: PAGE_SIZE,
  });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Job Referrals</h1>
        <p className="mt-1 text-muted-foreground">
          Referrals posted by alumni for students and fellow graduates. Alumni manage their own
          postings; this view is for oversight.
        </p>
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
            <SelectTrigger className="sm:w-56">
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
              Failed to load job referrals. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No job referrals yet. They appear here once an alumnus posts one.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Posted</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((referral) => (
                  <TableRow key={referral.id}>
                    <TableCell className="font-medium">{referral.title}</TableCell>
                    <TableCell className="text-muted-foreground">{referral.company}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(referral.posted_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <ReferralStatusBadge status={referral.status} />
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
    </div>
  );
}
