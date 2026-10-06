import { Mail, MoveRight, Pencil, Plus, Trash2, UserMinus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  HackathonPublic,
  MemberRef,
  RosterMember,
  RosterTeam,
} from "@/features/hackathons/api/hackathons-api";
import { useRoster, useTeamAdmin, useTeamCandidates } from "@/features/hackathons/api/hackathons-hooks";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

const NATIVE_SELECT =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/**
 * Choose who to put in a team: someone who already has a login and isn't in a team yet
 * (searchable), or a new person by name and email (a login and a set-password email are created).
 */
function MemberPicker({
  hackathonId,
  onChange,
}: {
  hackathonId: string;
  onChange: (ref: MemberRef | null) => void;
}) {
  const [mode, setMode] = useState<"existing" | "new">("existing");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const { data: candidates, isFetching } = useTeamCandidates(hackathonId, query, mode === "existing");

  useEffect(() => {
    if (mode === "existing") onChange(selected ? { student_id: selected } : null);
    else onChange(name.trim() && email.trim() ? { name: name.trim(), email: email.trim(), phone: phone.trim() || undefined } : null);
  }, [mode, selected, name, email, phone, onChange]);

  return (
    <div className="space-y-3">
      <div className="inline-flex rounded-md border p-0.5 text-sm">
        {(["existing", "new"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`rounded px-3 py-1 ${mode === m ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
          >
            {m === "existing" ? "Existing participant" : "New person"}
          </button>
        ))}
      </div>
      {mode === "existing" ? (
        <div className="space-y-2">
          <Input
            placeholder="Search by name or email"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search participants"
          />
          <ul className="max-h-48 divide-y overflow-y-auto rounded-md border text-sm">
            {(candidates ?? []).map((c) => (
              <li key={c.student_id}>
                <button
                  type="button"
                  onClick={() => setSelected(c.student_id)}
                  className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left ${
                    selected === c.student_id ? "bg-primary/10" : "hover:bg-muted/50"
                  }`}
                >
                  <span>{c.full_name}</span>
                  <span className="truncate text-xs text-muted-foreground">{c.email}</span>
                </button>
              </li>
            ))}
            {candidates && candidates.length === 0 && (
              <li className="px-3 py-3 text-muted-foreground">
                {isFetching ? "Searching..." : "Nobody without a team matches. Use New person to add them."}
              </li>
            )}
          </ul>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="space-y-1">
            <Label htmlFor="new-member-name">Name</Label>
            <Input id="new-member-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="new-member-email">Email</Label>
            <Input id="new-member-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="new-member-phone">Phone (optional)</Label>
            <Input id="new-member-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          <p className="text-xs text-muted-foreground">
            They get an ERPX login and an email with a link to set their password. If this email already has a
            login, that person is added as they are.
          </p>
        </div>
      )}
    </div>
  );
}

type Dialogs =
  | { kind: "create" }
  | { kind: "rename"; team: RosterTeam }
  | { kind: "add"; team: RosterTeam }
  | { kind: "edit"; team: RosterTeam; member: RosterMember }
  | { kind: "move"; team: RosterTeam; member: RosterMember }
  | null;

