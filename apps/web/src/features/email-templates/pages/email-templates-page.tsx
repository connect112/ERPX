import { TemplateList } from "@/features/email-templates/components/template-list";

/** Every email ERPX sends, with its wording, editable in one place. */
export function EmailTemplatesPage() {
  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Email templates</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          The wording of the emails ERPX sends, such as password resets, invites, exam links and certificates. Open one
          to edit it, preview it, and send yourself a test. Changes apply to emails sent from now on; emails already
          sent are not changed. Hackathon welcome emails can also be written per event, on that event's Emails tab.
        </p>
      </div>
      <TemplateList scope={{}} />
    </div>
  );
}
