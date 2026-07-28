import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

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
import { useCampaignsList } from "@/features/marketing/campaigns/api/campaigns-hooks";
import { CampaignFormDialog } from "@/features/marketing/campaigns/components/campaign-form-dialog";
import { CampaignStatusBadge } from "@/features/marketing/campaigns/components/campaign-status-badge";
import {
  type CampaignStatus,
  campaignChannelLabels,
  campaignStatusLabels,
  campaignStatusValues,
} from "@/features/marketing/campaigns/schemas/campaign-schemas";

const PAGE_SIZE = 20;

export function CampaignsListPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<CampaignStatus | "all">("all");
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useCampaignsList({
    status: status === "all" ? undefined : status,
    skip,
    limit: PAGE_SIZE,
  });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Campaigns</h1>
          <p className="mt-1 text-muted-foreground">
            Plan and track marketing campaigns across every channel.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Campaign
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value as CampaignStatus | "all");
              setSkip(0);
            }}
          >
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {campaignStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {campaignStatusLabels[s]}
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
              Failed to load campaigns. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No campaigns found. Create your first campaign to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Channel</TableHead>
                  <TableHead>Start date</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((campaign) => (
                  <TableRow
                    key={campaign.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/marketing/campaigns/${campaign.id}`)}
                  >
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {campaign.campaign_code}
                    </TableCell>
                    <TableCell className="font-medium">{campaign.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {campaignChannelLabels[campaign.channel]}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(campaign.start_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <CampaignStatusBadge status={campaign.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} campaigns)
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

      <CampaignFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
