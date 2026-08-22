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

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const mutation = useResetPasswordMutation();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormValues>({ resolver: zodResolver(resetPasswordSchema) });

  const onSubmit = (values: ResetPasswordFormValues) => {
    if (!token) return;
    mutation.mutate(
      { token, newPassword: values.password },
      { onSuccess: () => navigate("/login") }
    );
  };

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>Invalid link</CardTitle>
            <CardDescription>
              This password reset link is missing its token. Request a new one.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link to="/forgot-password">
              <Button className="w-full">Request new link</Button>
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
          <CardTitle>Choose a new password</CardTitle>
          <CardDescription>Enter and confirm your new password below.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="password" required>New password</Label>
              <Input id="password" type="password" {...register("password")} />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword" required>Confirm new password</Label>
              <Input id="confirmPassword" type="password" {...register("confirmPassword")} />
              {errors.confirmPassword && (
                <p className="text-sm text-destructive">{errors.confirmPassword.message}</p>
              )}
            </div>
            {mutation.isError && (
              <p className="text-sm text-destructive">
                {(mutation.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ??
                  "This link may have expired. Please request a new one."}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? "Resetting..." : "Reset password"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
