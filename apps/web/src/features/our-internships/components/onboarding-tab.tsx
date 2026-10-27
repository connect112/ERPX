import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, KeyRound, Wallet } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/features/institutions/lib/format";
import {
  type GrantResult,
  type OurInternship,
  onboardingApi,
  ourInternshipsApi,
  ourInternshipsKeys,
} from "@/features/our-internships/api/our-internships-api";
import { StudentOnboardingDialog } from "@/features/our-internships/components/student-onboarding-dialog";
import {
  LMS_LABELS,
  OFFER_RESPONSE_LABELS,
  PAYMENT_LABELS,
  STAGE_ORDER,
  VERIFICATION_LABELS,
  chunk,
  grantableIds,
  stageCounts,
  stageVariant,
} from "@/features/our-internships/lib/onboarding";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";
const GRANT_BATCH = 25;

/**
 * After the offers: see every selected student's stage at a glance, mark verification and payment (one at a time from their
 * profile, or many at once), and grant LMS access. The LMS course is chosen here, once, for the whole internship.
 */
export function OnboardingTab({ internship }: { internship: OurInternship }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [results, setResults] = useState<GrantResult[] | null>(null);
  const [progress, setProgress] = useState<string | null>(null);

  const selected = useQuery({ queryKey: ourInternshipsKeys.selected(internship.id), queryFn: () => ourInternshipsApi.selected(internship.id) });
  const courses = useQuery({ queryKey: ["our-internships", "courses", internship.id], queryFn: () => onboardingApi.courses(internship.id) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });

  const setCourse = useMutation({ mutationFn: (courseId: string | null) => onboardingApi.setCourse(internship.id, courseId), onSuccess: refresh });
  const mark = useMutation({
    mutationFn: (v: { verification_status?: "verified"; payment_status?: "paid" }) => onboardingApi.updateMany(internship.id, [...picked], v),
    onSuccess: refresh,
  });
  const grant = useMutation({
    mutationFn: async (ids: string[]) => {
      const all: GrantResult[] = [];
      const batches = chunk(ids, GRANT_BATCH);
      for (let i = 0; i < batches.length; i++) {
        setProgress(batches.length > 1 ? `Granting access... ${i * GRANT_BATCH} of ${ids.length}` : "Granting access...");
        all.push(...(await onboardingApi.grantMany(internship.id, batches[i])).results);
      }
      return all;
    },
    onSuccess: (all) => {
      setResults(all);
      setPicked(new Set());
      void refresh();
    },
    onSettled: () => setProgress(null),
  });

  const items = useMemo(() => selected.data?.items ?? [], [selected.data]);
  const counts = useMemo(() => stageCounts(items), [items]);
  const ready = useMemo(() => new Set(grantableIds(items)), [items]);
  const readyPicked = [...picked].filter((id) => ready.has(id));

  if (selected.isLoading) return <Skeleton className="h-40 w-full" />;
  if (selected.isError) return <p className="text-sm text-destructive">Could not load the selected students.</p>;

  const toggle = (id: string, on: boolean) => {
    const next = new Set(picked);
    if (on) next.add(id);
    else next.delete(id);
    setPicked(next);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">LMS course</CardTitle>
          <CardDescription>Students given LMS access are enrolled in this course on lms.pentrix.in.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <select
            aria-label="LMS course"
            className={`${selectClass} w-full max-w-md`}
            value={internship.lms_course_id ?? ""}
            disabled={setCourse.isPending}
            onChange={(e) => setCourse.mutate(e.target.value || null)}
          >
            <option value="">Choose a course...</option>
            {courses.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
                {c.is_published ? "" : " (not published)"}
              </option>
            ))}
          </select>
          {courses.data?.length === 0 && <p className="text-xs text-muted-foreground">There are no courses yet. Create one under Courses first.</p>}
          {!internship.lms_course_id && <p className="text-xs text-amber-700 dark:text-amber-400">Choose the course before granting access.</p>}
          {setCourse.isError && <p className="text-sm text-destructive">{errorMessage(setCourse.error, "Could not save the course.")}</p>}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2" aria-label="Students per stage">
        {STAGE_ORDER.filter((stage) => counts[stage]).map((stage) => (
          <Badge key={stage} variant={stageVariant(stage)}>
            {items.find((i) => i.stage === stage)?.stage_label}: {counts[stage]}
          </Badge>
        ))}
      </div>

      {items.length === 0 ? (
        <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">No one is selected yet. Choose students first.</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">{picked.size} ticked</span>
            <Button size="sm" variant="outline" disabled={picked.size === 0 || mark.isPending} onClick={() => mark.mutate({ verification_status: "verified" })}>
              <BadgeCheck className="h-4 w-4" />
              Mark verified
            </Button>
            <Button size="sm" variant="outline" disabled={picked.size === 0 || mark.isPending} onClick={() => {
              if (window.confirm(`Mark payment as received for ${picked.size} student${picked.size === 1 ? "" : "s"}? Do this only once you have confirmed the money.`)) mark.mutate({ payment_status: "paid" });
            }}>
              <Wallet className="h-4 w-4" />
              Mark payment received
            </Button>
            <Button
              size="sm"
              disabled={readyPicked.length === 0 || grant.isPending}
              onClick={() => {
                if (window.confirm(`Give LMS access to ${readyPicked.length} student${readyPicked.length === 1 ? "" : "s"}? Each gets a login (if they have none) and an email.`)) grant.mutate(readyPicked);
              }}
            >
              <KeyRound className="h-4 w-4" />
              {grant.isPending ? progress ?? "Granting access..." : `Grant LMS access${readyPicked.length ? ` to ${readyPicked.length}` : ""}`}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setPicked(new Set(items.filter((i) => ready.has(i.student_id)).map((i) => i.student_id)))} disabled={ready.size === 0}>
              Tick everyone ready for access ({ready.size})
            </Button>
          </div>
          {mark.isSuccess && mark.data.problems.length > 0 && (
            <ul className="space-y-1 text-sm text-amber-700 dark:text-amber-400">
              {mark.data.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
          {mark.isError && <p className="text-sm text-destructive">{errorMessage(mark.error, "Could not update them.")}</p>}
          {grant.isError && <p className="text-sm text-destructive">{errorMessage(grant.error, "Could not grant access.")}</p>}
          {results && (
            <div className="rounded-md border p-3 text-sm">
              <p className="font-medium">
                {results.filter((r) => r.ok).length} granted{results.some((r) => !r.ok) ? `, ${results.filter((r) => !r.ok).length} not` : ""}.
              </p>
              <ul className="mt-1 space-y-0.5 text-xs">
                {results
                  .filter((r) => !r.ok)
                  .map((r) => (
                    <li key={r.student_id}>
                      <span className="font-medium">{r.name}:</span> {r.message}
                    </li>
                  ))}
              </ul>
            </div>
          )}

          <Card>
            <CardContent className="overflow-x-auto p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10" />
                    <TableHead>Student</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Reply</TableHead>
                    <TableHead>Verification</TableHead>
                    <TableHead>Payment</TableHead>
                    <TableHead>LMS</TableHead>
                    <TableHead className="w-20" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((s) => (
                    <TableRow key={s.student_id}>
                      <TableCell>
                        <input type="checkbox" aria-label={`Tick ${s.name}`} checked={picked.has(s.student_id)} onChange={(e) => toggle(s.student_id, e.target.checked)} />
                      </TableCell>
                      <TableCell>
                        <span className="font-medium">{s.name}</span>
                        <span className="block text-xs text-muted-foreground">{s.email}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={stageVariant(s.stage)}>{s.stage_label}</Badge>
                      </TableCell>
                      <TableCell className="text-sm">{OFFER_RESPONSE_LABELS[s.offer_response]}</TableCell>
                      <TableCell className="text-sm">{VERIFICATION_LABELS[s.verification_status]}</TableCell>
                      <TableCell className="text-sm">
                        {PAYMENT_LABELS[s.payment_status]}
                        {s.payment_amount !== null && <span className="block text-xs text-muted-foreground">{s.payment_amount}</span>}
                      </TableCell>
                      <TableCell className="text-sm">{LMS_LABELS[s.lms_status]}</TableCell>
                      <TableCell>
                        <Button size="sm" variant="outline" onClick={() => setOpen(s.student_id)}>
                          Open
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}

      {open && <StudentOnboardingDialog internshipId={internship.id} studentId={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
