import { Text } from "@react-email/components";

import { COMMON_PROPS, Layout, heading, note, p, paragraph, v } from "../layout";
import type { Props, TemplateMeta } from "../types";

export const meta: TemplateMeta = {
  key: "certificate_distribution",
  name: "Certificate distribution",
  description: "Delivers a participation or completion certificate; ERPX attaches that student's own PDF and says which kind it is.",
  category: "Internship Certificates",
  module: "internships",
  suggested_for: "internship_completion_certificate",
  subject: "Your internship {{certificate_type}} certificate: {{internship_title}}",
  placeholders: ["full_name", "internship_title", "certificate_type", "company_name", "signature"],
  props: [
    { name: "heading", label: "Heading", type: "text", default: "Congratulations, {{full_name}}!", required: true },
    { name: "message", label: "Message", type: "textarea", default: "Your certificate of {{certificate_type}} for {{internship_title}} is attached to this email as a PDF." },
    { name: "closing", label: "Closing line", type: "text", default: "Thank you for all your work." },
    ...COMMON_PROPS,
  ],
};

export default function CertificateDistribution(_: Props) {
  return (
    <Layout preview={p("heading")}>
      <Text style={heading}>{p("heading")}</Text>
      <Text style={paragraph}>{p("message")}</Text>
      <Text style={paragraph}>{p("closing")}</Text>
      <Text style={{ margin: 0 }}>{v("signature")}</Text>
      <Text style={note}>Keep this certificate for your records.</Text>
    </Layout>
  );
}
