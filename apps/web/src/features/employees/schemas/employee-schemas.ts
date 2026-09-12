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

// Required on every field except reportingManagerId (the top of an org
// chart reports to no one) and notes (inherently free-form) — mirrors
// modules/employees/schemas.py's EmployeeCreateRequest exactly, so a
// submission that passes this validation never bounces off the backend
// with a 422 for a missing field. See that file's own docstring for the
// full reasoning, including why branch_id/address_line2 (not in this form
// at all) are excluded from that list too.
// employeeCode is deliberately absent: it's system-generated
// (EMP-00001, EMP-00002, ...) by EmployeeRepository.create, mirroring
// modules/employees/schemas.py's EmployeeCreateRequest — an admin never
// types or sees a scheme to collide with.
export const employeeFormSchema = z.object({
  fullName: z.string().min(2, "Full name is required."),
  departmentId: z.string().min(1, "Department is required."),
  designationId: z.string().min(1, "Designation is required."),
  reportingManagerId: z.string().optional().or(z.literal("")),
  email: z.string().min(1, "Email is required.").email("Enter a valid email address."),
  phone: z.string().min(1, "Phone is required."),
  // z.string() rather than z.enum(genderValues) here — unlike
  // employmentType (which always has a real default so the Select is
  // never blank), this Select starts unselected like departmentId/
  // designationId above, and needs "" as a valid (if invalid-on-submit)
  // intermediate form value for that blank state to type-check.
  gender: z
    .string()
    .min(1, "Gender is required.")
    .refine((value) => (genderValues as readonly string[]).includes(value), {
      message: "Select a valid gender.",
    }),
  dateOfBirth: z.string().min(1, "Date of birth is required."),
  addressLine1: z.string().min(1, "Address is required."),
  city: z.string().min(1, "City is required."),
  state: z.string().min(1, "State is required."),
  country: z.string().min(1, "Country is required."),
  postalCode: z.string().min(1, "Postal code is required."),
  emergencyContactName: z.string().min(1, "Emergency contact name is required."),
  emergencyContactPhone: z.string().min(1, "Emergency contact phone is required."),
  employmentType: z.enum(employmentTypeValues),
  dateOfJoining: z.string().min(1, "Date of joining is required."),
  notes: z.string().optional().or(z.literal("")),
});
export type EmployeeFormValues = z.infer<typeof employeeFormSchema>;
