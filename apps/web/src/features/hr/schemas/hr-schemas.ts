import { z } from "zod";

export const departmentFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  code: z.string().min(1, "Code is required."),
  parentDepartmentId: z.string().optional().or(z.literal("")),
  headEmployeeId: z.string().optional().or(z.literal("")),
  description: z.string().optional().or(z.literal("")),
});
export type DepartmentFormValues = z.infer<typeof departmentFormSchema>;

export const designationFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  code: z.string().min(1, "Code is required."),
  gradeLevel: z.string().optional().or(z.literal("")),
  description: z.string().optional().or(z.literal("")),
  // What an employee holding this designation is granted beyond the
  // basic employee-portal login every employee gets regardless — see
  // DesignationsCard's role dropdown for why "student"/"super_admin"
  // never appear as options here.
  linkedRoleId: z.string().optional().or(z.literal("")),
  grantsTrainerAccess: z.boolean().optional(),
});
export type DesignationFormValues = z.infer<typeof designationFormSchema>;
