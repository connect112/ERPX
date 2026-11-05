import type { ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { errorMessage } from "@/features/institutions/lib/format";
import { PaymentAccountsManager } from "@/features/internship-onboarding/components/payment-accounts-manager";
import { PaymentsQueue } from "@/features/internship-onboarding/components/payments-queue";
import { SettingsEditor } from "@/features/internship-onboarding/components/settings-editor";
import { StudentsBoard } from "@/features/internship-onboarding/components/students-board";
import { TemplatesManager } from "@/features/internship-onboarding/components/templates-manager";
import { onboardingAccess, useOnboardingConfig } from "@/features/internship-onboarding/hooks";
import {
  modeNotice,
  operationSections,
  selfServiceActions,
  settingsSections,
} from "@/features/internship-onboarding/lib/tabs";

/** "Onboarding" tab: the self-service part of the day-to-day work on students (the manual tools follow below it). */
export function OnboardingOperationsPanel({ internshipId, isAdmin }: { internshipId: string; isAdmin: boolean }) {
  const config = useOnboardingConfig(internshipId);
  const access = onboardingAccess(isAdmin, config.data);
  const mode = config.data?.settings.modes.mode;
  const sections = operationSections(access);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Student onboarding</CardTitle>
        <CardDescription>{modeNotice(mode)}</CardDescription>
      </CardHeader>
      <CardContent>
        {config.isError && <p className="text-sm text-destructive">{errorMessage(config.error, "Could not load the onboarding settings.")}</p>}
        {config.data && (
          <Tabs defaultValue="students">
            <TabsList className="h-auto flex-wrap justify-start">
              <TabsTrigger value="students">Students</TabsTrigger>
              {sections.includes("payments") && <TabsTrigger value="payments">Payment checks</TabsTrigger>}
            </TabsList>
            <TabsContent value="students">
              <StudentsBoard internshipId={internshipId} timezone={config.data.settings.deadlines.timezone} canManage={selfServiceActions(access, mode)} />
            </TabsContent>
            {sections.includes("payments") && (
              <TabsContent value="payments">
                <PaymentsQueue internshipId={internshipId} />
              </TabsContent>
            )}
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}

/** "Onboarding Settings" tab: how this internship onboards. ``lmsCourse`` is the internship's LMS course picker. */
export function OnboardingSettingsPanel({ internshipId, isAdmin, lmsCourse }: { internshipId: string; isAdmin: boolean; lmsCourse: ReactNode }) {
  const config = useOnboardingConfig(internshipId);
  const sections = settingsSections(onboardingAccess(isAdmin, config.data));

  if (config.isError) return <p className="text-sm text-destructive">{errorMessage(config.error, "Could not load the onboarding settings.")}</p>;
  if (!config.data) return null;
  return (
    <Tabs defaultValue={sections[0]}>
      <TabsList className="h-auto flex-wrap justify-start">
        {sections.includes("general") && <TabsTrigger value="general">Settings</TabsTrigger>}
        {sections.includes("lms-course") && <TabsTrigger value="lms-course">LMS course</TabsTrigger>}
        {sections.includes("accounts") && <TabsTrigger value="accounts">Payment accounts</TabsTrigger>}
        {sections.includes("templates") && <TabsTrigger value="templates">Templates</TabsTrigger>}
      </TabsList>
      {sections.includes("general") && (
        <TabsContent value="general">
          <SettingsEditor internshipId={internshipId} view={config.data} />
        </TabsContent>
      )}
      {sections.includes("lms-course") && <TabsContent value="lms-course">{lmsCourse}</TabsContent>}
      {sections.includes("accounts") && (
        <TabsContent value="accounts">
          <PaymentAccountsManager />
        </TabsContent>
      )}
      {sections.includes("templates") && (
        <TabsContent value="templates">
          <TemplatesManager />
        </TabsContent>
      )}
    </Tabs>
  );
}
