import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCategories } from "@/features/courses/categories/api/categories-hooks";
import { useCoursesList } from "@/features/courses/api/courses-hooks";
import { CourseFormDialog } from "@/features/courses/components/course-form-dialog";
import { CourseStatusBadge } from "@/features/courses/components/course-status-badge";
import { courseLevelLabels } from "@/features/courses/schemas/course-schemas";

const PAGE_SIZE = 20;

export function CoursesListPage() {
  const navigate = useNavigate();
  const { data: categories } = useCategories();
  const [categoryId, setCategoryId] = useState<string>("all");
  const [publishedFilter, setPublishedFilter] = useState<string>("all");
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useCoursesList({
    category_id: categoryId === "all" ? undefined : categoryId,
    is_published: publishedFilter === "all" ? undefined : publishedFilter === "published",
    skip,
    limit: PAGE_SIZE,
  });

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const categoryName = (id: string | null) => categories?.find((c) => c.id === id)?.name ?? "—";

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Courses</h1>
          <p className="mt-1 text-muted-foreground">Build and publish your course catalog.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate("/courses/categories")}>
            Categories
          </Button>
          <Button variant="outline" onClick={() => navigate("/courses/learning-paths")}>
            Learning Paths
          </Button>
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" />
            New Course
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Select
              value={categoryId}
              onValueChange={(value) => {
                setCategoryId(value);
                setSkip(0);
              }}
            >
              <SelectTrigger className="sm:w-56">
                <SelectValue placeholder="All categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {categories?.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={publishedFilter}
              onValueChange={(value) => {
                setPublishedFilter(value);
                setSkip(0);
              }}
            >
              <SelectTrigger className="sm:w-48">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="published">Published</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load courses.</p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No courses found. Create your first course to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Level</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((course) => (
                  <TableRow
                    key={course.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/courses/${course.id}`)}
                  >
                    <TableCell className="font-medium">{course.title}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {categoryName(course.category_id)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {courseLevelLabels[course.level]}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {course.price > 0 ? `₹${course.price}` : "Free"}
                    </TableCell>
                    <TableCell>
                      <CourseStatusBadge isPublished={course.is_published} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} courses)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip + PAGE_SIZE >= total}
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <CourseFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
