import { Copy } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { IntegrationOverview } from "@/features/social-media/api/social-media-api";
import { useDisconnect, useRecheck, useRefreshToken, useStartConnect } from "@/features/social-media/api/social-media-hooks";
import { errorMessage, formatInZone } from "@/features/social-media/lib/format";

const REASONS: Record<string, string> = {
  denied: "The connection was cancelled on Instagram, so nothing was connected.",
  state: "That connection link was already used or has expired. Press Connect Instagram to start again.",
  exchange: "Instagram refused the connection. Check that the redirect address in the Meta app matches the one below exactly, and that the app's permissions are set up.",
  network: "Instagram couldn't be reached. Try again in a moment.",
  profile: "The connected account's details couldn't be read. Try again.",
  token: "Instagram rejected the access it had just given. Try connecting again.",
  permission: "The person who started this connection is no longer allowed to connect accounts.",
  account_type: "That Instagram account isn't a Professional account. Switch it to Business or Creator in the Instagram app, then connect again.",
};

const STATUS: Record<string, { text: string; variant: "success" | "warning" | "destructive" | "secondary" }> = {
  connected: { text: "Connected", variant: "success" },
  expiring: { text: "Access expiring soon", variant: "warning" },
  expired: { text: "Access expired: reconnect", variant: "destructive" },
  revoked: { text: "Access revoked: reconnect", variant: "destructive" },
  not_connected: { text: "Not connected", variant: "secondary" },
  error: { text: "Problem: reconnect", variant: "destructive" },
};

function Copyable({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium">{label}</p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 break-all rounded border bg-muted/40 px-2 py-1 text-xs">{value}</code>
        <Button
          type="button"
          size="icon"
          variant="outline"
          aria-label={`Copy ${label}`}
          onClick={() => {
            navigator.clipboard
              ?.writeText(value)
              .then(() => setCopied(true))
              .catch(() => setCopied(false));
          }}
        >
          <Copy className="h-3.5 w-3.5" />
        </Button>
        {copied && <span className="text-xs text-emerald-700">Copied</span>}
      </div>
    </div>
  );
}

/** Connect, reconnect or disconnect the Instagram account, and say plainly what is missing before it can be connected. */
export function ConnectionCard({ info, timeZone }: { info: IntegrationOverview; timeZone: string }) {
  const [params, setParams] = useSearchParams();
  const me = useMyRoles();
  const start = useStartConnect();
  const disconnect = useDisconnect();
  const recheck = useRecheck();
  const refresh = useRefreshToken();
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const canConnect = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.connect");
  const account = info.account;
  const status = account ? STATUS[account.status] ?? STATUS.error : STATUS.not_connected;
  const busy = start.isPending || disconnect.isPending || recheck.isPending || refresh.isPending;

  const result = params.get("connect");
  const reason = params.get("reason");
  function dismissResult() {
    const next = new URLSearchParams(params);
    next.delete("connect");
    next.delete("reason");
    setParams(next, { replace: true });
  }

  function connect() {
    setMessage(null);
    start.mutate(undefined, {
      onSuccess: (r) => window.location.assign(r.url),
      onError: (e) => setMessage({ ok: false, text: errorMessage(e, "Couldn't start the connection.") }),
    });
  }

  const run = (action: { mutate: (v: undefined, o: { onSuccess: (r: unknown) => void; onError: (e: unknown) => void }) => void }, done: string) => {
    setMessage(null);
    action.mutate(undefined, { onSuccess: () => setMessage({ ok: true, text: done }), onError: (e) => setMessage({ ok: false, text: errorMessage(e, "That didn't work.") }) });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Instagram connection</CardTitle>
        <CardDescription>Nothing is published, read or sent until an account is connected. The access token is stored encrypted on the server and is never shown or sent to your browser.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {result && (
          <div role={result === "ok" ? "status" : "alert"} className={`flex items-start justify-between gap-3 rounded-md border p-3 ${result === "ok" ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "border-destructive/40 bg-destructive/5 text-destructive"}`}>
            <span>{result === "ok" ? "Instagram is connected." : REASONS[reason ?? ""] ?? "The connection didn't complete."}</span>
            <Button size="sm" variant="ghost" onClick={dismissResult}>
              Dismiss
            </Button>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          {account && <span className="font-medium">@{account.username ?? "account"}</span>}
          {account?.account_type && <Badge variant="outline">{account.account_type.toLowerCase()}</Badge>}
          <Badge variant={status.variant}>{status.text}</Badge>
          {account?.token_days_left != null && <span className="text-muted-foreground">access lasts about {account.token_days_left} more day(s); it is renewed automatically</span>}
        </div>
        {account?.token_expires_at && <p className="text-xs text-muted-foreground">Access expires {formatInZone(account.token_expires_at, timeZone)}.</p>}
        {account?.last_error && <p className="text-destructive">{account.last_error}</p>}

        {canConnect ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={connect} disabled={busy || !info.app_configured}>
              {start.isPending ? "Opening Instagram..." : account ? "Reconnect Instagram" : "Connect Instagram"}
            </Button>
            {account && (
              <>
                <Button variant="outline" disabled={busy} onClick={() => run(recheck, "Checked again. See what the account can do below.")}>
                  {recheck.isPending ? "Checking..." : "Check what it can do"}
                </Button>
                <Button variant="outline" disabled={busy} onClick={() => run(refresh, "The access token was renewed.")}>
                  Renew access now
                </Button>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => window.confirm("Disconnect Instagram? The access token is deleted from this server. Scheduled posts will fail until you reconnect.") && run(disconnect, "Disconnected. The access token was deleted.")}
                >
                  Disconnect
                </Button>
              </>
            )}
            {!info.app_configured && <span className="text-xs text-muted-foreground">Needs configuration: the Meta app isn&apos;t set up on this server yet (steps below).</span>}
          </div>
        ) : (
          <p className="text-muted-foreground">Connecting or disconnecting the account needs the social_media.connect permission.</p>
        )}
        {message && (
          <p role={message.ok ? "status" : "alert"} className={message.ok ? "text-emerald-700" : "text-destructive"}>
            {message.text}
          </p>
        )}

        {(!account || !info.app_configured || !info.webhook_verify_token_set) && (
          <div className="space-y-3 rounded-md border p-3">
            <p className="font-medium">Set-up steps</p>
            <ol className="list-decimal space-y-1 pl-5">
              {info.setup_steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <div className="grid gap-3">
              <Copyable label="Redirect address (valid OAuth redirect URI)" value={info.redirect_uri} />
              <Copyable label="Webhook callback address" value={info.webhook_url} />
              <p className="text-xs text-muted-foreground">
                Server settings: app ID and secret {info.app_configured ? "are set" : "are NOT set"}; webhook verify token {info.webhook_verify_token_set ? "is set" : "is NOT set"}. Permissions requested: {info.scopes_requested.join(", ")}.
              </p>
            </div>
            <a className="text-primary underline" href="https://developers.facebook.com/docs/instagram-platform/" target="_blank" rel="noreferrer noopener">
              Meta&apos;s Instagram platform documentation
            </a>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