/** Create a team (name + first member), add a member to one, or rename one. */
function TeamFormDialog({
  hackathon,
  dialog,
  admin,
  onClose,
  onDone,
}: {
  hackathon: HackathonPublic;
  dialog: Extract<Dialogs, { kind: "create" | "rename" | "add" }>;
  admin: ReturnType<typeof useTeamAdmin>;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [name, setName] = useState(dialog.kind === "rename" ? dialog.team.name : "");
  const [member, setMember] = useState<MemberRef | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const needsName = dialog.kind !== "add";
  const needsMember = dialog.kind !== "rename";
  const ready = (!needsName || name.trim() !== "") && (!needsMember || member !== null);

  const title = dialog.kind === "create" ? "Create a team" : dialog.kind === "rename" ? "Rename team" : `Add a member to ${dialog.team.name}`;

  const submit = async () => {
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (dialog.kind === "create" && member) await admin.createTeam.mutateAsync({ name: name.trim(), member });
      else if (dialog.kind === "rename") await admin.renameTeam.mutateAsync({ teamId: dialog.team.id, name: name.trim() });
      else if (dialog.kind === "add" && member) await admin.addMember.mutateAsync({ teamId: dialog.team.id, member });
      onDone(dialog.kind === "create" ? `Team "${name.trim()}" created.` : dialog.kind === "rename" ? "Team renamed." : "Member added.");
    } catch (e) {
      setError(errorMessage(e, "That didn't work."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {dialog.kind === "create"
              ? `A team needs at least one member. Up to ${hackathon.max_team_size} people fit in a team; add the rest afterwards.`
              : dialog.kind === "add"
                ? `${dialog.team.members.length} of ${hackathon.max_team_size} places taken.`
                : "Team names must be unique within the hackathon."}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          {needsName && (
            <div className="space-y-1">
              <Label htmlFor="team-name">Team name</Label>
              <Input id="team-name" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
            </div>
          )}
          {needsMember && <MemberPicker hackathonId={hackathon.id} onChange={setMember} />}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!ready || busy}>
              {busy ? "Saving..." : dialog.kind === "create" ? "Create team" : dialog.kind === "rename" ? "Rename" : "Add member"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Correct a member's name, phone or login email. */
export function EditMemberDialog({
  member,
  admin,
  onClose,
  onDone,
}: {
  member: Pick<RosterMember, "student_id" | "full_name" | "email" | "phone">;
  admin: ReturnType<typeof useTeamAdmin>;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [fullName, setFullName] = useState(member.full_name);
  const [email, setEmail] = useState(member.email ?? "");
  const [phone, setPhone] = useState(member.phone ?? "");
  const [sendLink, setSendLink] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const emailChanged = email.trim().toLowerCase() !== (member.email ?? "").toLowerCase();
  const changed = fullName.trim() !== member.full_name || phone.trim() !== (member.phone ?? "") || emailChanged;
  const valid = fullName.trim() !== "" && email.trim() !== "";

  const submit = async () => {
    if (!changed || !valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await admin.updateMember.mutateAsync({
        studentId: member.student_id,
        payload: {
          ...(fullName.trim() !== member.full_name ? { full_name: fullName.trim() } : {}),
          ...(emailChanged ? { email: email.trim(), send_login_link: sendLink } : {}),
          ...(phone.trim() !== (member.phone ?? "") ? { phone: phone.trim() } : {}),
        },
      });
      onDone(result.message);
    } catch (e) {
      setError(errorMessage(e, "Could not save the changes."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {member.full_name}</DialogTitle>
          <DialogDescription>Fix a name, phone number or the email address they sign in with.</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="edit-name">Name</Label>
            <Input id="edit-name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="edit-email">Email (their login)</Label>
            <Input id="edit-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="edit-phone">Phone</Label>
            <Input id="edit-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          {emailChanged && (
            <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
              <p>
                Their login moves to the new address. The old address stops working, they are signed out everywhere,
                and any unused set-password link is cancelled.
              </p>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={sendLink} onChange={(e) => setSendLink(e.target.checked)} />
                <span>Email the new address a link to set a password</span>
              </label>
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!changed || !valid || busy}>
              {busy ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Move a member to another team that has room. */
function MoveMemberDialog({
  hackathon,
  teams,
  from,
  member,
  admin,
  onClose,
  onDone,
}: {
  hackathon: HackathonPublic;
  teams: RosterTeam[];
  from: RosterTeam;
  member: RosterMember;
  admin: ReturnType<typeof useTeamAdmin>;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const options = teams.filter((t) => t.id !== from.id);
  const [target, setTarget] = useState(options.find((t) => t.members.length < hackathon.max_team_size)?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!target || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await admin.moveMember.mutateAsync({ studentId: member.student_id, teamId: target });
      onDone(result.message);
    } catch (e) {
      setError(errorMessage(e, "Could not move them."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Move {member.full_name}</DialogTitle>
          <DialogDescription>
            From {from.name}. Task submissions stay with the team that made them, so they will not move with the person.
          </DialogDescription>
        </DialogHeader>
        {options.length === 0 ? (
          <p className="text-sm text-muted-foreground">There is no other team to move them to.</p>
        ) : (
          <div className="space-y-1">
            <Label htmlFor="move-target">New team</Label>
            <select id="move-target" className={NATIVE_SELECT} value={target} onChange={(e) => setTarget(e.target.value)}>
              {options.map((t) => (
                <option key={t.id} value={t.id} disabled={t.members.length >= hackathon.max_team_size}>
                  {t.name} ({t.members.length} / {hackathon.max_team_size}
                  {t.members.length >= hackathon.max_team_size ? ", full" : ""})
                </option>
              ))}
            </select>
          </div>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!target || busy} onClick={() => void submit()}>
            {busy ? "Moving..." : "Move"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Teams and their members, with the organiser's controls: create, rename, delete, add / remove / move members, edit logins. */
export function TeamsTab({ hackathon }: { hackathon: HackathonPublic }) {
  const { data: teams, isLoading } = useRoster(hackathon.id);
  const admin = useTeamAdmin(hackathon.id);
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<Dialogs>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return teams ?? [];
    return (teams ?? []).filter(
      (t) =>
        t.name.toLowerCase().includes(needle) ||
        t.members.some((m) => m.full_name.toLowerCase().includes(needle) || (m.email ?? "").toLowerCase().includes(needle))
    );
  }, [teams, search]);

  const memberTotal = (teams ?? []).reduce((sum, t) => sum + t.members.length, 0);

  const run = async (action: () => Promise<{ message: string }>) => {
    try {
      const result = await action();
      setNotice({ tone: "ok", text: result.message });
    } catch (e) {
      setNotice({ tone: "error", text: errorMessage(e, "That didn't work.") });
    }
  };
  const done = (message: string) => {
    setDialog(null);
    setNotice({ tone: "ok", text: message });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">Teams and members</CardTitle>
            <CardDescription>
              {teams?.length ?? 0} teams, {memberTotal} members. A team holds up to {hackathon.max_team_size} people.
            </CardDescription>
          </div>
          <Button onClick={() => setDialog({ kind: "create" })}>
            <Plus className="h-4 w-4" />
            Create team
          </Button>
        </div>
        <Input
          placeholder="Search by team, name or email"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search teams"
          className="max-w-sm"
        />
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
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : visible.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            {search ? "No team or member matches." : "No teams yet. Students create them from the student portal, or use Create team."}
          </p>
        ) : (
          visible.map((team) => (
            <div key={team.id} className="rounded-lg border">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b p-3">
                <div>
                  <h3 className="font-semibold">{team.name}</h3>
                  <p className="text-xs text-muted-foreground">
                    {team.members.length} / {hackathon.max_team_size} members · {team.tasks_submitted} task
                    {team.tasks_submitted === 1 ? "" : "s"} submitted · {team.total_score} points
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={team.members.length >= hackathon.max_team_size}
                    title={team.members.length >= hackathon.max_team_size ? "The team is full" : undefined}
                    onClick={() => setDialog({ kind: "add", team })}
                  >
                    <Plus className="h-4 w-4" />
                    Add member
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setDialog({ kind: "rename", team })}>
                    <Pencil className="h-4 w-4" />
                    Rename
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-destructive hover:text-destructive"
                    onClick={() => {
                      if (
                        window.confirm(
                          `Delete team "${team.name}"? Its ${team.members.length} member${team.members.length === 1 ? "" : "s"} leave the team (their logins stay) and its ${team.tasks_submitted} task submission${team.tasks_submitted === 1 ? "" : "s"} and marks are deleted.`
                        )
                      ) {
                        void run(() => admin.deleteTeam.mutateAsync(team.id));
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </Button>
                </div>
              </div>
              {team.members.length === 0 ? (
                <p className="p-3 text-sm text-muted-foreground">No members.</p>
              ) : (
                <ul className="divide-y">
                  {team.members.map((member) => (
                    <li key={member.student_id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
                      <div className="min-w-0">
                        <p className="font-medium">
                          {member.full_name}
                          {member.is_creator && <span className="ml-2 text-xs font-normal text-muted-foreground">creator</span>}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">
                          {member.email ?? "no email"}
                          {member.phone ? ` · ${member.phone}` : ""}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge variant={member.has_logged_in ? "success" : "warning"}>
                          {member.has_logged_in ? "Signed in" : "Not signed in yet"}
                        </Badge>
                        <Button size="sm" variant="ghost" onClick={() => setDialog({ kind: "edit", team, member })}>
                          <Pencil className="h-4 w-4" />
                          Edit
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setDialog({ kind: "move", team, member })}>
                          <MoveRight className="h-4 w-4" />
                          Move
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          title="Email a fresh set-password link"
                          onClick={() => void run(() => admin.sendLoginLink.mutateAsync(member.student_id))}
                        >
                          <Mail className="h-4 w-4" />
                          Login link
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-destructive hover:text-destructive"
                          onClick={() => {
                            if (
                              window.confirm(
                                `Remove ${member.full_name} from "${team.name}"? Their login stays and they can join or be added to another team.`
                              )
                            ) {
                              void run(() => admin.removeMember.mutateAsync({ teamId: team.id, studentId: member.student_id }));
                            }
                          }}
                        >
                          <UserMinus className="h-4 w-4" />
                          Remove
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))
        )}
      </CardContent>

      {dialog && (dialog.kind === "create" || dialog.kind === "rename" || dialog.kind === "add") && (
        <TeamFormDialog hackathon={hackathon} dialog={dialog} admin={admin} onClose={() => setDialog(null)} onDone={done} />
      )}
      {dialog?.kind === "edit" && (
        <EditMemberDialog member={dialog.member} admin={admin} onClose={() => setDialog(null)} onDone={done} />
      )}
      {dialog?.kind === "move" && (
        <MoveMemberDialog
          hackathon={hackathon}
          teams={teams ?? []}
          from={dialog.team}
          member={dialog.member}
          admin={admin}
          onClose={() => setDialog(null)}
          onDone={done}
        />
      )}
    </Card>
  );
}
