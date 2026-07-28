import { ArchiveIcon, ArrowLeft, Pencil, Send } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useArchiveLandingPage,
  useLandingPage,
  useLandingPageStats,
  usePublishLandingPage,
} from "@/features/marketing/landing-pages/api/landing-pages-hooks";
import { LandingPageFormDialog } from "@/features/marketing/landing-pages/components/landing-page-form-dialog";
import { LandingPageStatusBadge } from "@/features/marketing/landing-pages/components/landing-page-status-badge";

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

export function LandingPageDetailPage() {
  const { pageId } = useParams<{ pageId: string }>();
  const navigate = useNavigate();
  const { data: page, isLoading } = useLandingPage(pageId);
  const { data: stats } = useLandingPageStats(pageId);
  const publishPage = usePublishLandingPage(pageId ?? "");
  const archivePage = useArchiveLandingPage(pageId ?? "");
  const [editOpen, setEditOpen] = useState(false);

  if (isLoading || !page) {
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
          <Button variant="ghost" size="icon" onClick={() => navigate("/marketing/landing-pages")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{page.title}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">/{page.slug}</span>
              <LandingPageStatusBadge status={page.status} />
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
          {page.status === "draft" && (
            <Button variant="outline" onClick={() => publishPage.mutate()} disabled={publishPage.isPending}>
              <Send className="h-4 w-4" />
              {publishPage.isPending ? "Publishing..." : "Publish"}
            </Button>
          )}
          {page.status !== "archived" && (
            <Button variant="outline" onClick={() => archivePage.mutate()} disabled={archivePage.isPending}>
              <ArchiveIcon className="h-4 w-4" />
              {archivePage.isPending ? "Archiving..." : "Archive"}
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Page details</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Meta description" value={page.meta_description || "—"} />
            <DetailRow
              label="Published at"
              value={page.published_at ? new Date(page.published_at).toLocaleString() : "—"}
            />
            <div className="pt-3">
              <p className="text-sm text-muted-foreground">Content</p>
              <p className="mt-1 whitespace-pre-wrap text-sm">{page.content}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Stats</CardTitle>
          </CardHeader>
          <CardContent>
            {stats ? (
              <div className="space-y-1">
                <StatTile label="Total views" value={stats.total_views} />
                <StatTile label="Total conversions" value={stats.total_conversions} />
                <StatTile label="Conversion rate" value={`${stats.conversion_rate_percent.toFixed(1)}%`} />
              </div>
            ) : (
              <Skeleton className="h-16 w-full" />
            )}
          </CardContent>
        </Card>
      </div>

      <LandingPageFormDialog open={editOpen} onOpenChange={setEditOpen} page={page} />
    </div>
  );
}
