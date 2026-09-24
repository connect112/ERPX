import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useResetPasswordMutation } from "@/features/auth/api/auth-hooks";
import {
  type ResetPasswordFormValues,
  resetPasswordSchema,
} from "@/features/auth/schemas/auth-schemas";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Landing page for the "set your password" link Pentrix-provisioned
 * students receive by email (see ERPX's modules/provisioning — the token
 * here is the same PasswordResetToken machinery the ordinary
 * forgot-password flow already uses, just reframed for a brand-new
 * account's first login). Also reachable from an ordinary forgot-password
 * email, since both flows share one token type and one backend endpoint.
 */
export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const resetMutation = useResetPasswordMutation();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormValues>({ resolver: zodResolver(resetPasswordSchema) });

  const onSubmit = (values: ResetPasswordFormValues) => {
    if (!token) return;
    resetMutation.mutate(
      { token, new_password: values.newPassword },
      { onSuccess: () => navigate("/login", { replace: true }) }
    );
  };

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>Invalid link</CardTitle>
            <CardDescription>
              This password-setup link is missing its token. Please use the link from your email
              again, or request a new one.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link to="/login" className="text-sm text-primary underline-offset-4 hover:underline">
              Back to sign in
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Set your password</CardTitle>
          <CardDescription>Choose a password to activate your ERPX student account.</CardDescription>
        </CardHeader>
        <CardContent>
          {resetMutation.isSuccess ? (
            <p className="text-sm text-muted-foreground">
              Your password has been set. Redirecting to sign in…
            </p>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="newPassword">New password</Label>
                <Input id="newPassword" type="password" {...register("newPassword")} />
                {errors.newPassword && (
                  <p className="text-sm text-destructive">{errors.newPassword.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm password</Label>
                <Input id="confirmPassword" type="password" {...register("confirmPassword")} />
                {errors.confirmPassword && (
                  <p className="text-sm text-destructive">{errors.confirmPassword.message}</p>
                )}
              </div>

              {resetMutation.isError && (
                <p className="text-sm text-destructive">
                  {(resetMutation.error as { response?: { data?: { error?: { message?: string } } } })
                    ?.response?.data?.error?.message ??
                    "This link may have expired. Please request a new one."}
                </p>
              )}

              <Button type="submit" className="w-full" disabled={resetMutation.isPending}>
                {resetMutation.isPending ? "Setting password..." : "Set password"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
