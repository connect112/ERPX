import { ArrowLeft, Pencil } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCampaign,
  useCampaignPerformance,
  useChangeCampaignStatus,
} from "@/features/marketing/campaigns/api/campaigns-hooks";
import { CampaignFormDialog } from "@/features/marketing/campaigns/components/campaign-form-dialog";
import { CampaignStatusBadge } from "@/features/marketing/campaigns/components/campaign-status-badge";
import {
  type CampaignStatus,
  campaignChannelLabels,
  campaignStatusLabels,
  campaignStatusValues,
} from "@/features/marketing/campaigns/schemas/campaign-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}

export function CampaignDetailPage() {
  const { campaignId } = useParams<{ campaignId: string }>();
  const navigate = useNavigate();
  const { data: campaign, isLoading } = useCampaign(campaignId);
  const { data: performance, isLoading: performanceLoading } = useCampaignPerformance(campaignId);
  const changeStatus = useChangeCampaignStatus(campaignId ?? "");
  const [editOpen, setEditOpen] = useState(false);

  if (isLoading || !campaign) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/marketing/campaigns")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{campaign.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{campaign.campaign_code}</span>
              <CampaignStatusBadge status={campaign.status} />
            </div>
          </div>
        </div>
        <Button variant="outline" onClick={() => setEditOpen(true)}>
          <Pencil className="h-4 w-4" />
          Edit
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Campaign details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Channel" value={campaignChannelLabels[campaign.channel]} />
              <DetailRow label="Start date" value={new Date(campaign.start_date).toLocaleDateString()} />
              <DetailRow
                label="End date"
                value={campaign.end_date ? new Date(campaign.end_date).toLocaleDateString() : "—"}
              />
              <DetailRow
                label="Budget"
                value={campaign.budget_amount != null ? campaign.budget_amount.toLocaleString() : "—"}
              />
              <DetailRow label="Actual spend" value={campaign.actual_spend.toLocaleString()} />
              <DetailRow label="Target audience" value={campaign.target_audience || "—"} />
              <DetailRow label="Goal" value={campaign.goal || "—"} />
              {campaign.notes && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Notes</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{campaign.notes}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Change status</CardTitle>
            </CardHeader>
            <CardContent>
              <Select
                value={campaign.status}
                onValueChange={(value) => changeStatus.mutate(value as CampaignStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {campaignStatusValues.map((s) => (
                    <SelectItem key={s} value={s}>
                      {campaignStatusLabels[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Performance</CardTitle>
        </CardHeader>
        <CardContent>
          {performanceLoading && <Skeleton className="h-24 w-full" />}
          {performance && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatTile label="Leads generated" value={performance.leads_generated} />
              <StatTile label="Leads converted" value={performance.leads_converted} />
              <StatTile label="Conversion rate" value={`${performance.conversion_rate_percent.toFixed(1)}%`} />
              <StatTile label="Landing pages" value={performance.landing_pages_count} />
              <StatTile label="Landing page views" value={performance.landing_page_views} />
              <StatTile label="Coupons" value={performance.coupons_count} />
              <StatTile label="Coupon redemptions" value={performance.coupon_redemptions} />
              <StatTile
                label="Cost per lead"
                value={performance.cost_per_lead != null ? performance.cost_per_lead.toFixed(2) : "—"}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <CampaignFormDialog open={editOpen} onOpenChange={setEditOpen} campaign={campaign} />
    </div>
  );
}
