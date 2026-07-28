import { ArrowLeft } from "lucide-react";
import { type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useCoupon,
  useCouponRedemptions,
  useCouponUsageSummary,
} from "@/features/marketing/coupons/api/coupons-hooks";
import { couponDiscountTypeLabels } from "@/features/marketing/coupons/schemas/coupon-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function CouponDetailPage() {
  const { couponId } = useParams<{ couponId: string }>();
  const navigate = useNavigate();
  const { data: coupon, isLoading } = useCoupon(couponId);
  const { data: summary } = useCouponUsageSummary(couponId);
  const { data: redemptions, isLoading: redemptionsLoading } = useCouponRedemptions(couponId, { limit: 30 });

  if (isLoading || !coupon) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/marketing/coupons")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{coupon.code}</h1>
          <div className="mt-1">
            <Badge variant={coupon.is_active ? "success" : "secondary"}>
              {coupon.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Coupon details</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Discount type" value={couponDiscountTypeLabels[coupon.discount_type]} />
            <DetailRow label="Discount value" value={coupon.discount_value} />
            <DetailRow
              label="Max discount amount"
              value={coupon.max_discount_amount != null ? coupon.max_discount_amount.toLocaleString() : "—"}
            />
            <DetailRow label="Min order amount" value={coupon.min_order_amount.toLocaleString()} />
            <DetailRow label="Usage limit (total)" value={coupon.usage_limit_total ?? "Unlimited"} />
            <DetailRow label="Usage limit (per customer)" value={coupon.usage_limit_per_customer} />
            <DetailRow label="Valid from" value={new Date(coupon.valid_from).toLocaleDateString()} />
            <DetailRow label="Valid until" value={new Date(coupon.valid_until).toLocaleDateString()} />
            {coupon.description && (
              <div className="pt-3">
                <p className="text-sm text-muted-foreground">Description</p>
                <p className="mt-1 whitespace-pre-wrap text-sm">{coupon.description}</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Usage summary</CardTitle>
          </CardHeader>
          <CardContent>
            {summary ? (
              <>
                <DetailRow label="Redemptions" value={summary.redemption_count} />
                <DetailRow label="Total discount given" value={summary.total_discount_given.toLocaleString()} />
              </>
            ) : (
              <Skeleton className="h-16 w-full" />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Redemptions</CardTitle>
        </CardHeader>
        <CardContent>
          {redemptionsLoading && <Skeleton className="h-24 w-full" />}
          {!redemptionsLoading && (redemptions?.items.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No redemptions yet.</p>
          )}
          {!redemptionsLoading && (redemptions?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Redeemed by</TableHead>
                  <TableHead>Applied to</TableHead>
                  <TableHead>Order amount</TableHead>
                  <TableHead>Discount applied</TableHead>
                  <TableHead>Redeemed at</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {redemptions?.items.map((redemption) => (
                  <TableRow key={redemption.id}>
                    <TableCell className="font-medium">{redemption.redeemed_by_reference}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {redemption.redeemed_against_type || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {redemption.order_amount.toLocaleString()}
                    </TableCell>
                    <TableCell className="font-medium">
                      {redemption.discount_amount_applied.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(redemption.redeemed_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
