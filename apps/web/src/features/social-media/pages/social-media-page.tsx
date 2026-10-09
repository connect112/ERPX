import { useSearchParams } from "react-router-dom";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OverviewTab } from "@/features/social-media/components/overview-tab";
import { PostsTab } from "@/features/social-media/components/posts-tab";
import { SettingsTab } from "@/features/social-media/components/settings-tab";
import { StrategyTab } from "@/features/social-media/components/strategy-tab";

const TABS = ["overview", "posts", "strategy", "settings"] as const;

export function SocialMediaPage() {
  const [params, setParams] = useSearchParams();
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
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="posts">Posts</TabsTrigger>
            <TabsTrigger value="strategy">Strategy</TabsTrigger>
            <TabsTrigger value="settings">Settings &amp; Integrations</TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="overview">
          <OverviewTab onOpenTab={openTab} />
        </TabsContent>
        <TabsContent value="posts">
          <PostsTab key={params.get("status") ?? ""} initialStatus={params.get("status") ?? ""} />
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
