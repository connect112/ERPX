import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
  otpCode: z.string().optional(),
});
export type LoginFormValues = z.infer<typeof loginSchema>;

// Mirrors modules/authentication/schemas.py's _validate_password_strength
// exactly, so a form error surfaces client-side instead of only after a
// round trip to the API.
const passwordSchema = z
  .string()
  .min(8, "Password must be at least 8 characters long.")
  .regex(/[A-Z]/, "Password must contain at least one uppercase letter.")
  .regex(/[a-z]/, "Password must contain at least one lowercase letter.")
  .regex(/\d/, "Password must contain at least one digit.")
  .regex(/[^A-Za-z0-9]/, "Password must contain at least one special character.");

export const resetPasswordSchema = z
  .object({
    newPassword: passwordSchema,
    confirmPassword: z.string(),
  })
  .refine((values) => values.newPassword === values.confirmPassword, {
    message: "Passwords do not match.",
    path: ["confirmPassword"],
  });
export type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

// Mirrors apps/web/src/features/employees/schemas/employee-schemas.ts's
// genderValues/genderLabels exactly — kept as its own copy here (not a
// shared package) since this is the only place the employee-portal needs
// them, same reasoning as passwordSchema's duplication above.
export const genderValues = ["male", "female", "other", "prefer_not_to_say"] as const;
export type Gender = (typeof genderValues)[number];
export const genderLabels: Record<Gender, string> = {
  male: "Male",
  female: "Female",
  other: "Other",
  prefer_not_to_say: "Prefer not to say",
};

// The form an invited employee lands on from their invite email: sets
// their password (same rules as resetPasswordSchema above) AND fills in
// the personal-detail fields modules/employees/schemas.py's
// EmployeeCreateRequest deliberately never collects from the admin —
// see EmployeeCompleteRegistrationRequest's own docstring for why.
export const completeRegistrationSchema = z
  .object({
    newPassword: passwordSchema,
    confirmPassword: z.string(),
    phone: z.string().min(1, "Phone is required."),
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
  })
  .refine((values) => values.newPassword === values.confirmPassword, {
    message: "Passwords do not match.",
    path: ["confirmPassword"],
  });
export type CompleteRegistrationFormValues = z.infer<typeof completeRegistrationSchema>;
