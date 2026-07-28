import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { useBroadcastNotification } from "@/features/notifications/api/notifications-hooks";
import type { NotificationType } from "@/features/notifications/api/notifications-api";

const typeOptions: { value: NotificationType; label: string }[] = [
  { value: "info", label: "Info" },
  { value: "success", label: "Success" },
  { value: "warning", label: "Warning" },
  { value: "error", label: "Error" },
  { value: "action_required", label: "Action required" },
];

export function BroadcastPage() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [notificationType, setNotificationType] = useState<NotificationType>("info");
  const [lastResult, setLastResult] = useState<number | null>(null);
  const broadcast = useBroadcastNotification();

  const handleSubmit = () => {
    setLastResult(null);
    broadcast.mutate(
      {
        title,
        body: body || undefined,
        notification_type: notificationType,
        link_url: linkUrl || undefined,
      },
      {
        onSuccess: (result) => {
          setLastResult(result.notified_count);
          setTitle("");
          setBody("");
          setLinkUrl("");
        },
      }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Broadcast Notification</h1>
        <p className="mt-1 text-muted-foreground">
          Send an in-app notification to every member of your organization.
        </p>
      </div>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle className="text-base">Compose</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="body">Body</Label>
            <Textarea id="body" rows={3} value={body} onChange={(e) => setBody(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="notificationType">Type</Label>
              <Select value={notificationType} onValueChange={(v) => setNotificationType(v as NotificationType)}>
                <SelectTrigger id="notificationType">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {typeOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="linkUrl">Link (optional)</Label>
              <Input
                id="linkUrl"
                placeholder="/announcements/123"
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
              />
            </div>
          </div>

          {broadcast.isError && (
            <p className="text-sm text-destructive">
              {(broadcast.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Could not send broadcast."}
            </p>
          )}
          {lastResult !== null && (
            <p className="text-sm text-emerald-600">Sent to {lastResult} member(s).</p>
          )}

          <Button disabled={!title || broadcast.isPending} onClick={handleSubmit}>
            {broadcast.isPending ? "Sending..." : "Send broadcast"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
