import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { institutionsApi, institutionsKeys } from "@/features/institutions/api/institutions-api";
import { errorMessage } from "@/features/institutions/lib/format";
import { useDebounced } from "@/features/institutions/lib/use-debounced";
import { type InternshipStatus, ourInternshipsApi, ourInternshipsKeys } from "@/features/our-internships/api/our-internships-api";
import { AssignmentsTab } from "@/features/our-internships/components/assignments-tab";
import { ExamsTab } from "@/features/our-internships/components/exams-tab";
import { ProjectsTab } from "@/features/our-internships/components/projects-tab";
import { CertificatesTab } from "@/features/our-internships/components/certificates-tab";
import { AwardsTab } from "@/features/our-internships/components/awards-tab";
import { OffersTab } from "@/features/our-internships/components/offers-tab";
import { OnboardingTab } from "@/features/our-internships/components/onboarding-tab";
import { SelectedStudentsTab } from "@/features/our-internships/components/selected-students-tab";
import { StudentWiseView } from "@/features/our-internships/components/student-wise-view";
import { TeamWiseView } from "@/features/our-internships/components/team-wise-view";
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
  const institutions = useQuery({ queryKey: institutionsKeys.list(""), queryFn: () => institutionsApi.list(""), enabled: allScope });
  const events = useQuery({
    queryKey: institutionsKeys.events(institutionId),
    queryFn: () => institutionsApi.events(institutionId),
    enabled: allScope && !!institutionId,
  });
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

  return (
    <div className="space-y-6 p-6">
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
              {institutions.data?.items.map((inst) => (
                <option key={inst.id} value={inst.id}>
                  {inst.name}
                </option>
              ))}
            </select>
            {institutionId && (
              <select aria-label="Filter by event" className={selectClass} value={eventId} onChange={(e) => setEventId(e.target.value)}>
                <option value="">All events</option>
                {events.data?.map((ev) => (
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
          <TabsTrigger value="offers">Offers</TabsTrigger>
          <TabsTrigger value="onboarding">Onboarding</TabsTrigger>
          <TabsTrigger value="exams">Exams</TabsTrigger>
          <TabsTrigger value="assignments">Assignments</TabsTrigger>
          <TabsTrigger value="projects">Projects</TabsTrigger>
          <TabsTrigger value="awards">Awards</TabsTrigger>
          <TabsTrigger value="certificates">Certificates</TabsTrigger>
        </TabsList>
        <TabsContent value="students">
          {performance.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : performance.isError || !board ? (
            <p className="text-sm text-destructive">Could not load the students.</p>
          ) : board.total_students === 0 ? (
            <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">
              No students are registered here yet. Import the registration list on the event page under Institutions.
            </p>
          ) : (
            <StudentWiseView rows={board.students} showInstitution={allScope} pending={select.isPending} onSelect={(ids) => select.mutate(ids)} />
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
        <TabsContent value="offers">
          <OffersTab internshipId={internshipId} />
        </TabsContent>
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
      </Tabs>
    </div>
  );
}
