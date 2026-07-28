import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCouponsList } from "@/features/marketing/coupons/api/coupons-hooks";
import { CouponFormDialog } from "@/features/marketing/coupons/components/coupon-form-dialog";
import { couponDiscountTypeLabels } from "@/features/marketing/coupons/schemas/coupon-schemas";

const PAGE_SIZE = 20;

export function CouponsListPage() {
  const navigate = useNavigate();
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useCouponsList({ skip, limit: PAGE_SIZE });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Coupons</h1>
          <p className="mt-1 text-muted-foreground">
            Manage discount coupons and track their redemptions.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Coupon
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load coupons. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No coupons found. Create your first coupon to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Discount</TableHead>
                  <TableHead>Valid until</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((coupon) => (
                  <TableRow
                    key={coupon.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/marketing/coupons/${coupon.id}`)}
                  >
                    <TableCell className="font-mono text-xs text-muted-foreground">{coupon.code}</TableCell>
                    <TableCell className="font-medium">
                      {coupon.discount_type === "percentage"
                        ? `${coupon.discount_value}%`
                        : coupon.discount_value.toLocaleString()}{" "}
                      <span className="text-xs text-muted-foreground">
                        ({couponDiscountTypeLabels[coupon.discount_type]})
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(coupon.valid_until).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant={coupon.is_active ? "success" : "secondary"}>
                        {coupon.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} coupons)
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

      <CouponFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
