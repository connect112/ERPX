import { Column, Row, Section, Text } from "@react-email/components";

import { COMMON_PROPS, Layout, heading, note, p, paragraph, v } from "../layout";
import type { Props, TemplateMeta } from "../types";

export const meta: TemplateMeta = {
  key: "internship_offer",
  name: "Internship offer letter",
  description: "Congratulates a selected student and summarises the internship; their offer letter PDF is attached by ERPX.",
  category: "Internship Offer Letters",
  module: "internships",
  suggested_for: "internship_offer_letter",
  subject: "Congratulations {{student_name}} - internship offer from {{company_name}}",
  placeholders: [
    "student_name", "institution_name", "internship_name", "internship_position", "internship_duration", "internship_start_date",
    "internship_end_date", "program_type", "company_name", "reference", "letter_date", "signature",
  ],
  props: [
    { name: "heading", label: "Heading", type: "text", default: "Congratulations, {{student_name}}!", required: true },
    { name: "intro", label: "Opening message", type: "textarea", default: "We are pleased to offer you a place on {{internship_name}} at {{company_name}}." },
    { name: "attachment_note", label: "Attachment notice", type: "textarea", default: "Your offer letter (reference {{reference}}) is attached to this email as a PDF. Please read it carefully, sign it and send it back with the documents it lists." },
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

export default function InternshipOffer(_: Props) {
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
      <Text style={paragraph}>{p("closing")}</Text>
      <Text style={{ margin: 0 }}>{v("signature")}</Text>
      <Text style={note}>
        Reference {v("reference")} · {v("letter_date")}
      </Text>
    </Layout>
  );
}
