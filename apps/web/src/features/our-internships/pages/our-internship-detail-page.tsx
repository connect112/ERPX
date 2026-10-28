import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { errorMessage } from "@/features/institutions/lib/format";
import { useDebounced } from "@/features/institutions/lib/use-debounced";
import { type InternshipStatus, ourInternshipsApi, ourInternshipsKeys } from "@/features/our-internships/api/our-internships-api";
import { useMyAccess } from "@/features/our-internships/api/instructors-api";
import { useDestinations } from "@/features/our-internships/api/students-api";
import { AssignmentsTab } from "@/features/our-internships/components/assignments-tab";
import { InstructorsTab } from "@/features/our-internships/components/instructors-tab";
import { ExamsTab } from "@/features/our-internships/components/exams-tab";
import { ProjectsTab } from "@/features/our-internships/components/projects-tab";
import { CertificatesTab } from "@/features/our-internships/components/certificates-tab";
import { AwardsTab } from "@/features/our-internships/components/awards-tab";
import { OfferLettersTab } from "@/features/our-internships/components/offer-letters-tab";
import { OnboardingTab } from "@/features/our-internships/components/onboarding-tab";
import { SelectedStudentsTab } from "@/features/our-internships/components/selected-students-tab";
import { StudentsManager } from "@/features/our-internships/components/students-manager";
import { TeamWiseView } from "@/features/our-internships/components/team-wise-view";
import { InternshipAccessContext, accessEndsText } from "@/features/our-internships/lib/internship-access";
import { statusBadge } from "@/features/our-internships/lib/performance";

const selectClass = "rounded-md border bg-background px-3 py-2 text-sm";

