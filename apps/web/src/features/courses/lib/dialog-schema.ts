import { z } from "zod";

import { courseFormSchema, courseTypeValues } from "@/features/courses/schemas/course-schemas";

/**
 * The New / Edit Course form: the original course form plus the course type and fee visibility. Kept apart from
 * ``courseFormSchema`` (whose behaviour is pinned by the schema characterization fixture) and built on it, so the regular-course
 * fields validate exactly as before.
 */
export const courseDialogSchema = courseFormSchema
  .extend({
    courseType: z.enum(courseTypeValues),
    showInternshipFee: z.boolean(),
  })
  .refine((v) => v.courseType !== "internship" || !v.price || Number(v.price) === 0, {
    path: ["price"],
    message: "An internship course has no price of its own.",
  });
export type CourseDialogValues = z.infer<typeof courseDialogSchema>;
