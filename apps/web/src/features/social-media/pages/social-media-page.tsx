import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CommentsTab } from "@/features/social-media/components/comments-tab";
import { MessagesTab } from "@/features/social-media/components/messages-tab";
import { AnalyticsTab } from "@/features/social-media/components/analytics-tab";
import { ReportsTab } from "@/features/social-media/components/reports-tab";
import { LeadsTab } from "@/features/social-media/components/leads-tab";
import { OverviewTab } from "@/features/social-media/components/overview-tab";
import { CalendarTab } from "@/features/social-media/components/calendar-tab";
import { GridPreview } from "@/features/social-media/components/grid-preview";
import { LibraryTab } from "@/features/social-media/components/library-tab";
import { PostsTab } from "@/features/social-media/components/posts-tab";
import { QueueTab } from "@/features/social-media/components/queue-tab";
import { ResearchTab } from "@/features/social-media/components/research-tab";
import { SettingsTab } from "@/features/social-media/components/settings-tab";
import { StrategyTab } from "@/features/social-media/components/strategy-tab";
import { StudioTab } from "@/features/social-media/components/studio-tab";

const TAB = "text-foreground/75 data-[state=active]:text-foreground";

const TABS = ["overview", "studio", "research", "posts", "calendar", "queue", "comments", "messages", "leads", "analytics", "reports", "library", "grid", "strategy", "settings"] as const;

const TAB_LABEL: Record<string, string> = {
  overview: "Overview",
  studio: "Studio",
  research: "Research",
  posts: "Posts",
  calendar: "Calendar",
  queue: "Publishing queue",
  comments: "Comments",
  messages: "Direct messages",
  leads: "Campaigns and leads",
  analytics: "Analytics",
  reports: "Reports and experiments",
  library: "Image library",
  grid: "Profile grid",
  strategy: "Strategy",
  settings: "Settings and integrations",
};

export function SocialMediaPage() {
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<string[]>([]);
  const requested = params.get("tab") ?? "overview";
  const tab = (TABS as readonly string[]).includes(requested) ? requested : "overview";

  function openTab(next: string, status?: string) {
    const nextParams = new URLSearchParams();
    nextParams.set("tab", next);
    if (status) nextParams.set("status", status);
    setParams(nextParams);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Social Media</h1>
        <p className="text-sm text-muted-foreground">
          Plan, review and approve Instagram content. Nothing is published without an approval, and replies to comments and messages are only ever sent by a person.
        </p>
      </div>
      <Tabs value={tab} onValueChange={(value) => openTab(value)} className="space-y-6">
        <div className="max-w-full overflow-x-auto">
          <TabsList>
            <TabsTrigger value="overview" className={TAB}>Overview</TabsTrigger>
            <TabsTrigger value="studio" className={TAB}>Studio</TabsTrigger>
            <TabsTrigger value="research" className={TAB}>Research</TabsTrigger>
            <TabsTrigger value="posts" className={TAB}>Posts</TabsTrigger>
            <TabsTrigger value="calendar" className={TAB}>Calendar</TabsTrigger>
            <TabsTrigger value="queue" className={TAB}>Queue</TabsTrigger>
            <TabsTrigger value="comments" className={TAB}>Comments</TabsTrigger>
            <TabsTrigger value="messages" className={TAB}>Messages</TabsTrigger>
            <TabsTrigger value="leads" className={TAB}>Campaigns &amp; Leads</TabsTrigger>
            <TabsTrigger value="analytics" className={TAB}>Analytics</TabsTrigger>
            <TabsTrigger value="reports" className={TAB}>Reports</TabsTrigger>
            <TabsTrigger value="library" className={TAB}>Library</TabsTrigger>
            <TabsTrigger value="grid" className={TAB}>Grid</TabsTrigger>
            <TabsTrigger value="strategy" className={TAB}>Strategy</TabsTrigger>
            <TabsTrigger value="settings" className={TAB}>Settings &amp; Integrations</TabsTrigger>
          </TabsList>
        </div>
        <h2 className="sr-only">{TAB_LABEL[tab]}</h2>
        <TabsContent value="overview">
          <OverviewTab onOpenTab={openTab} />
        </TabsContent>
        <TabsContent value="studio">
          <StudioTab selected={selected} onSelectedChange={setSelected} onOpenPosts={() => openTab("posts", "draft")} />
        </TabsContent>
        <TabsContent value="research">
          <ResearchTab
            onDraftFrom={(id) => {
              setSelected([id]);
              openTab("studio");
            }}
          />
        </TabsContent>
        <TabsContent value="posts">
          <PostsTab key={params.get("status") ?? ""} initialStatus={params.get("status") ?? ""} />
        </TabsContent>
        <TabsContent value="calendar">
          <CalendarTab />
        </TabsContent>
        <TabsContent value="queue">
          <QueueTab />
        </TabsContent>
        <TabsContent value="comments">
          <CommentsTab />
        </TabsContent>
        <TabsContent value="messages">
          <MessagesTab />
        </TabsContent>
        <TabsContent value="leads">
          <LeadsTab />
        </TabsContent>
        <TabsContent value="analytics">
          <AnalyticsTab />
        </TabsContent>
        <TabsContent value="reports">
          <ReportsTab />
        </TabsContent>
        <TabsContent value="library">
          <LibraryTab />
        </TabsContent>
        <TabsContent value="grid">
          <Card>
            <CardHeader>
              <CardTitle>Profile grid preview</CardTitle>
              <CardDescription>The next nine designed posts as they will sit on the profile, and what makes them look repetitive, dense or inconsistent.</CardDescription>
            </CardHeader>
            <CardContent>
              <GridPreview />
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="strategy">
          <StrategyTab />
        </TabsContent>
        <TabsContent value="settings">
          <SettingsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