export function OurInternshipDetailPage() {
  const { internshipId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("students");
  const [search, setSearch] = useState("");
  const [institutionId, setInstitutionId] = useState("");
  const [eventId, setEventId] = useState("");
  const q = useDebounced(search.trim());

  const internship = useQuery({ queryKey: ourInternshipsKeys.detail(internshipId), queryFn: () => ourInternshipsApi.get(internshipId) });
  const i = internship.data;
  const allScope = i?.scope === "all";

  // an all-students internship can be narrowed to one institution and one of its events; the others are fixed by its scope
  const destinations = useDestinations(internshipId);
  const institutionOptions = (destinations.data ?? []).map((d) => ({ id: d.institution_id, name: d.institution_name }));
  const eventOptions = destinations.data?.find((d) => d.institution_id === institutionId)?.events ?? [];
  const access = useMyAccess(internshipId);
  const canDelete = access.data?.can_delete ?? false;
  const isAdmin = access.data?.role === "admin" && canDelete;
  const performance = useQuery({
    queryKey: ourInternshipsKeys.performance(internshipId, institutionId, eventId, q),
    queryFn: () => ourInternshipsApi.performance(internshipId, { institutionId, eventId, q }),
    enabled: !!i,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });
  const select = useMutation({
    mutationFn: (studentIds: string[]) => ourInternshipsApi.select(internshipId, studentIds),
    onSuccess: refresh,
  });
  const setStatus = useMutation({ mutationFn: (status: InternshipStatus) => ourInternshipsApi.update(internshipId, { status }), onSuccess: refresh });
  const remove = useMutation({
    mutationFn: () => ourInternshipsApi.remove(internshipId),
    onSuccess: () => {
      void refresh();
      navigate("/our-internships");
    },
  });

  if (internship.isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (internship.isError || !i) {
    return (
      <div className="space-y-3 p-6">
        <p className="text-sm text-destructive">Could not load this internship.</p>
        <Button variant="outline" onClick={() => navigate("/our-internships")}>
          Back to internships
        </Button>
      </div>
    );
  }

  const board = performance.data;
  const status = statusBadge[i.status];

  const accessValue = { role: access.data?.role ?? "admin", canDelete: access.data ? access.data.can_delete : true, accessUntil: access.data?.access_until ?? null } as const;
  const endsText = access.data?.role === "instructor" ? accessEndsText(access.data.access_until) : null;

  return (
    <InternshipAccessContext.Provider value={accessValue}>
    <div className="space-y-6 p-6">
      {access.data?.role === "instructor" && (
        <p className="rounded-md border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200">
          You are an instructor on this internship. You can add, edit, view, mark and validate everything here, but not delete.
          {endsText ? ` ${endsText}.` : ""}
        </p>
      )}
      <div>
        <Link to="/our-internships" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Our Internships
        </Link>
        <div className="mt-2 flex items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold">{i.title}</h1>
              <Badge variant={status.variant}>{status.label}</Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              Selecting from {allScope ? "all students" : `${i.institution_name}${i.event_name ? ` · ${i.event_name}` : " · all events"}`} · {i.selected_count} selected
            </p>
            {i.description && <p className="mt-2 max-w-3xl whitespace-pre-wrap text-sm">{i.description}</p>}
          </div>
          <div className="flex items-center gap-2">
            <select
              aria-label="Internship status"
              className={selectClass}
              value={i.status}
              onChange={(e) => setStatus.mutate(e.target.value as InternshipStatus)}
            >
              {Object.entries(statusBadge).map(([value, { label }]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            {canDelete && (
              <Button
                variant="outline"
                disabled={remove.isPending}
                onClick={() => {
                  if (window.confirm(`Delete "${i.title}" and its selected list? This cannot be undone.`)) remove.mutate();
                }}
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </Button>
            )}
          </div>
        </div>
        {(setStatus.isError || remove.isError) && <p className="mt-2 text-sm text-destructive">{errorMessage(setStatus.error ?? remove.error, "Could not save that change.")}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Input aria-label="Search students and teams" className="w-72" placeholder="Search name, email or team" value={search} onChange={(e) => setSearch(e.target.value)} />
        {allScope && (
          <>
            <select
              aria-label="Filter by institution"
              className={selectClass}
              value={institutionId}
              onChange={(e) => {
                setInstitutionId(e.target.value);
                setEventId("");
              }}
            >
              <option value="">All institutions</option>
              {institutionOptions.map((inst) => (
                <option key={inst.id} value={inst.id}>
                  {inst.name}
                </option>
              ))}
            </select>
            {institutionId && (
              <select aria-label="Filter by event" className={selectClass} value={eventId} onChange={(e) => setEventId(e.target.value)}>
                <option value="">All events</option>
                {eventOptions.map((ev) => (
                  <option key={ev.id} value={ev.id}>
                    {ev.name}
                  </option>
                ))}
              </select>
            )}
          </>
        )}
      </div>

      {select.isError && <p className="text-sm text-destructive">{errorMessage(select.error, "Could not add them to the selected list.")}</p>}
      {select.isSuccess && <p className="text-sm text-emerald-700 dark:text-emerald-400">{select.data.message}</p>}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="students">Students{board ? ` (${board.students.length})` : ""}</TabsTrigger>
          <TabsTrigger value="teams">Teams{board ? ` (${board.teams.filter((t) => t.team_id).length})` : ""}</TabsTrigger>
          <TabsTrigger value="selected">Selected ({i.selected_count})</TabsTrigger>
          {isAdmin && <TabsTrigger value="offers">Offer letters</TabsTrigger>}
          <TabsTrigger value="onboarding">Onboarding</TabsTrigger>
          <TabsTrigger value="exams">Exams</TabsTrigger>
          <TabsTrigger value="assignments">Assignments</TabsTrigger>
          <TabsTrigger value="projects">Projects</TabsTrigger>
          <TabsTrigger value="awards">Awards</TabsTrigger>
          <TabsTrigger value="certificates">Certificates</TabsTrigger>
          {isAdmin && <TabsTrigger value="instructors">Instructors</TabsTrigger>}
        </TabsList>
        <TabsContent value="students">
          {performance.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : performance.isError || !board ? (
            <p className="text-sm text-destructive">Could not load the students.</p>
          ) : (
            <StudentsManager
              internshipId={internshipId}
              rows={board.students}
              showInstitution={allScope}
              pending={select.isPending}
              canManage
              onSelect={(ids) => select.mutate(ids)}
            />
          )}
        </TabsContent>
        <TabsContent value="teams">
          {performance.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : board ? (
            <TeamWiseView teams={board.teams} showInstitution={allScope} pending={select.isPending} onSelect={(ids) => select.mutate(ids)} />
          ) : null}
        </TabsContent>
        <TabsContent value="selected">
          <SelectedStudentsTab internshipId={internshipId} />
        </TabsContent>
        {isAdmin && (
          // the signature, the official wording and what is emailed to students are for administrators only
          <TabsContent value="offers">
            <OfferLettersTab internshipId={internshipId} />
          </TabsContent>
        )}
        <TabsContent value="onboarding">
          <OnboardingTab internship={i} />
        </TabsContent>
        <TabsContent value="exams">
          <ExamsTab internshipId={internshipId} canManage />
        </TabsContent>
        <TabsContent value="assignments">
          <AssignmentsTab internshipId={internshipId} canManage />
        </TabsContent>
        <TabsContent value="projects">
          <ProjectsTab internshipId={internshipId} canManage />
        </TabsContent>
        <TabsContent value="awards">
          <AwardsTab internshipId={internshipId} canManage />
        </TabsContent>
        <TabsContent value="certificates">
          <CertificatesTab internshipId={internshipId} canManage />
        </TabsContent>
        {isAdmin && (
          <TabsContent value="instructors">
            <InstructorsTab internshipId={internshipId} />
          </TabsContent>
        )}
      </Tabs>
    </div>
    </InternshipAccessContext.Provider>
  );
}
