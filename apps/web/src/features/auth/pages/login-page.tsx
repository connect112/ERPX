import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";

import { isTwoFactorRequired } from "@/features/auth/api/auth-api";
import { useLoginMutation } from "@/features/auth/api/auth-hooks";
import { type LoginFormValues, loginSchema } from "@/features/auth/schemas/auth-schemas";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function LoginPage() {
  const navigate = useNavigate();
  const loginMutation = useLoginMutation();
  const [needsTwoFactor, setNeedsTwoFactor] = useState(false);

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = (values: LoginFormValues) => {
    loginMutation.mutate(
      { email: values.email, password: values.password, otp_code: values.otpCode },
      {
        onSuccess: (data) => {
          if (isTwoFactorRequired(data)) {
            setNeedsTwoFactor(true);
            return;
          }
          navigate("/");
        },
      }
    );
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Sign in to ERPX</CardTitle>
          <CardDescription>Enter your credentials to access your account.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email" required>Email</Label>
              <Input id="email" type="email" placeholder="you@company.com" {...register("email")} />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" required>Password</Label>
              <Input id="password" type="password" {...register("password")} />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>

            {needsTwoFactor && (
              <div className="space-y-2">
                <Label htmlFor="otpCode">Authenticator code</Label>
                <Input
                  id="otpCode"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="123456"
                  {...register("otpCode")}
                />
                <p className="text-xs text-muted-foreground">
                  Enter the 6-digit code from your authenticator app.
                </p>
              </div>
            )}

            {loginMutation.isError && !needsTwoFactor && (
              <p className="text-sm text-destructive">
                {(loginMutation.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
            {loginMutation.isError && needsTwoFactor && getValues("otpCode") && (
              <p className="text-sm text-destructive">Invalid code. Please try again.</p>
            )}

            <Button type="submit" className="w-full" disabled={loginMutation.isPending}>
              {loginMutation.isPending
                ? "Signing in..."
                : needsTwoFactor
                  ? "Verify and sign in"
                  : "Sign in"}
            </Button>

            <div className="flex items-center justify-between text-sm">
              <Link to="/forgot-password" className="text-primary hover:underline">
                Forgot password?
              </Link>
              <Link to="/register" className="text-primary hover:underline">
                Create account
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
