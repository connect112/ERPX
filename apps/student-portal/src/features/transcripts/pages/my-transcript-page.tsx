import { Award, GraduationCap } from "lucide-react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyTranscript } from "@/features/transcripts/api/transcripts-hooks";
import type { CourseTranscriptEntry } from "@/features/transcripts/api/transcripts-api";

const resultStatusVariants: Record<string, BadgeProps["variant"]> = {
  pass: "success",
  fail: "destructive",
  incomplete: "secondary",
};

function CourseEntry({ entry }: { entry: CourseTranscriptEntry }) {
  return (
    <Card>
      <CardContent className="space-y-3 p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="font-medium">{entry.course_title}</p>
            <p className="text-xs text-muted-foreground">
              Enrolled {new Date(entry.enrolled_on).toLocaleDateString()}
            </p>
          </div>
          <Badge variant={entry.enrollment_status === "completed" ? "success" : "secondary"}>
            {entry.enrollment_status}
          </Badge>
        </div>

        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>{entry.percent_complete}% complete</span>
        </div>

        {entry.result && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">
              Result: {entry.result.overall_score}/{entry.result.overall_total} (
              {entry.result.overall_percentage}%)
            </span>
            <Badge variant={resultStatusVariants[entry.result.overall_status]}>
              {entry.result.overall_status}
            </Badge>
          </div>
        )}

        {entry.certificate_number && (
          <div className="flex items-center gap-2 text-sm text-primary">
            <Award className="h-4 w-4" />
            <span>Certificate {entry.certificate_number}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function MyTranscriptPage() {
  const { data, isLoading, isError } = useMyTranscript();

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">My Transcript</h1>
        <p className="mt-1 text-muted-foreground">
          A summary of every course you've enrolled in, your progress, results, and certificates.
        </p>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      )}

      {isError && <p className="text-sm text-destructive">Failed to load transcript.</p>}

      {data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card>
              <CardContent className="flex items-center gap-4 p-6">
                <GraduationCap className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-2xl font-semibold tracking-tight">{data.total_courses}</p>
                  <p className="text-sm text-muted-foreground">Courses enrolled</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-4 p-6">
                <GraduationCap className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-2xl font-semibold tracking-tight">{data.completed_courses}</p>
                  <p className="text-sm text-muted-foreground">Courses completed</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-4 p-6">
                <Award className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-2xl font-semibold tracking-tight">{data.certificates_earned}</p>
                  <p className="text-sm text-muted-foreground">Certificates earned</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {data.courses.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No enrollments yet.
            </p>
          ) : (
            <div className="space-y-3">
              {data.courses.map((entry) => (
                <CourseEntry key={entry.course_id} entry={entry} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
