import { Button, Section, Text } from "@react-email/components";

import { COMMON_PROPS, Layout, button, heading, note, p, paragraph, v } from "../layout";
import type { Props, TemplateMeta } from "../types";

export const meta: TemplateMeta = {
  key: "password_reset",
  name: "Password reset",
  description: "A calm, security-focused email with a button to choose a new password.",
  category: "Password Reset",
  module: "authentication",
  suggested_for: "password_reset",
  subject: "Reset your {{company_name}} password",
  placeholders: ["full_name", "reset_url", "company_name"],
  props: [
    { name: "heading", label: "Heading", type: "text", default: "Reset your password", required: true },
    { name: "message", label: "Message", type: "textarea", default: "Hi {{full_name}}, we received a request to reset your password. Use the button below to choose a new one." },
    { name: "button_text", label: "Button text", type: "text", default: "Reset password", required: true },
    { name: "security_note", label: "Security note", type: "textarea", default: "This link expires in 1 hour and can be used once. If you didn't ask for this, you can ignore this email and your password will stay the same." },
    ...COMMON_PROPS,
  ],
};

export default function PasswordReset(_: Props) {
  return (
    <Layout preview={p("heading")}>
      <Text style={heading}>{p("heading")}</Text>
      <Text style={paragraph}>{p("message")}</Text>
      <Section style={{ margin: "24px 0" }}>
        <Button href={v("reset_url")} style={button}>{p("button_text")}</Button>
      </Section>
      <Text style={note}>{p("security_note")}</Text>
    </Layout>
  );
}
