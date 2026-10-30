import { useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import { DuplicatesPanel } from "@/features/storage-manager/components/duplicates-panel";
import { FilesPanel } from "@/features/storage-manager/components/files-panel";
import { LogPanel } from "@/features/storage-manager/components/log-panel";
import { OverviewPanel } from "@/features/storage-manager/components/overview-panel";
import { ServerPanel } from "@/features/storage-manager/components/server-panel";
import { TrashPanel } from "@/features/storage-manager/components/trash-panel";

export function StorageManagerPage() {
  const { data: me } = useMyRoles();
  // Deleting, restoring, purging and the server inspector are for platform superusers; the server enforces it too.
  const isSuperuser = me?.is_superuser ?? false;
  const [tab, setTab] = useState("overview");
  const [filesKey, setFilesKey] = useState(0);
  const [initialStatus, setInitialStatus] = useState<string | undefined>(undefined);

  const showFiles = (status: string) => {
    setInitialStatus(status);
    setFilesKey((key) => key + 1);
    setTab("files");
  };

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Storage Manager</h1>
        <p className="mt-1 text-muted-foreground">
          See every file ERPX stores, check whether it is still needed, and move unused files to Trash.
          {!isSuperuser && " You can look at your organization's files; only a platform administrator can delete them."}
        </p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="h-auto flex-wrap justify-start">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="files">Files</TabsTrigger>
          <TabsTrigger value="duplicates">Duplicates</TabsTrigger>
          <TabsTrigger value="trash">Trash</TabsTrigger>
          <TabsTrigger value="log">Deletion log</TabsTrigger>
          {isSuperuser && <TabsTrigger value="server">Server</TabsTrigger>}
        </TabsList>

        <TabsContent value="overview">
          <OverviewPanel onShow={showFiles} />
        </TabsContent>
        <TabsContent value="files">
          <FilesPanel key={filesKey} canDelete={isSuperuser} initialStatus={initialStatus} />
        </TabsContent>
        <TabsContent value="duplicates">
          <DuplicatesPanel active={tab === "duplicates"} />
        </TabsContent>
        <TabsContent value="trash">
          <TrashPanel canDelete={isSuperuser} />
        </TabsContent>
        <TabsContent value="log">
          <LogPanel />
        </TabsContent>
        {isSuperuser && (
          <TabsContent value="server">
            <ServerPanel active={tab === "server"} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
