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
import type { CampaignPublic } from "@/features/marketing/campaigns/api/campaigns-api";
import { useCreateCampaign, useUpdateCampaign } from "@/features/marketing/campaigns/api/campaigns-hooks";
import {
  type CampaignFormValues,
  campaignChannelLabels,
  campaignChannelValues,
  campaignFormSchema,
} from "@/features/marketing/campaigns/schemas/campaign-schemas";

interface CampaignFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  campaign?: CampaignPublic;
}

const emptyValues: CampaignFormValues = {
  campaignCode: "",
  name: "",
  channel: "email",
  startDate: "",
  endDate: "",
  budgetAmount: undefined,
  actualSpend: undefined,
  targetAudience: "",
  goal: "",
  notes: "",
};

export function CampaignFormDialog({ open, onOpenChange, campaign }: CampaignFormDialogProps) {
  const isEditing = !!campaign;
  const createCampaign = useCreateCampaign();
  const updateCampaign = useUpdateCampaign(campaign?.id ?? "");

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CampaignFormValues>({
    resolver: zodResolver(campaignFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        campaign
          ? {
              campaignCode: campaign.campaign_code,
              name: campaign.name,
              channel: campaign.channel,
              startDate: campaign.start_date,
              endDate: campaign.end_date ?? "",
              budgetAmount: campaign.budget_amount ?? undefined,
              actualSpend: campaign.actual_spend,
              targetAudience: campaign.target_audience ?? "",
              goal: campaign.goal ?? "",
              notes: campaign.notes ?? "",
            }
          : emptyValues
      );
    }
  }, [open, campaign, reset]);

  const mutation = isEditing ? updateCampaign : createCampaign;

  const onSubmit = (values: CampaignFormValues) => {
    if (isEditing) {
      updateCampaign.mutate(
        {
          name: values.name,
          end_date: values.endDate || undefined,
          budget_amount: values.budgetAmount,
          actual_spend: values.actualSpend,
          target_audience: values.targetAudience || undefined,
          goal: values.goal || undefined,
          notes: values.notes || undefined,
        },
        { onSuccess: () => onOpenChange(false) }
      );
    } else {
      createCampaign.mutate(
        {
          campaign_code: values.campaignCode,
          name: values.name,
          channel: values.channel,
          start_date: values.startDate,
          end_date: values.endDate || undefined,
          budget_amount: values.budgetAmount,
          target_audience: values.targetAudience || undefined,
          goal: values.goal || undefined,
          notes: values.notes || undefined,
        },
        { onSuccess: () => onOpenChange(false) }
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit campaign" : "New campaign"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="campaignCode">Campaign code</Label>
              <Input id="campaignCode" disabled={isEditing} {...register("campaignCode")} />
              {errors.campaignCode && (
                <p className="text-sm text-destructive">{errors.campaignCode.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="channel">Channel</Label>
              <Controller
                control={control}
                name="channel"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange} disabled={isEditing}>
                    <SelectTrigger id="channel">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {campaignChannelValues.map((c) => (
                        <SelectItem key={c} value={c}>
                          {campaignChannelLabels[c]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="startDate">Start date</Label>
              <Input id="startDate" type="date" disabled={isEditing} {...register("startDate")} />
              {errors.startDate && (
                <p className="text-sm text-destructive">{errors.startDate.message}</p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="endDate">End date</Label>
              <Input id="endDate" type="date" {...register("endDate")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="budgetAmount">Budget</Label>
              <Input id="budgetAmount" type="number" step="0.01" {...register("budgetAmount")} />
            </div>
            {isEditing && (
              <div className="space-y-2">
                <Label htmlFor="actualSpend">Actual spend</Label>
                <Input id="actualSpend" type="number" step="0.01" {...register("actualSpend")} />
              </div>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="targetAudience">Target audience</Label>
            <Input id="targetAudience" {...register("targetAudience")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="goal">Goal</Label>
            <Input id="goal" {...register("goal")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
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
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create campaign"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
