import { TemplateList } from "@/features/email-templates/components/template-list";
import type { HackathonPublic } from "@/features/hackathons/api/hackathons-api";

/**
 * The emails of this event. Write this event's own wording and only its participants get it; leave it alone
 * and the organisation's wording (Administration > Email templates) is used.
 */
export function EventEmailsTab({ hackathon }: { hackathon: HackathonPublic }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Emails sent to the participants of <strong>{hackathon.title}</strong>. Edit one to give this event its own
        wording; until you do, the organisation's wording is used. You can preview it and send yourself a test.
      </p>
      <TemplateList scope={{ hackathonId: hackathon.id }} />
    </div>
  );
}
