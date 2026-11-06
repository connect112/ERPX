import { Button, Column, Row, Section, Text } from "@react-email/components";

import { COMMON_PROPS, Layout, button, heading, note, p, paragraph, v } from "../layout";
import type { Props, TemplateMeta } from "../types";

export const meta: TemplateMeta = {
  key: "internship_offer_onboarding",
  name: "Internship offer letter with onboarding link",
  description:
    "Congratulates a selected student, summarises the internship and gives their personal onboarding button. Their offer letter PDF is attached by ERPX. Where the student has no new link to receive (manual onboarding, or they keep the link they have), the whole onboarding section is left out.",
  category: "Internship Offer Letters",
  module: "internships",
  suggested_for: "internship_offer_letter",
  subject: "Congratulations {{student_name}} - your internship offer from {{company_name}}",
  placeholders: [
    "student_name", "institution_name", "internship_name", "internship_position", "internship_duration", "internship_start_date",
    "internship_end_date", "program_type", "company_name", "reference", "letter_date", "signature", "onboarding_link", "onboarding_deadline",
  ],
  props: [
    { name: "heading", label: "Heading", type: "text", default: "Congratulations, {{student_name}}!", required: true },
    { name: "intro", label: "Opening message", type: "textarea", default: "We are pleased to offer you a place on {{internship_name}} at {{company_name}}." },
    { name: "attachment_note", label: "Attachment notice", type: "textarea", default: "Your offer letter (reference {{reference}}) is attached to this email as a PDF. Please read it carefully, sign it and send it back with the documents it lists." },
    { name: "onboarding_title", label: "Onboarding heading", type: "text", default: "Next step: complete your onboarding" },
    { name: "onboarding_text", label: "Onboarding message", type: "textarea", default: "Confirm your details, upload your documents and accept the offer before {{onboarding_deadline}}." },
    { name: "button_text", label: "Button text", type: "text", default: "Start onboarding", required: true },
    { name: "link_note", label: "Note under the button", type: "textarea", default: "Your onboarding link is personal, so please do not forward it. If we sent you one earlier, it keeps working." },
    { name: "closing", label: "Closing line", type: "text", default: "We look forward to working with you." },
    ...COMMON_PROPS,
  ],
};

const label = { fontSize: "13px", color: "#6b7280", margin: "0", padding: "6px 0" } as const;
const value = { fontSize: "14px", fontWeight: 600, margin: "0", padding: "6px 0" } as const;

function Detail({ name, text }: { name: string; text: string }) {
  return (
    <Row style={{ borderBottom: "1px solid #e5e7eb" }}>
      <Column style={{ width: "40%" }}>
        <Text style={label}>{name}</Text>
      </Column>
      <Column>
        <Text style={value}>{text}</Text>
      </Column>
    </Row>
  );
}

export default function InternshipOfferOnboarding(_: Props) {
  return (
    <Layout preview={p("heading")}>
      <Text style={heading}>{p("heading")}</Text>
      <Text style={paragraph}>{p("intro")}</Text>
      <Section style={{ margin: "8px 0 20px", borderTop: "1px solid #e5e7eb" }}>
        <Detail name="Internship" text={v("internship_name")} />
        <Detail name="Position" text={v("internship_position")} />
        <Detail name="Institution" text={v("institution_name")} />
        <Detail name="Duration" text={v("internship_duration")} />
        <Detail name="Start date" text={v("internship_start_date")} />
        <Detail name="End date" text={v("internship_end_date")} />
        <Detail name="Programme type" text={v("program_type")} />
      </Section>
      <Text style={paragraph}>{p("attachment_note")}</Text>
      {/* The whole onboarding call to action goes when the student has no link to be given (manual onboarding, or they keep the one they have). */}
      <Section data-optional-for="onboarding_link" style={{ margin: "0" }}>
        <Text style={{ ...paragraph, fontWeight: 700, margin: "20px 0 8px" }}>{p("onboarding_title")}</Text>
        <Text style={{ ...paragraph, margin: "0 0 8px" }}>{p("onboarding_text")}</Text>
        <Section style={{ margin: "16px 0" }}>
          <Button href={v("onboarding_link")} style={button}>
            {p("button_text")}
          </Button>
        </Section>
        <Text style={note}>{p("link_note")}</Text>
      </Section>
      <Text style={{ ...paragraph, margin: "20px 0 16px" }}>{p("closing")}</Text>
      <Text style={{ margin: 0 }}>{v("signature")}</Text>
      <Text style={note}>
        Reference {v("reference")} · {v("letter_date")}
      </Text>
    </Layout>
  );
}
