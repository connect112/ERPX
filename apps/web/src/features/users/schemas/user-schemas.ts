import { z } from "zod";

export const genderValues = ["male", "female", "other", "prefer_not_to_say"] as const;
export type Gender = (typeof genderValues)[number];

export const genderLabels: Record<Gender, string> = {
  male: "Male",
  female: "Female",
  other: "Other",
  prefer_not_to_say: "Prefer not to say",
};

export const userStatusValues = ["pending_verification", "active", "suspended", "deactivated"] as const;
export type UserStatus = (typeof userStatusValues)[number];

export const userStatusLabels: Record<UserStatus, string> = {
  pending_verification: "Pending Verification",
  active: "Active",
  suspended: "Suspended",
  deactivated: "Deactivated",
};

const passwordSchema = z
  .string()
  .min(8, "Password must be at least 8 characters.")
  .regex(/[A-Z]/, "Password must include an uppercase letter.")
  .regex(/[a-z]/, "Password must include a lowercase letter.")
  .regex(/[0-9]/, "Password must include a digit.")
  .regex(/[^A-Za-z0-9]/, "Password must include a special character.");

export const createUserFormSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: passwordSchema,
  fullName: z.string().min(2, "Full name is required."),
  phoneNumber: z.string().optional().or(z.literal("")),
  branchId: z.string().optional().or(z.literal("")),
  employeeCode: z.string().optional().or(z.literal("")),
  designation: z.string().optional().or(z.literal("")),
  department: z.string().optional().or(z.literal("")),
  gender: z.union([z.enum(genderValues), z.literal("")]).optional(),
});
export type CreateUserFormValues = z.infer<typeof createUserFormSchema>;

export const userProfileFormSchema = z.object({
  branchId: z.string().optional().or(z.literal("")),
  employeeCode: z.string().optional().or(z.literal("")),
  designation: z.string().optional().or(z.literal("")),
  department: z.string().optional().or(z.literal("")),
  gender: z.union([z.enum(genderValues), z.literal("")]).optional(),
  dateOfBirth: z.string().optional().or(z.literal("")),
  dateOfJoining: z.string().optional().or(z.literal("")),
  addressLine1: z.string().optional().or(z.literal("")),
  city: z.string().optional().or(z.literal("")),
  state: z.string().optional().or(z.literal("")),
  country: z.string().optional().or(z.literal("")),
  postalCode: z.string().optional().or(z.literal("")),
});
export type UserProfileFormValues = z.infer<typeof userProfileFormSchema>;
