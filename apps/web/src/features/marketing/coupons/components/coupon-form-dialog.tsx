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
import { useCampaignsList } from "@/features/marketing/campaigns/api/campaigns-hooks";
import { useCreateCoupon } from "@/features/marketing/coupons/api/coupons-hooks";
import {
  type CouponFormValues,
  couponDiscountTypeLabels,
  couponDiscountTypeValues,
  couponFormSchema,
} from "@/features/marketing/coupons/schemas/coupon-schemas";

interface CouponFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const emptyValues: CouponFormValues = {
  code: "",
  campaignId: "",
  description: "",
  discountType: "percentage",
  discountValue: 0,
  maxDiscountAmount: undefined,
  minOrderAmount: 0,
  usageLimitTotal: undefined,
  usageLimitPerCustomer: 1,
  validFrom: "",
  validUntil: "",
};

export function CouponFormDialog({ open, onOpenChange }: CouponFormDialogProps) {
  const createCoupon = useCreateCoupon();
  const { data: campaigns } = useCampaignsList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CouponFormValues>({
    resolver: zodResolver(couponFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: CouponFormValues) => {
    createCoupon.mutate(
      {
        code: values.code,
        campaign_id: values.campaignId || undefined,
        description: values.description || undefined,
        discount_type: values.discountType,
        discount_value: values.discountValue,
        max_discount_amount: values.maxDiscountAmount,
        min_order_amount: values.minOrderAmount,
        usage_limit_total: values.usageLimitTotal,
        usage_limit_per_customer: values.usageLimitPerCustomer,
        valid_from: values.validFrom,
        valid_until: values.validUntil,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New coupon</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="code">Code</Label>
              <Input id="code" {...register("code")} />
              {errors.code && <p className="text-sm text-destructive">{errors.code.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="campaignId">Campaign</Label>
              <Controller
                control={control}
                name="campaignId"
                render={({ field }) => (
                  <Select value={field.value || undefined} onValueChange={field.onChange}>
                    <SelectTrigger id="campaignId">
                      <SelectValue placeholder="Select campaign" />
                    </SelectTrigger>
                    <SelectContent>
                      {campaigns?.items.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" rows={2} {...register("description")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="discountType">Discount type</Label>
              <Controller
                control={control}
                name="discountType"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="discountType">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {couponDiscountTypeValues.map((t) => (
                        <SelectItem key={t} value={t}>
                          {couponDiscountTypeLabels[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="discountValue">Discount value</Label>
              <Input id="discountValue" type="number" step="0.01" {...register("discountValue")} />
              {errors.discountValue && (
                <p className="text-sm text-destructive">{errors.discountValue.message}</p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="maxDiscountAmount">Max discount amount</Label>
              <Input id="maxDiscountAmount" type="number" step="0.01" {...register("maxDiscountAmount")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="minOrderAmount">Min order amount</Label>
              <Input id="minOrderAmount" type="number" step="0.01" {...register("minOrderAmount")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="usageLimitTotal">Usage limit (total)</Label>
              <Input id="usageLimitTotal" type="number" {...register("usageLimitTotal")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="usageLimitPerCustomer">Usage limit (per customer)</Label>
              <Input id="usageLimitPerCustomer" type="number" {...register("usageLimitPerCustomer")} />
            </div>
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
              {errors.validUntil && (
                <p className="text-sm text-destructive">{errors.validUntil.message}</p>
              )}
            </div>
          </div>

          {createCoupon.isError && (
            <p className="text-sm text-destructive">
              {(createCoupon.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createCoupon.isPending}>
              {createCoupon.isPending ? "Saving..." : "Create coupon"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
