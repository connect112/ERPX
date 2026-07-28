import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useOrgSettings, useUpsertOrgSetting } from "@/features/settings/api/org-settings-hooks";

export function OrgSettingsPanel({ organizationId }: { organizationId: string }) {
  const { data: settings, isLoading, isError } = useOrgSettings(organizationId);
  const upsertSetting = useUpsertOrgSetting(organizationId);

  const [formOpen, setFormOpen] = useState(false);
  const [editingKey, setEditingKey] = useState("");
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  const openNew = () => {
    setEditingKey("");
    setKey("");
    setValue("");
    setFormOpen(true);
  };

  const openEdit = (settingKey: string, settingValue: string) => {
    setEditingKey(settingKey);
    setKey(settingKey);
    setValue(settingValue);
    setFormOpen(true);
  };

  const handleSubmit = () => {
    if (!key.trim()) return;
    upsertSetting.mutate({ key, value }, { onSuccess: () => setFormOpen(false) });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Settings</CardTitle>
        <Button size="sm" onClick={openNew}>
          <Plus className="h-4 w-4" />
          New setting
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-32 w-full" />}
        {isError && <p className="text-sm text-destructive">Failed to load settings.</p>}
        {!isLoading && !isError && (settings?.length ?? 0) === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">No settings configured.</p>
        )}
        {!isLoading && !isError && (settings?.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Key</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {settings?.map((setting) => (
                <TableRow key={setting.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{setting.key}</TableCell>
                  <TableCell className="font-medium">{setting.value}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(setting.updated_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEdit(setting.key, setting.value)}
                    >
                      Edit
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingKey ? `Edit ${editingKey}` : "New setting"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="key">Key</Label>
              <Input
                id="key"
                disabled={!!editingKey}
                value={key}
                onChange={(e) => setKey(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="value">Value</Label>
              <Input id="value" value={value} onChange={(e) => setValue(e.target.value)} />
            </div>
          </div>

          {upsertSetting.isError && (
            <p className="text-sm text-destructive">
              {(upsertSetting.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={!key.trim() || upsertSetting.isPending}>
              {upsertSetting.isPending ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
