import { Button, Section, Text } from "@react-email/components";

import { COMMON_PROPS, Layout, button, heading, note, p, paragraph, v } from "../layout";
import type { Props, TemplateMeta } from "../types";

export const meta: TemplateMeta = {
  key: "account_verification",
  name: "Account verification",
  description: "A branded email with a button that confirms a new account's email address.",
  category: "Account Verification",
  module: "authentication",
  suggested_for: "verification",
  subject: "Verify your {{company_name}} account",
  placeholders: ["full_name", "verification_url", "company_name"],
  props: [
    { name: "heading", label: "Heading", type: "text", default: "Welcome, {{full_name}}", required: true },
    { name: "message", label: "Message", type: "textarea", default: "Please confirm your email address to activate your account." },
    { name: "button_text", label: "Button text", type: "text", default: "Verify email", required: true },
    { name: "expiry_note", label: "Note under the button", type: "textarea", default: "This link expires in 24 hours. If you didn't create this account, you can ignore this email." },
    ...COMMON_PROPS,
  ],
};

export default function AccountVerification(_: Props) {
  return (
    <Layout preview={p("heading")}>
      <Text style={heading}>{p("heading")}</Text>
      <Text style={paragraph}>{p("message")}</Text>
      <Section style={{ margin: "24px 0" }}>
        <Button href={v("verification_url")} style={button}>{p("button_text")}</Button>
      </Section>
      <Text style={note}>{p("expiry_note")}</Text>
    </Layout>
  );
}
