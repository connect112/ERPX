import { useQuery } from "@tanstack/react-query";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { marketingAnalyticsApi } from "@/features/marketing/analytics/api/analytics-api";

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
}

export function MarketingOverviewPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["marketing", "analytics", "overview"],
    queryFn: () => marketingAnalyticsApi.overview(),
  });

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Marketing Overview</h1>
        <p className="mt-1 text-muted-foreground">
          Org-wide snapshot of campaigns, landing pages, coupons, and referrals.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Campaigns</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Skeleton className="h-16 w-full" />}
          {isError && <p className="text-sm text-destructive">Failed to load marketing overview.</p>}
          {data && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatTile label="Total campaigns" value={data.total_campaigns} />
              <StatTile label="Active campaigns" value={data.active_campaigns} />
              <StatTile label="Leads from campaigns" value={data.total_leads_from_campaigns} />
              <StatTile label="Landing page views" value={data.total_landing_page_views} />
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Coupons</CardTitle>
          </CardHeader>
          <CardContent>
            {data && (
              <div className="grid grid-cols-2 gap-4">
                <StatTile label="Redemptions" value={data.total_coupon_redemptions} />
                <StatTile label="Discount given" value={data.total_coupon_discount_given.toLocaleString()} />
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Referrals</CardTitle>
          </CardHeader>
          <CardContent>
            {data && (
              <div className="grid grid-cols-3 gap-4">
                <StatTile label="Total referrals" value={data.total_referrals} />
                <StatTile label="Converted" value={data.referrals_converted} />
                <StatTile label="Rewarded" value={data.referrals_rewarded} />
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
