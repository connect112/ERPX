import { Button, Column, Row, Section, Text } from "@react-email/components";

import { COMMON_PROPS, Layout, button, heading, note, p, paragraph, v } from "../layout";
import type { Props, TemplateMeta } from "../types";

export const meta: TemplateMeta = {
  key: "internship_onboarding_invite",
  name: "Internship onboarding invitation",
  description: "Invites a selected student to complete onboarding with their personal link: what to do, when it opens and the deadline.",
  category: "Internship Onboarding",
  module: "internships",
  suggested_for: "internship_onboarding_invitation",
  subject: "Complete your internship onboarding - {{internship_name}}",
  placeholders: [
    "student_name", "internship_name", "onboarding_link", "onboarding_deadline", "onboarding_start_date", "application_reference", "signature",
  ],
  props: [
    { name: "heading", label: "Heading", type: "text", default: "Welcome aboard, {{student_name}}", required: true },
    { name: "intro", label: "Opening message", type: "textarea", default: "Please complete your onboarding for {{internship_name}} before {{onboarding_deadline}}." },
    { name: "steps_title", label: "Steps heading", type: "text", default: "What you will do" },
    { name: "step_one", label: "Step 1", type: "text", default: "Check and confirm your details." },
    { name: "step_two", label: "Step 2", type: "text", default: "Upload the documents we ask for." },
    { name: "step_three", label: "Step 3", type: "text", default: "Accept your offer and, if a fee applies, pay it online." },
    { name: "button_text", label: "Button text", type: "text", default: "Start onboarding", required: true },
    { name: "link_note", label: "Note under the button", type: "textarea", default: "This link is personal, so please do not forward it. If you receive more than one email from us, use the newest one." },
    { name: "closing", label: "Closing line", type: "text", default: "We are glad to have you with us." },
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

export default function InternshipOnboardingInvite(_: Props) {
  return (
    <Layout preview={p("heading")}>
      <Text style={heading}>{p("heading")}</Text>
      <Text style={paragraph}>{p("intro")}</Text>
      <Section style={{ margin: "8px 0 20px", borderTop: "1px solid #e5e7eb" }}>
        <Detail name="Internship" text={v("internship_name")} />
        <Detail name="Onboarding opens" text={v("onboarding_start_date")} />
        <Detail name="Complete it by" text={v("onboarding_deadline")} />
        <Detail name="Your reference" text={v("application_reference")} />
      </Section>
      <Text style={{ ...paragraph, fontWeight: 700, margin: "0 0 8px" }}>{p("steps_title")}</Text>
      <Text style={{ ...paragraph, margin: "0 0 4px" }}>1. {p("step_one")}</Text>
      <Text style={{ ...paragraph, margin: "0 0 4px" }}>2. {p("step_two")}</Text>
      <Text style={{ ...paragraph, margin: "0 0 16px" }}>3. {p("step_three")}</Text>
      <Section style={{ margin: "20px 0" }}>
        <Button href={v("onboarding_link")} style={button}>
          {p("button_text")}
        </Button>
      </Section>
      <Text style={note}>{p("link_note")}</Text>
      <Text style={{ ...paragraph, margin: "20px 0 16px" }}>{p("closing")}</Text>
      <Text style={{ margin: 0 }}>{v("signature")}</Text>
    </Layout>
  );
}
