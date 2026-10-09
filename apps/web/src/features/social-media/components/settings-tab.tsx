import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { Capability } from "@/features/social-media/api/social-media-api";
import { useIntegration, useSocialSettings, useUpdateSocialSettings } from "@/features/social-media/api/social-media-hooks";
import { TIMEZONES, errorMessage, formatInZone } from "@/features/social-media/lib/format";

const NATIVE_SELECT = "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

const API_LABEL: Record<Capability["api"], { text: string; variant: "success" | "warning" | "secondary" | "destructive" }> = {
  supported: { text: "Offered by Meta's API", variant: "success" },
  needs_app_review: { text: "Needs Meta app review", variant: "warning" },
  restricted: { text: "Restricted by Meta", variant: "warning" },
  unavailable: { text: "Not available", variant: "destructive" },
};

export function SettingsTab() {
  const settings = useSocialSettings();
  const integration = useIntegration();
  const update = useUpdateSocialSettings();
  const me = useMyRoles();
  const canManage = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.manage");

  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [publishMode, setPublishMode] = useState<"manual" | "scheduled">("manual");
  const [budget, setBudget] = useState("0");
  const [alertAt, setAlertAt] = useState("80");
  const [emails, setEmails] = useState("");
  const [onFailure, setOnFailure] = useState(true);
  const [onExpiry, setOnExpiry] = useState(true);
  const [retention, setRetention] = useState("365");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const data = settings.data;
  useEffect(() => {
    if (!data) return;
    setTimezone(data.timezone);
    setPublishMode(data.publish_mode);
    setBudget(String(data.budgets.monthly_budget_inr));
    setAlertAt(String(data.budgets.alert_at_percent));
    setEmails(data.notifications.emails.join("\n"));
    setOnFailure(data.notifications.notify_on_failure);
    setOnExpiry(data.notifications.notify_on_token_expiry);
    setRetention(String(data.retention_days));
  }, [data]);

  if (settings.isLoading || integration.isLoading) return <Skeleton className="h-64 w-full" />;
  if (settings.isError || integration.isError || !data || !integration.data) {
    return <p className="text-sm text-destructive">Couldn&apos;t load the settings.</p>;
  }
  const info = integration.data;
  const zones = TIMEZONES.includes(timezone) ? TIMEZONES : [timezone, ...TIMEZONES];

  function save() {
    setMessage(null);
    update.mutate(
      {
        timezone,
        publish_mode: publishMode,
        budgets: { monthly_budget_inr: Number(budget) || 0, alert_at_percent: Number(alertAt) || 80 },
        notifications: {
          emails: emails.split(/[\s,]+/).filter(Boolean),
          notify_on_failure: onFailure,
          notify_on_token_expiry: onExpiry,
        },
        retention_days: Number(retention) || 365,
      },
      {
        onSuccess: () => setMessage({ ok: true, text: "Settings saved." }),
        onError: (e) => setMessage({ ok: false, text: errorMessage(e, "Couldn't save the settings.") }),
      },
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Instagram connection</CardTitle>
          <CardDescription>Nothing is published, read or sent until an account is connected.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {info.account ? (
            <div className="space-y-1">
              <p>
                <span className="font-medium">@{info.account.username ?? info.account.id}</span>{" "}
                <Badge variant={info.connected ? "success" : "warning"}>{info.account.status}</Badge>
              </p>
              {info.account.token_expires_at && <p>Access expires {formatInZone(info.account.token_expires_at, data.timezone)}</p>}
              {info.account.last_synced_at && <p>Last synced {formatInZone(info.account.last_synced_at, data.timezone)}</p>}
              {info.account.last_error && <p className="text-destructive">{info.account.last_error}</p>}
            </div>
          ) : (
            <>
              <Badge variant="secondary">Not connected</Badge>
              <p className="text-muted-foreground">
                The connection flow is built in Phase 4, once the Meta app exists. To prepare, follow these steps:
              </p>
              <ol className="list-decimal space-y-1 pl-5">
                {info.setup_steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <a className="text-primary underline" href="https://developers.facebook.com/docs/instagram-platform/" target="_blank" rel="noreferrer noopener">
                Meta&apos;s Instagram platform documentation
              </a>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>What Instagram allows, and what is built</CardTitle>
          <CardDescription>
            Nothing below has been checked against a live account yet. Replies to comments and messages are always written and sent by a person.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {info.capabilities.map((cap) => (
            <div key={cap.key} className="rounded-md border p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{cap.label}</span>
                <Badge variant={API_LABEL[cap.api].variant}>{API_LABEL[cap.api].text}</Badge>
                <Badge variant="outline">{cap.implemented === "yes" ? "Built" : cap.implemented === "never" ? "Not possible" : `Not built yet (${cap.implemented})`}</Badge>
                <Badge variant="outline">{cap.verified_live ? "Verified on a live account" : "Not verified live"}</Badge>
              </div>
              <p className="mt-1 text-muted-foreground">{cap.note}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Publishing, budget and notifications</CardTitle>
        </CardHeader>
        <fieldset disabled={!canManage}>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="s-tz">Account timezone</Label>
              <select id="s-tz" className={NATIVE_SELECT} value={timezone} onChange={(e) => setTimezone(e.target.value)}>
                {zones.map((zone) => (
                  <option key={zone} value={zone}>
                    {zone}
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">Planned times without a zone are read in this timezone.</p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-mode">After a post is approved</Label>
              <select id="s-mode" className={NATIVE_SELECT} value={publishMode} onChange={(e) => setPublishMode(e.target.value as "manual" | "scheduled")}>
                <option value="manual">I publish it myself</option>
                <option value="scheduled">Publish it at its scheduled time</option>
              </select>
              <p className="text-xs text-muted-foreground">Either way, nothing is published without an approval.</p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-budget">Monthly budget for AI and image services (INR)</Label>
              <Input id="s-budget" type="number" min={0} value={budget} onChange={(e) => setBudget(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-alert">Warn me at (% of budget)</Label>
              <Input id="s-alert" type="number" min={1} max={100} value={alertAt} onChange={(e) => setAlertAt(e.target.value)} />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="s-emails">Notification emails (one per line)</Label>
              <Textarea id="s-emails" rows={2} value={emails} onChange={(e) => setEmails(e.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={onFailure} onChange={(e) => setOnFailure(e.target.checked)} />
              Tell me when a post fails to publish
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={onExpiry} onChange={(e) => setOnExpiry(e.target.checked)} />
              Tell me before the Instagram access expires
            </label>
            <div className="space-y-1.5">
              <Label htmlFor="s-ret">Keep data for (days)</Label>
              <Input id="s-ret" type="number" min={30} max={3650} value={retention} onChange={(e) => setRetention(e.target.value)} />
            </div>
          </CardContent>
        </fieldset>
        {canManage && (
          <CardContent className="flex items-center gap-3 pt-0">
            <Button onClick={save} disabled={update.isPending}>
              {update.isPending ? "Saving..." : "Save settings"}
            </Button>
            {message && (
              <span role="status" className={message.ok ? "text-sm text-emerald-700" : "text-sm text-destructive"}>
                {message.text}
              </span>
            )}
          </CardContent>
        )}
      </Card>
    </div>
  );
}
