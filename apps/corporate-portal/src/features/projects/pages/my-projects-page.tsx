import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyProjects } from "@/features/projects/api/projects-hooks";

export function MyProjectsPage() {
  const { data: projects, isLoading } = useMyProjects();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">My Projects</h1>
        <p className="text-sm text-muted-foreground">Engagements we're running for your organization.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Projects</CardTitle>
          <CardDescription>VAPT, SOC, consulting, and training engagements.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : projects && projects.length > 0 ? (
            <ul className="divide-y">
              {projects.map((project) => (
                <li key={project.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">{project.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {project.project_code} &middot; {project.project_type.toUpperCase()}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="capitalize">
                      {project.status.replace("_", " ")}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      Started {new Date(project.start_date).toLocaleDateString()}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No projects are running for your organization yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
