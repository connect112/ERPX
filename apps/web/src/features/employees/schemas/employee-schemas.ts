import { z } from "zod";

export const employmentTypeValues = ["full_time", "part_time", "contract", "intern", "consultant"] as const;
export type EmploymentType = (typeof employmentTypeValues)[number];

export const employmentTypeLabels: Record<EmploymentType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  intern: "Intern",
  consultant: "Consultant",
};

export const employmentStatusValues = [
  "active",
  "on_leave",
  "suspended",
  "resigned",
  "terminated",
  "retired",
] as const;
export type EmploymentStatus = (typeof employmentStatusValues)[number];

export const employmentStatusLabels: Record<EmploymentStatus, string> = {
  active: "Active",
  on_leave: "On Leave",
  suspended: "Suspended",
  resigned: "Resigned",
  terminated: "Terminated",
  retired: "Retired",
};

export const genderValues = ["male", "female", "other", "prefer_not_to_say"] as const;
export type Gender = (typeof genderValues)[number];

export const genderLabels: Record<Gender, string> = {
  male: "Male",
  female: "Female",
  other: "Other",
  prefer_not_to_say: "Prefer not to say",
};

export const employeeFormSchema = z.object({
  employeeCode: z.string().min(1, "Code is required."),
  fullName: z.string().min(2, "Full name is required."),
  departmentId: z.string().optional().or(z.literal("")),
  designationId: z.string().optional().or(z.literal("")),
  reportingManagerId: z.string().optional().or(z.literal("")),
  email: z.string().email("Enter a valid email address.").optional().or(z.literal("")),
  phone: z.string().optional().or(z.literal("")),
  gender: z.union([z.enum(genderValues), z.literal("")]).optional(),
  dateOfBirth: z.string().optional().or(z.literal("")),
  addressLine1: z.string().optional().or(z.literal("")),
  city: z.string().optional().or(z.literal("")),
  state: z.string().optional().or(z.literal("")),
  country: z.string().optional().or(z.literal("")),
  postalCode: z.string().optional().or(z.literal("")),
  emergencyContactName: z.string().optional().or(z.literal("")),
  emergencyContactPhone: z.string().optional().or(z.literal("")),
  employmentType: z.enum(employmentTypeValues),
  dateOfJoining: z.string().min(1, "Date of joining is required."),
  notes: z.string().optional().or(z.literal("")),
});
export type EmployeeFormValues = z.infer<typeof employeeFormSchema>;
