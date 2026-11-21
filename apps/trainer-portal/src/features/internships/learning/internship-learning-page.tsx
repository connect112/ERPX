import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { learningApi, useQ, key } from "@/features/internships/learning/api";
import { ActivityTab, DiscussionsTab } from "@/features/internships/learning/activity-tabs";
import { EvaluationsTab, ProjectsTab } from "@/features/internships/learning/evaluations-tab";

function Curriculum({ courseId }: { courseId: string | null }) {
  const chapters = useQ(key("chapters", courseId ?? ""), () => learningApi.chapters(courseId!), !!courseId);
  if (!courseId) return <p className="text-sm text-muted-foreground">No LMS course is linked to this internship yet.</p>;
  if (chapters.isLoading) return <Skeleton className="h-24 w-full" />;
  if (chapters.isError) return <p className="text-sm text-destructive">Could not load the curriculum.</p>;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Curriculum</CardTitle>
        <p className="text-xs text-muted-foreground">You can read the course's curriculum here. Editing it needs the course permission, which managing an internship does not include.</p>
      </CardHeader>
      <CardContent className="space-y-2">
        {(chapters.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">This course has no chapters yet.</p>}
        {chapters.data?.sort((a, b) => a.order_index - b.order_index).map((c) => <ChapterItem key={c.id} courseId={courseId} id={c.id} title={`${c.order_index}. ${c.title}`} />)}
      </CardContent>
    </Card>
  );
}

function LessonFiles({ courseId, chapterId, lessonId }: { courseId: string; chapterId: string; lessonId: string }) {
  const files = useQ(key("resources", lessonId), () => learningApi.resources(courseId, chapterId, lessonId));
  if (!files.data || files.data.length === 0) return null;
  const open = async (id: string) => {
    const { url } = await learningApi.resourceLink(courseId, chapterId, lessonId, id);
    window.open(url, "_blank", "noopener,noreferrer");
  };
  return (
    <ul className="ml-4 list-none text-xs">
      {files.data.map((r) => (
        <li key={r.id}>
          {r.is_upload ? (
            <button type="button" className="text-primary hover:underline" onClick={() => void open(r.id)}>
              {r.title} ({r.original_filename})
            </button>
          ) : (
            <a className="text-primary hover:underline" href={r.file_url} target="_blank" rel="noreferrer">
              {r.title}
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}

function ChapterItem({ courseId, id, title }: { courseId: string; id: string; title: string }) {
  const lessons = useQ(key("lessons", id), () => learningApi.lessons(courseId, id));
  return (
    <div className="rounded-md border p-3">
      <p className="text-sm font-medium">{title}</p>
      <ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">
        {(lessons.data ?? []).sort((a, b) => a.order_index - b.order_index).map((l) => (
          <li key={l.id}>
            {l.title} <span className="text-xs">({l.content_type})</span>
            <LessonFiles courseId={courseId} chapterId={id} lessonId={l.id} />
          </li>
        ))}
        {lessons.data?.length === 0 && <li className="list-none text-xs">No lessons yet.</li>}
      </ul>
    </div>
  );
}

function Enrollments({ internshipId }: { internshipId: string }) {
  const rows = useQ(key("enrollments", internshipId), () => learningApi.enrollments(internshipId));
  if (rows.isLoading) return <Skeleton className="h-24 w-full" />;
  if (rows.isError) return <p className="text-sm text-destructive">Could not load the enrollments.</p>;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Students and their LMS access</CardTitle>
        <p className="text-xs text-muted-foreground">Access is granted and withdrawn by the internship administrators. You can see who has it and how they are progressing.</p>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Student</TableHead>
              <TableHead>LMS access</TableHead>
              <TableHead>Enrollment</TableHead>
              <TableHead>Progress</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.data?.map((r) => (
              <TableRow key={r.selection_id}>
                <TableCell>
                  <div className="font-medium">{r.name}</div>
                  <div className="text-xs text-muted-foreground">{r.email}</div>
                </TableCell>
                <TableCell><Badge variant={r.lms_status === "granted" ? "success" : r.lms_status === "revoked" ? "warning" : "secondary"}>{r.lms_status.replace("_", " ")}</Badge></TableCell>
                <TableCell className="text-sm capitalize">{r.enrollment_status ?? "—"}{r.provenance === "independent" ? " (independent)" : ""}</TableCell>
                <TableCell className="text-sm">{r.progress_percent != null ? `${r.progress_percent}%` : "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

/** An instructor's Learning workspace for one assigned internship: the same seven tabs as the administrator site, working on the same records. */
export function InternshipLearningPage() {
  const { internshipId = "" } = useParams<{ internshipId: string }>();
  const ctx = useQ(key("context", internshipId), () => learningApi.context(internshipId));
  const [tab, setTab] = useState("curriculum");

  if (ctx.isLoading) return <div className="p-6"><Skeleton className="h-40 w-full" /></div>;
  if (ctx.isError || !ctx.data) {
    return (
      <div className="space-y-3 p-6">
        <Link to="/internships" className="text-sm text-muted-foreground hover:text-foreground">← My Internships</Link>
        <p className="text-sm text-destructive" data-testid="learning-denied">You do not have access to this internship, or your access period has ended.</p>
      </div>
    );
  }
  const internship = ctx.data.internships[0];
  const courseId = ctx.data.course?.id ?? null;
  const canManage = !!internship?.can_manage;

  return (
    <div className="space-y-4 p-6" data-testid="trainer-learning">
      <div>
        <Link to="/internships" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          My Internships
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">{internship?.title}</h1>
        <p className="text-sm text-muted-foreground">
          Learning{ctx.data.course ? ` · course: ${ctx.data.course.title}` : ""}. You can add, edit, mark and review, but not delete.
        </p>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="h-auto max-w-full flex-wrap justify-start">
          {ctx.data.tabs.map((t) => (
            <TabsTrigger key={t.key} value={t.key} data-testid={`learning-tab-${t.key}`}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="curriculum"><Curriculum courseId={courseId} /></TabsContent>
        <TabsContent value="enrollments"><Enrollments internshipId={internshipId} /></TabsContent>
        <TabsContent value="evaluations"><EvaluationsTab internshipId={internshipId} courseId={courseId} canManage={canManage} /></TabsContent>
        <TabsContent value="projects"><ProjectsTab internshipId={internshipId} canManage={canManage} /></TabsContent>
        <TabsContent value="discussions"><DiscussionsTab internshipId={internshipId} courseId={courseId} /></TabsContent>
        <TabsContent value="practicals"><ActivityTab kind="practicals" internshipId={internshipId} courseId={courseId} canManage={canManage} /></TabsContent>
        <TabsContent value="viva"><ActivityTab kind="viva" internshipId={internshipId} courseId={courseId} canManage={canManage} /></TabsContent>
      </Tabs>
    </div>
  );
}
