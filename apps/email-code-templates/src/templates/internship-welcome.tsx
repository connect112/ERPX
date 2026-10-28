import { Button, Section, Text } from "@react-email/components";

import { COMMON_PROPS, Layout, button, heading, note, p, paragraph, v } from "../layout";
import type { Props, TemplateMeta } from "../types";

export const meta: TemplateMeta = {
  key: "internship_welcome",
  name: "Internship welcome",
  description: "Welcomes a student who has joined an internship, with the key instructions and a link to sign in.",
  category: "Internship Onboarding",
  module: "internships",
  suggested_for: "internship_welcome",
  subject: "Welcome to {{internship_title}}",
  placeholders: ["full_name", "internship_title", "course_title", "login_url", "company_name", "signature"],
  props: [
    { name: "heading", label: "Heading", type: "text", default: "Welcome, {{full_name}}", required: true },
    { name: "intro", label: "Welcome message", type: "textarea", default: "Your access to {{internship_title}} is ready. You are now enrolled in {{course_title}}." },
    { name: "instructions_title", label: "Instructions heading", type: "text", default: "Before you start" },
    { name: "step_one", label: "Instruction 1", type: "text", default: "Sign in with the button below." },
    { name: "step_two", label: "Instruction 2", type: "text", default: "Open your course and read the programme guidelines." },
    { name: "step_three", label: "Instruction 3", type: "text", default: "Contact your coordinator if anything is unclear." },
    { name: "button_text", label: "Button text", type: "text", default: "Sign in", required: true },
    { name: "footer_note", label: "Closing note", type: "textarea", default: "We are glad to have you with us." },
    ...COMMON_PROPS,
  ],
};

export default function InternshipWelcome(_: Props) {
  return (
    <Layout preview={p("heading")}>
      <Text style={heading}>{p("heading")}</Text>
      <Text style={paragraph}>{p("intro")}</Text>
      <Text style={{ ...paragraph, fontWeight: 700, margin: "0 0 8px" }}>{p("instructions_title")}</Text>
      <Text style={{ ...paragraph, margin: "0 0 4px" }}>1. {p("step_one")}</Text>
      <Text style={{ ...paragraph, margin: "0 0 4px" }}>2. {p("step_two")}</Text>
      <Text style={{ ...paragraph, margin: "0 0 16px" }}>3. {p("step_three")}</Text>
      <Section style={{ margin: "20px 0" }}>
        <Button href={v("login_url")} style={button}>
          {p("button_text")}
        </Button>
      </Section>
      <Text style={note}>{p("footer_note")}</Text>
      <Text style={{ margin: 0 }}>{v("signature")}</Text>
    </Layout>
  );
}
