import { Body, Container, Head, Html, Preview, Text } from "@react-email/components";
import type { ReactNode } from "react";

import type { PropDef } from "./types";

/** The colour and name properties every template shares. The brand profile fills them when the template is used. */
export const COMMON_PROPS: PropDef[] = [
  { name: "primary_color", label: "Main colour", type: "color", default: "#2563eb" },
  { name: "secondary_color", label: "Secondary colour", type: "color", default: "#1e40af" },
  { name: "accent_color", label: "Accent colour", type: "color", default: "#f59e0b" },
  { name: "background_color", label: "Page background", type: "color", default: "#f4f4f5" },
  { name: "text_color", label: "Text colour", type: "color", default: "#111827" },
];

export const p = (name: string) => `{{prop:${name}}}`; // a property, filled by the administrator's settings
export const v = (name: string) => `{{${name}}}`; // an ERPX placeholder, filled when the email is sent

export function Layout({ preview, children }: { preview: string; children: ReactNode }) {
  return (
    <Html lang="en">
      <Head />
      <Preview>{preview}</Preview>
      <Body style={{ margin: 0, padding: "24px 0", backgroundColor: p("background_color"), fontFamily: "Helvetica, Arial, sans-serif", color: p("text_color") }}>
        {/* the brand header and footer are inserted here when the template is used */}
        <Container style={{ maxWidth: "600px", width: "100%" }}>
          <Text style={{ margin: 0 }}>{v("brand_header")}</Text>
          <Container style={{ backgroundColor: "#ffffff", padding: "28px 32px", borderRadius: "8px", maxWidth: "600px" }}>{children}</Container>
          <Text style={{ margin: 0 }}>{v("brand_footer")}</Text>
        </Container>
      </Body>
    </Html>
  );
}

export const heading = { fontSize: "24px", lineHeight: "32px", fontWeight: 700, margin: "0 0 16px", color: p("text_color") } as const;
export const paragraph = { fontSize: "15px", lineHeight: "24px", margin: "0 0 16px", color: p("text_color") } as const;
export const note = { fontSize: "13px", lineHeight: "20px", margin: "16px 0 0", color: "#6b7280" } as const;
export const button = {
  backgroundColor: p("primary_color"), color: "#ffffff", fontSize: "15px", fontWeight: 600, padding: "12px 24px", borderRadius: "6px", textDecoration: "none", display: "inline-block",
} as const;
