import { z } from "zod";

export const studentStatusValues = [
  "active",
  "on_hold",
  "completed",
  "dropped",
  "transferred",
] as const;
export type StudentStatus = (typeof studentStatusValues)[number];

export const studentStatusLabels: Record<StudentStatus, string> = {
  active: "Active",
  on_hold: "On Hold",
  completed: "Completed",
  dropped: "Dropped",
  transferred: "Transferred",
};

export const genderValues = ["male", "female", "other", "prefer_not_to_say"] as const;
export type Gender = (typeof genderValues)[number];

export const genderLabels: Record<Gender, string> = {
  male: "Male",
  female: "Female",
  other: "Other",
  prefer_not_to_say: "Prefer not to say",
};

export const studentFormSchema = z.object({
  fullName: z.string().min(2, "Full name is required."),
  email: z.string().email("Enter a valid email address.").optional().or(z.literal("")),
  phone: z.string().optional().or(z.literal("")),
  gender: z.union([z.enum(genderValues), z.literal("")]).optional(),
  dateOfBirth: z.string().optional().or(z.literal("")),
  guardianName: z.string().optional().or(z.literal("")),
  guardianPhone: z.string().optional().or(z.literal("")),
  addressLine1: z.string().optional().or(z.literal("")),
  addressLine2: z.string().optional().or(z.literal("")),
  city: z.string().optional().or(z.literal("")),
  state: z.string().optional().or(z.literal("")),
  country: z.string().optional().or(z.literal("")),
  postalCode: z.string().optional().or(z.literal("")),
  courseName: z.string().min(2, "Course name is required."),
  batchName: z.string().optional().or(z.literal("")),
  enrollmentDate: z.string().min(1, "Enrollment date is required."),
  notes: z.string().optional().or(z.literal("")),
});
export type StudentFormValues = z.infer<typeof studentFormSchema>;
