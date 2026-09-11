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
