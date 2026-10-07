import { Copy, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { HackathonPublic } from "@/features/hackathons/api/hackathons-api";
import { useUpdateHackathon } from "@/features/hackathons/api/hackathons-hooks";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

/** The same tidying the server does, so what is typed is what will be saved. */
function tidy(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * A public, no-login live leaderboard to put on a screen: turn it on, then edit the end of the
 * link to whatever you like (letters, numbers and hyphens), copy it and share it.
 */
export function LeaderboardShareCard({ hackathon }: { hackathon: HackathonPublic }) {
  const update = useUpdateHackathon(hackathon.id);
  const [slug, setSlug] = useState(hackathon.leaderboard_slug ?? "");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setSlug(hackathon.leaderboard_slug ?? "");
  }, [hackathon.leaderboard_slug]);

  const url = hackathon.leaderboard_share_url;
  // Everything in the link before the editable part, e.g. "https://lms.example.com/live/".
  const prefix = url && hackathon.leaderboard_slug ? url.slice(0, url.length - hackathon.leaderboard_slug.length) : "";
  const cleaned = tidy(slug);
  const valid = cleaned.length >= 3 && cleaned.length <= 60;
  const changed = valid && cleaned !== hackathon.leaderboard_slug;
  const enabled = hackathon.leaderboard_share_enabled;

  const saveSlug = () => {
    if (changed && !update.isPending) update.mutate({ leaderboard_slug: cleaned });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Presentation link</CardTitle>
        <CardDescription>
          {enabled
            ? "Anyone with this link can watch the live leaderboard, no login needed."
            : "Share the live leaderboard on a big screen with a link anyone can open, no login needed."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={enabled}
            disabled={update.isPending}
            onChange={(e) => update.mutate({ leaderboard_share_enabled: e.target.checked })}
          />
          <span>Share a public live leaderboard link</span>
        </label>

        {hackathon.leaderboard_slug && (
          <div className="space-y-2">
            <label htmlFor="leaderboard-slug" className="text-sm font-medium">
              Link name
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <span className="break-all text-xs text-muted-foreground">{prefix}</span>
              <Input
                id="leaderboard-slug"
                className={`h-9 w-48 ${slug.trim() !== "" && !valid ? "border-destructive" : ""}`}
                value={slug}
                maxLength={60}
                onChange={(e) => setSlug(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    saveSlug();
                  }
                }}
              />
              <Button size="sm" disabled={!changed || update.isPending} onClick={saveSlug}>
                Save
              </Button>
            </div>
            {slug.trim() !== "" && cleaned !== slug.trim() && (
              <p className="text-xs text-muted-foreground">
                Will be saved as <span className="font-mono">{cleaned || "…"}</span>
              </p>
            )}
            {!enabled && <p className="text-xs text-muted-foreground">Sharing is off, so this link shows nothing until you turn it on.</p>}
          </div>
        )}

        {enabled && url && (
          <div className="space-y-2 rounded-md border bg-muted/30 p-3">
            <p className="break-all font-mono text-xs">{url}</p>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  void navigator.clipboard?.writeText(url).then(() => {
                    setCopied(true);
                    window.setTimeout(() => setCopied(false), 1500);
                  });
                }}
              >
                <Copy className="h-4 w-4" />
                {copied ? "Copied" : "Copy link"}
              </Button>
              <Button asChild size="sm" variant="outline">
                <a href={url} target="_blank" rel="noreferrer">
                  <ExternalLink className="h-4 w-4" />
                  Open
                </a>
              </Button>
            </div>
          </div>
        )}

        {enabled && (
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={hackathon.leaderboard_show_members}
              disabled={update.isPending}
              onChange={(e) => update.mutate({ leaderboard_show_members: e.target.checked })}
            />
            <span>Show team members' names on the page (otherwise only team names)</span>
          </label>
        )}
        {update.isError && <p className="text-sm text-destructive">{errorMessage(update.error, "Could not save.")}</p>}
      </CardContent>
    </Card>
  );
}
