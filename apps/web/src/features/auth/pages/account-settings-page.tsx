import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useChangePasswordMutation,
  useCurrentUser,
} from "@/features/auth/api/auth-hooks";
import { TwoFactorDisableDialog } from "@/features/auth/components/two-factor-disable-dialog";
import { TwoFactorSetupDialog } from "@/features/auth/components/two-factor-setup-dialog";
import {
  type ChangePasswordFormValues,
  changePasswordSchema,
} from "@/features/auth/schemas/auth-schemas";

function ProfileCard() {
  const { data: user, isLoading } = useCurrentUser();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Profile</CardTitle>
        <CardDescription>Your account details.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-20 w-full" />}
        {user && (
          <>
            <div className="flex items-center justify-between border-b py-2 last:border-0">
              <span className="text-sm text-muted-foreground">Name</span>
              <span className="text-sm font-medium">{user.full_name}</span>
            </div>
            <div className="flex items-center justify-between border-b py-2 last:border-0">
              <span className="text-sm text-muted-foreground">Email</span>
              <span className="flex items-center gap-2 text-sm font-medium">
                {user.email}
                <Badge variant={user.is_email_verified ? "success" : "warning"}>
                  {user.is_email_verified ? "Verified" : "Unverified"}
                </Badge>
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-sm text-muted-foreground">Member since</span>
              <span className="text-sm font-medium">
                {new Date(user.created_at).toLocaleDateString()}
              </span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ChangePasswordCard() {
  const [successMessage, setSuccessMessage] = useState(false);
  const changePassword = useChangePasswordMutation();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ChangePasswordFormValues>({ resolver: zodResolver(changePasswordSchema) });

  const onSubmit = (values: ChangePasswordFormValues) => {
    setSuccessMessage(false);
    changePassword.mutate(
      { currentPassword: values.currentPassword, newPassword: values.newPassword },
      {
        onSuccess: () => {
          setSuccessMessage(true);
          reset();
        },
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Change password</CardTitle>
        <CardDescription>Update the password used to sign in.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="currentPassword" required>Current password</Label>
            <Input id="currentPassword" type="password" {...register("currentPassword")} />
            {errors.currentPassword && (
              <p className="text-sm text-destructive">{errors.currentPassword.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="newPassword" required>New password</Label>
            <Input id="newPassword" type="password" {...register("newPassword")} />
            {errors.newPassword && (
              <p className="text-sm text-destructive">{errors.newPassword.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirmPassword" required>Confirm new password</Label>
            <Input id="confirmPassword" type="password" {...register("confirmPassword")} />
            {errors.confirmPassword && (
              <p className="text-sm text-destructive">{errors.confirmPassword.message}</p>
            )}
          </div>

          {changePassword.isError && (
            <p className="text-sm text-destructive">
              {(changePassword.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Could not change your password."}
            </p>
          )}
          {successMessage && (
            <p className="text-sm text-emerald-600 dark:text-emerald-400">
              Password changed successfully.
            </p>
          )}

          <Button type="submit" disabled={changePassword.isPending}>
            {changePassword.isPending ? "Saving..." : "Change password"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function TwoFactorCard() {
  const { data: user } = useCurrentUser();
  const [setupOpen, setSetupOpen] = useState(false);
  const [disableOpen, setDisableOpen] = useState(false);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Two-factor authentication</CardTitle>
        <CardDescription>
          Add an extra layer of security to your account using an authenticator app.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-between">
        <Badge variant={user?.two_factor_enabled ? "success" : "secondary"}>
          {user?.two_factor_enabled ? "Enabled" : "Disabled"}
        </Badge>
        {user?.two_factor_enabled ? (
          <Button variant="outline" onClick={() => setDisableOpen(true)}>
            Disable 2FA
          </Button>
        ) : (
          <Button onClick={() => setSetupOpen(true)}>Enable 2FA</Button>
        )}
      </CardContent>

      <TwoFactorSetupDialog open={setupOpen} onOpenChange={setSetupOpen} />
      <TwoFactorDisableDialog open={disableOpen} onOpenChange={setDisableOpen} />
    </Card>
  );
}

export function AccountSettingsPage() {
  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Account Settings</h1>
        <p className="mt-1 text-muted-foreground">
          Manage your profile, password, and account security.
        </p>
      </div>

      <div className="grid gap-6 lg:max-w-2xl">
        <ProfileCard />
        <ChangePasswordCard />
        <TwoFactorCard />
      </div>
    </div>
  );
}
