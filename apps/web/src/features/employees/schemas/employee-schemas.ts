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

// Required: only what HR actually knows on day one — mirrors
// modules/employees/schemas.py's EmployeeCreateRequest exactly (full
// name, department, designation, a login-capable email, date of
// joining), so a submission that passes this validation never bounces
// off the backend with a 422 for a missing field. reportingManagerId is
// optional for its own reason (the top of an org chart reports to no
// one); notes is inherently free-form.
//
// Every personal field below (phone/gender/DOB/address/emergency
// contact) is deliberately optional here too, NOT because they're
// unimportant, but because the admin never fills them in at all anymore
// — see EmployeeCompleteRegistrationRequest in that same backend file.
// The employee-portal's own complete-registration page collects these
// from the employee themselves, in the same step as setting their
// password, after clicking their invite email. This form only ever
// shows them (still editable, never required) when editing an existing
// record — see employee-form-dialog.tsx's `isEditing` gating.
//
// employeeCode is deliberately absent: it's system-generated
// (EMP-00001, EMP-00002, ...) by EmployeeRepository.create — an admin
// never types or sees a scheme to collide with.
export const employeeFormSchema = z.object({
  fullName: z.string().min(2, "Full name is required."),
  departmentId: z.string().min(1, "Department is required."),
  designationId: z.string().min(1, "Designation is required."),
  reportingManagerId: z.string().optional().or(z.literal("")),
  email: z.string().min(1, "Email is required.").email("Enter a valid email address."),
  phone: z.string().optional().or(z.literal("")),
  gender: z
    .string()
    .optional()
    .or(z.literal(""))
    .refine((value) => !value || (genderValues as readonly string[]).includes(value), {
      message: "Select a valid gender.",
    }),
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
