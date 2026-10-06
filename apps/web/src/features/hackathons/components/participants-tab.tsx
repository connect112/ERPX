import { Mail, Pencil, Trash2, UserMinus } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { HackathonPublic, Participant } from "@/features/hackathons/api/hackathons-api";
import { useParticipantActions, useParticipants, useTeamAdmin } from "@/features/hackathons/api/hackathons-hooks";
import { EditMemberDialog } from "@/features/hackathons/components/teams-tab";

type Filter = "all" | "not_signed_in" | "no_team";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border px-4 py-2">
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

/**
 * Everyone invited to the hackathon, whether or not they've formed a team: contact details,
 * team, and whether they have signed in. Select people for bulk actions: send a set-password
 * link, take them out of the hackathon (their login is kept), or delete their accounts.
 */
export function ParticipantsTab({ hackathon }: { hackathon: HackathonPublic }) {
  const { data: people, isLoading } = useParticipants(hackathon.id);
  const actions = useParticipantActions(hackathon.id);
  const teamAdmin = useTeamAdmin(hackathon.id);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<Participant | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const all = useMemo(() => people ?? [], [people]);
  const notSignedIn = all.filter((p) => !p.has_logged_in);
  const noTeam = all.filter((p) => p.team_id === null);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return all.filter((p) => {
      if (filter === "not_signed_in" && p.has_logged_in) return false;
      if (filter === "no_team" && p.team_id !== null) return false;
      if (!needle) return true;
      return [p.full_name, p.email ?? "", p.phone ?? "", p.team_name ?? "", p.student_code].some((v) =>
        v.toLowerCase().includes(needle)
      );
    });
  }, [all, search, filter]);

  const chosen = all.filter((p) => selected.has(p.student_id));
  const allVisibleSelected = visible.length > 0 && visible.every((p) => selected.has(p.student_id));

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const report = (text: string, tone: "ok" | "error" = "ok") => setNotice({ tone, text });

  const sendLinks = async (ids: string[] | null, count: number) => {
    try {
      const result = await actions.sendLinks.mutateAsync(ids);
      report(result.message);
    } catch (e) {
      report(errorMessage(e, `Could not send the link${count === 1 ? "" : "s"}.`), "error");
    }
  };

  const removePeople = async (ids: string[], deleteAccount: boolean) => {
    try {
      const result = await actions.remove.mutateAsync({ studentIds: ids, deleteAccount });
      setSelected((prev) => new Set([...prev].filter((id) => !ids.includes(id))));
      const verb = deleteAccount ? "Deleted" : "Removed";
      if (result.skipped.length === 0) report(`${verb} ${result.done} participant${result.done === 1 ? "" : "s"}.`);
      else
        report(
          `${verb} ${result.done}. Skipped ${result.skipped.length}: ${result.skipped
            .map((s) => `${s.name} (${s.reason})`)
            .join("; ")}`,
          "error"
        );
    } catch (e) {
      report(errorMessage(e, "That didn't work."), "error");
    }
  };

  const confirmRemove = (people: Participant[]) => {
    const who = people.length === 1 ? people[0].full_name : `${people.length} participants`;
    if (
      window.confirm(
        `Remove ${who} from this hackathon? They leave their team and this list. Their ERPX login is kept.`
      )
    ) {
      void removePeople(
        people.map((p) => p.student_id),
        false
      );
    }
  };

  const confirmDelete = (people: Participant[]) => {
    const deletable = people.filter((p) => p.can_delete_account);
    const blocked = people.length - deletable.length;
    if (deletable.length === 0) {
      report("None of these accounts can be deleted from here: they have other access in ERPX.", "error");
      return;
    }
    const who = deletable.length === 1 ? deletable[0].full_name : `${deletable.length} accounts`;
    if (
      window.confirm(
        `Delete ${who} permanently? They can no longer sign in, they leave every hackathon, and their email address is freed to invite again. This cannot be undone.${
          blocked > 0 ? ` (${blocked} selected ${blocked === 1 ? "has" : "have"} other access and will be skipped.)` : ""
        }`
      )
    ) {
      void removePeople(
        deletable.map((p) => p.student_id),
        true
      );
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Participants</CardTitle>
            <CardDescription>
              Everyone invited to this hackathon, with or without a team. Add people from the Overview tab.
            </CardDescription>
          </div>
          <Button
            variant="outline"
            disabled={notSignedIn.length === 0 || actions.sendLinks.isPending}
            onClick={() => {
              if (
                window.confirm(
                  `Email a fresh set-password link to the ${notSignedIn.length} participant${notSignedIn.length === 1 ? "" : "s"} who haven't signed in yet?`
                )
              ) {
                void sendLinks(null, notSignedIn.length);
              }
            }}
          >
            <Mail className="h-4 w-4" />
            Send link to everyone not signed in ({notSignedIn.length})
          </Button>
        </div>
        <div className="flex flex-wrap gap-3 pt-1">
          <Stat label="Invited" value={all.length} />
          <Stat label="Signed in" value={all.length - notSignedIn.length} />
          <Stat label="Not signed in yet" value={notSignedIn.length} />
          <Stat label="In a team" value={all.length - noTeam.length} />
          <Stat label="Without a team" value={noTeam.length} />
        </div>
        <div className="flex flex-wrap items-center gap-3 pt-1">
          <Input
            placeholder="Search by name, email, phone or team"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search participants"
            className="max-w-sm"
          />
          <div className="inline-flex rounded-md border p-0.5 text-sm">
            {(
              [
                ["all", "All"],
                ["not_signed_in", "Not signed in"],
                ["no_team", "No team"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={`rounded px-3 py-1 ${filter === value ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {notice && (
          <p
            role="status"
            className={`rounded-md p-2 text-sm ${
              notice.tone === "ok"
                ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
                : "bg-destructive/10 text-destructive"
            }`}
          >
            {notice.text}
          </p>
        )}
        {chosen.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/40 p-2 text-sm">
            <span className="font-medium">{chosen.length} selected</span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void sendLinks(chosen.map((p) => p.student_id), chosen.length)}
            >
              <Mail className="h-4 w-4" />
              Send login link
            </Button>
            <Button size="sm" variant="outline" onClick={() => confirmRemove(chosen)}>
              <UserMinus className="h-4 w-4" />
              Remove from hackathon
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="text-destructive hover:text-destructive"
              onClick={() => confirmDelete(chosen)}
            >
              <Trash2 className="h-4 w-4" />
              Delete accounts
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
              Clear
            </Button>
          </div>
        )}
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <Skeleton className="m-6 h-24" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-y text-left text-xs text-muted-foreground">
                  <th className="w-10 px-4 py-2">
                    <input
                      type="checkbox"
                      aria-label="Select everyone shown"
                      checked={allVisibleSelected}
                      onChange={() =>
                        setSelected((prev) => {
                          const next = new Set(prev);
                          if (allVisibleSelected) visible.forEach((p) => next.delete(p.student_id));
                          else visible.forEach((p) => next.add(p.student_id));
                          return next;
                        })
                      }
                    />
                  </th>
                  <th className="px-2 py-2 font-medium">Name</th>
                  <th className="px-2 py-2 font-medium">Email</th>
                  <th className="px-2 py-2 font-medium">Phone</th>
                  <th className="px-2 py-2 font-medium">Team</th>
                  <th className="px-2 py-2 font-medium">Status</th>
                  <th className="px-2 py-2 font-medium">Invited</th>
                  <th className="px-4 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {visible.map((p) => (
                  <tr key={p.student_id} className={selected.has(p.student_id) ? "bg-primary/5" : ""}>
                    <td className="px-4 py-2">
                      <input
                        type="checkbox"
                        aria-label={`Select ${p.full_name}`}
                        checked={selected.has(p.student_id)}
                        onChange={() => toggle(p.student_id)}
                      />
                    </td>
                    <td className="px-2 py-2 font-medium">{p.full_name}</td>
                    <td className="px-2 py-2 text-muted-foreground">{p.email ?? "-"}</td>
                    <td className="px-2 py-2 text-muted-foreground">{p.phone ?? "-"}</td>
                    <td className="px-2 py-2">
                      {p.team_name ? (
                        <span>
                          {p.team_name}
                          {p.is_creator && <span className="ml-1 text-xs text-muted-foreground">(creator)</span>}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">No team</span>
                      )}
                    </td>
                    <td className="px-2 py-2">
                      <Badge variant={p.has_logged_in ? "success" : "warning"}>
                        {p.has_logged_in ? "Signed in" : "Not signed in yet"}
                      </Badge>
                      {p.last_login_at && (
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          last {new Date(p.last_login_at).toLocaleString()}
                        </p>
                      )}
                    </td>
                    <td className="px-2 py-2 text-xs text-muted-foreground">
                      {p.invited_at ? new Date(p.invited_at).toLocaleDateString() : "-"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-right">
                      <Button size="sm" variant="ghost" title="Edit name, phone or email" onClick={() => setEditing(p)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        title="Email a fresh set-password link"
                        onClick={() => void sendLinks([p.student_id], 1)}
                      >
                        <Mail className="h-4 w-4" />
                      </Button>
                      <Button size="sm" variant="ghost" title="Remove from this hackathon" onClick={() => confirmRemove([p])}>
                        <UserMinus className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-destructive hover:text-destructive"
                        disabled={!p.can_delete_account}
                        title={
                          p.can_delete_account
                            ? "Delete this account"
                            : "Has other access in ERPX; remove from the hackathon instead"
                        }
                        onClick={() => confirmDelete([p])}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
                {visible.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-muted-foreground">
                      {all.length === 0
                        ? "Nobody has been invited yet. Add participants from the Overview tab."
                        : "No participant matches."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
      {editing && (
        <EditMemberDialog
          member={editing}
          admin={teamAdmin}
          onClose={() => setEditing(null)}
          onDone={(message) => {
            setEditing(null);
            report(message);
          }}
        />
      )}
    </Card>
  );
}
