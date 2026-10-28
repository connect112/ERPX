import type { ReactBuild } from "@/features/email-studio/api/studio-api";

/** A small, valid example that shows the shapes the importer understands, including ERPX placeholders. */
export const REACT_EXAMPLE = `import { Body, Button, Container, Head, Heading, Html, Preview, Section, Text, Tailwind } from "@react-email/components";

export default function Welcome() {
  return (
    <Html>
      <Head>
        <title>Welcome</title>
      </Head>
      <Preview>Your internship starts soon</Preview>
      <Tailwind>
        <Body className="bg-white">
          <Container className="mx-auto max-w-[560px] p-5">
            <Heading className="text-2xl font-bold text-gray-900">Welcome, {{student_name}}</Heading>
            <Text className="text-[16px] leading-6 text-gray-700">
              We are glad to have you at {{company_name}}. Sign in to see your first tasks.
            </Text>
            <Section>
              <Button href="{{login_url}}" className="rounded-lg bg-blue-600 px-5 py-3 text-white">
                Open my dashboard
              </Button>
            </Section>
          </Container>
        </Body>
      </Tailwind>
    </Html>
  );
}
`;

/** Tidy the code with Prettier. Loaded only when asked for, because it is large. Never runs the code. */
export async function formatReactSource(source: string): Promise<string> {
  const [prettier, typescript, estree] = await Promise.all([import("prettier/standalone"), import("prettier/plugins/typescript"), import("prettier/plugins/estree")]);
  return prettier.format(source, { parser: "typescript", plugins: [typescript, estree as never], printWidth: 110, tabWidth: 2, semi: true, singleQuote: false });
}

export type BuildState = "idle" | "building" | "ok" | "errors" | "stale";

export function buildState(build: ReactBuild | null, building: boolean, builtSource: string | null, source: string): BuildState {
  if (building) return "building";
  if (!build) return "idle";
  if (builtSource !== source) return "stale";
  return build.ok ? "ok" : "errors";
}

export const BUILD_LABEL: Record<BuildState, { label: string; tone: "secondary" | "success" | "destructive" | "warning" | "info" }> = {
  idle: { label: "Not built yet", tone: "secondary" },
  building: { label: "Building...", tone: "info" },
  ok: { label: "Build passed", tone: "success" },
  errors: { label: "Build failed", tone: "destructive" },
  stale: { label: "Changed since the last build", tone: "warning" },
};
