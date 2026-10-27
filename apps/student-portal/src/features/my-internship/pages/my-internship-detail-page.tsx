import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useMyInternshipDetail, useMyInternshipList } from "@/features/my-internship/api/my-internship-api";
import { AssignmentsSection } from "@/features/my-internship/components/assignments-section";
import { AwardsSection } from "@/features/my-internship/components/awards-section";
import { ProjectsSection } from "@/features/my-internship/components/projects-section";
import { ExamsSection } from "@/features/my-internship/components/exams-section";

export function MyInternshipDetailPage() {
  const { internshipId = "" } = useParams();
  const [tab, setTab] = useState("assignments");
  const { data: internship, isLoading, isError } = useMyInternshipDetail(internshipId);
  const { data: all } = useMyInternshipList();

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (isError || !internship) {
    return (
      <div className="space-y-2 p-6">
        <p className="text-sm text-destructive">This internship could not be found, or you do not have access to it.</p>
        <Link to="/my-internship" className="text-sm underline">
          Back to my internships
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        {all && all.length > 1 && (
          <Link to="/my-internship" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            My Internship
          </Link>
        )}
        <h1 className="mt-1 text-2xl font-semibold">{internship.title}</h1>
        {internship.description && <p className="mt-2 max-w-3xl whitespace-pre-wrap text-sm text-muted-foreground">{internship.description}</p>}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="assignments">Assignments</TabsTrigger>
          <TabsTrigger value="projects">Projects</TabsTrigger>
          <TabsTrigger value="exams">Exams</TabsTrigger>
          <TabsTrigger value="awards">Awards</TabsTrigger>
        </TabsList>
        <TabsContent value="assignments">
          <AssignmentsSection internshipId={internshipId} />
        </TabsContent>
        <TabsContent value="projects">
          <ProjectsSection internshipId={internshipId} />
        </TabsContent>
        <TabsContent value="exams">
          <ExamsSection internshipId={internshipId} />
        </TabsContent>
        <TabsContent value="awards">
          <AwardsSection internshipId={internshipId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
