"""
Importing React Email code: what is understood, what is refused (with the line it is on), that nothing pasted is ever run, and that
the result is email-safe HTML with the ERPX placeholders intact. Also the Tailwind subset.
"""

from pathlib import Path

import pytest

from modules.email_studio import tailwind
from modules.email_studio.react_import import MAX_SOURCE_CHARS, build

DATA = Path(__file__).resolve().parent.parent / "data" / "react_email"

WELCOME = """
import { Body, Button, Container, Head, Heading, Html, Img, Link, Preview, Section, Text, Tailwind } from "@react-email/components";
import * as React from "react";

const main = { backgroundColor: "#f6f9fc", fontFamily: "Helvetica,Arial,sans-serif" };
const steps = ["Verify your email", "Complete your profile"];

export default function Welcome() {
  return (
    <Html>
      <Head><title>Welcome</title></Head>
      <Preview>Welcome to Pentrix</Preview>
      <Tailwind>
        <Body style={main}>
          <Container className="mx-auto max-w-[600px] p-5">
            <Img src="https://cdn.example.com/logo.png" width="48" height="48" alt="Logo" />
            <Heading className="text-2xl font-bold text-gray-900">Hi {{student_name}},</Heading>
            <Text className="text-[16px] leading-6">Welcome to {{company_name}}! Here's what's next &amp; why.</Text>
            <Section>
              {steps.map((s, i) => (<Text key={i} style={{ margin: 0 }}>{i + 1}. {s}</Text>))}
            </Section>
            <Button href="{{login_url}}" className="rounded-lg bg-blue-600 px-5 py-3 text-white">Open dashboard</Button>
          </Container>
        </Body>
      </Tailwind>
    </Html>
  );
}
"""


def errors_of(source: str) -> list[str]:
    result = build(source)
    assert not result.ok
    return [f"{e.line}: {e.message}" for e in result.errors]


# ------------------------------------------------------------------ what is understood


def test_a_typical_template_becomes_safe_email_html_with_placeholders_intact():
    result = build(WELCOME)
    assert result.ok and not result.errors
    html = result.html
    assert html.startswith("<!DOCTYPE") and "<script" not in html.lower()
    assert "Hi {{student_name}}," in html and "Welcome to {{company_name}}!" in html and 'href="{{login_url}}"' in html
    assert "Here&#39;s what&#39;s next &amp; why." in html or "Here's what's next &amp; why." in html
    assert "1. Verify your email" in html and "2. Complete your profile" in html  # .map over a fixed list
    assert "background-color:#f6f9fc" in html  # <Body style>
    assert "max-width:600px" in html and "margin-left:auto" in html and "padding:20px" in html  # Tailwind to inline styles
    assert "font-size:24px" in html and "font-weight:700" in html and "color:#111827" in html
    assert "border-radius:8px" in html and "background-color:#2563eb" in html and "color:#ffffff" in html  # the button
    assert result.title == "Welcome" and result.preheader == "Welcome to Pentrix"
    assert sorted(result.placeholders) == ["company_name", "login_url", "student_name"]
    assert "Hi {{student_name}}," in result.text and "Open dashboard ({{login_url}})" in result.text
    assert {"Html", "Body", "Container", "Heading", "Button", "Tailwind"} <= set(result.components)


def test_a_bare_double_brace_in_text_is_read_as_the_erpx_placeholder_it_means():
    # In JSX {{name}} is an object, not text; the importer reads it as the placeholder the author intended.
    result = build('import { Html, Text } from "@react-email/components"; export default () => (<Html><Text>Dear {{ student_name }} and {"{{company_name}}"}</Text></Html>);')
    assert result.ok and "Dear {{student_name}} and {{company_name}}" in result.html


def test_text_follows_reacts_whitespace_and_entity_rules():
    result = build(
        'import { Html, Text } from "@react-email/components";\n'
        "export default () => (<Html><Text>\n   Terms & Conditions\n   &nbsp;apply &copy; 2026\n  </Text></Html>);"
    )
    assert result.ok
    assert "Terms &amp; Conditions" in result.html and "apply" in result.html and "2026" in result.html
    assert "Terms & Conditions" in result.text


def test_components_functions_props_and_children_in_the_same_file_work():
    source = """
import { Html, Section, Text } from "@react-email/components";
const Box = ({ title = "Untitled", children }) => (<Section><Text style={{ fontWeight: 700 }}>{title}</Text>{children}</Section>);
export default function Mail() {
  return (<Html><Box title="Details"><Text>Inside</Text></Box><Box /></Html>);
}
"""
    result = build(source)
    assert result.ok and result.html.count("Details") == 1 and "Untitled" in result.html and "Inside" in result.html


def test_preview_props_become_fixed_text_and_the_author_is_told():
    source = """
import { Html, Text } from "@react-email/components";
interface Props { name?: string }
export const Mail = ({ name }: Props) => (<Html><Text>Hello {name}</Text></Html>);
Mail.PreviewProps = { name: "Alan" } satisfies Props;
export default Mail;
"""
    result = build(source)
    assert result.ok and "Hello Alan" in result.html
    assert any("PreviewProps" in w.message and "Alan" in w.message for w in result.warnings)


def test_env_variables_and_relative_images_are_reported_not_silently_dropped():
    source = """
import { Html, Img } from "@react-email/components";
const baseUrl = process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "";
export default () => (<Html><Img src={`${baseUrl}/static/logo.png`} alt="Logo" /></Html>);
"""
    result = build(source)
    assert result.ok
    messages = " | ".join(w.message for w in result.warnings)
    assert "process.env" in messages and "/static/logo.png" in messages and "removed" in messages
    assert "/static/logo.png" not in result.html
    assert all(w.line for w in result.warnings)


def test_styles_an_email_client_cannot_use_are_reported():
    result = build('import { Html, Text } from "@react-email/components"; export default () => (<Html><Text style={{ position: "absolute", display: "flex", color: "red" }}>x</Text></Html>);')
    assert result.ok and "color:red" in result.html and "position" not in result.html and "flex" not in result.html
    assert any("position" in w.message and "removed" in w.message for w in result.warnings)


def test_repeated_warnings_are_merged_and_list_every_line():
    source = (
        'import { Html, Tailwind, Text } from "@react-email/components";\n'
        "export default () => (<Html><Tailwind>\n<Text className=\"flex\">a</Text>\n<Text className=\"flex\">b</Text>\n<Text className=\"flex\">c</Text></Tailwind></Html>);"
    )
    result = build(source)
    flagged = [w for w in result.warnings if "flex" in w.message]
    assert len(flagged) == 1 and flagged[0].line == 3 and "Also on lines 4, 5" in flagged[0].message


@pytest.mark.parametrize("name", ["linear-login-code", "stripe-welcome", "github-access-token", "koala-welcome"])
def test_official_react_email_examples_import(name):
    """Unmodified examples from the React Email demo app (tests/data/react_email/README.md)."""
    result = build((DATA / f"{name}.tsx").read_text(encoding="utf-8"))
    assert result.ok, [f"{e.line}: {e.message}" for e in result.errors]
    lowered = result.html.lower()
    assert "<script" not in lowered and "javascript:" not in lowered and "onclick" not in lowered
    assert len(result.text) > 40 and result.title is not None
    assert result.warnings  # their relative images, theme and sample values are all reported
    assert all(w.severity == "warning" for w in result.warnings)


def test_the_linear_example_keeps_its_layout_text_button_and_colours():
    result = build((DATA / "linear-login-code.tsx").read_text(encoding="utf-8"))
    assert result.ok
    assert "Your login code for Linear" in result.html
    assert "Login to Linear" in result.html
    assert "background-color" in result.html and "border-radius" in result.html  # button styling survived
    assert "<h1" in result.html and "<table" in result.html and 'role="presentation"' in result.html
    assert "tt226-5398x" in result.html  # the sample code from PreviewProps, reported as fixed text
    assert any("PreviewProps" in w.message for w in result.warnings)


# ------------------------------------------------------------------ what is refused, and where


def test_other_packages_and_files_cannot_be_imported():
    found = errors_of(
        'import axios from "axios";\nimport { thing } from "./thing";\nimport { render } from "@react-email/render";\n'
        'import { Html } from "@react-email/components";\nexport default () => (<Html />);'
    )
    assert any(e.startswith("1:") and "axios" in e for e in found)
    assert any(e.startswith("2:") and "./thing" in e and "another file" in e for e in found)
    assert any(e.startswith("3:") and "@react-email/render" in e for e in found)


def test_unsupported_react_email_components_are_named():
    found = errors_of('import { Html, Markdown, CodeBlock } from "@react-email/components";\nexport default () => (<Html><Markdown>hi</Markdown></Html>);')
    assert any("`Markdown`" in e for e in found) and any("`CodeBlock`" in e for e in found) and any("HTML tab" in e for e in found)


@pytest.mark.parametrize(
    ("snippet", "needle"),
    [
        ('{eval("1")}', "eval"),
        ('{require("fs")}', "require"),
        ("{fetch('https://evil.example')}", "fetch"),
        ("{new Date().getFullYear()}", "current_year"),
        ("{Math.random()}", "Math"),
        ("{window.location.href}", "window"),
        ("{(() => 1)()}", "never run"),
        ("{user.name}", "not defined"),
        ("{this.props.x}", "this"),
    ],
)
def test_dynamic_code_is_refused_with_its_line_and_never_run(snippet, needle):
    source = f'import {{ Html, Text }} from "@react-email/components";\nexport default function E() {{\n  return (<Html>\n<Text>{snippet}</Text></Html>);\n}}'
    found = errors_of(source)
    assert found and found[0].startswith("4:") and needle in found[0]


def test_logic_in_the_component_and_at_the_top_of_the_file_is_refused():
    found = errors_of(
        'import { Html } from "@react-email/components";\nconsole.log("loaded");\nconst data = await fetch("https://evil.example");\n'
        "export default function E() {\n  const now = new Date();\n  if (now) { }\n  return (<Html />);\n}"
    )
    assert any(e.startswith("2:") and "runs code when the file loads" in e for e in found)
    assert any(e.startswith("3:") and "asynchronous" in e for e in found)
    assert any(e.startswith("5:") for e in found)


def test_scripts_event_handlers_raw_html_and_script_links_are_refused():
    source = """
import { Html, Text, Body } from "@react-email/components";
export default function E() {
  return (<Html><Body>
    <script>alert(1)</script>
    <iframe src="https://evil.example" />
    <Text onClick={() => alert(1)}>a</Text>
    <Text dangerouslySetInnerHTML={{ __html: "<b>x</b>" }} />
    <a href="javascript:alert(1)">x</a>
    <a href="data:text/html;base64,AAAA">y</a>
  </Body></Html>);
}
"""
    found = " | ".join(errors_of(source))
    for needle in ("<script>", "<iframe>", "onClick", "dangerouslySetInnerHTML", "javascript:", "data:"):
        assert needle in found, needle


def test_a_component_that_calls_itself_or_a_huge_loop_cannot_hang_the_server():
    loop = 'import { Html, Text } from "@react-email/components";\nconst Again = () => (<Text><Again /></Text>);\nexport default () => (<Html><Again /></Html>);'
    assert any("too deeply" in e or "refers to itself" in e for e in errors_of(loop))
    big = 'import { Html, Text } from "@react-email/components";\nconst items = Array.from({length: 5});\nexport default () => (<Html />);'
    assert errors_of(big)
    many = "[" + ",".join(["1"] * 400) + "]"
    source = f'import {{ Html, Text }} from "@react-email/components";\nconst xs = {many};\nexport default () => (<Html>{{xs.map((x) => <Text>{{x}}</Text>)}}</Html>);'
    assert any("more than" in e for e in errors_of(source))


def test_deeply_nested_markup_is_refused_not_crashed():
    depth = 400
    source = 'import { Html, Section } from "@react-email/components";\nexport default () => (<Html>' + "<Section>" * depth + "x" + "</Section>" * depth + "</Html>);"
    assert errors_of(source)


def test_syntax_errors_give_a_line_and_a_hint():
    found = errors_of('import { Html, Text } from "@react-email/components";\nexport default () => (\n<Html>\n<Text>unclosed\n</Html>);')
    assert found and found[0].split(":")[0].isdigit()
    assert errors_of("this is not code at all <<<")
    assert "Paste React Email code" in errors_of("   ")[0]
    assert "too long" in build("x" * (MAX_SOURCE_CHARS + 1)).errors[0].message


def test_no_exported_component_is_explained():
    assert any("No email component" in e for e in errors_of('import { Html } from "@react-email/components";\nconst x = 1;'))


def test_every_problem_is_reported_in_one_go():
    source = """
import { Html, Text } from "@react-email/components";
export default () => (<Html>
<Text>{eval("a")}</Text>
<Text>{require("b")}</Text>
<Mystery />
</Html>);
"""
    assert len(errors_of(source)) >= 3


# ------------------------------------------------------------------ the Tailwind subset


def test_tailwind_utilities_become_inline_styles():
    styles, unsupported = tailwind.resolve("px-5 py-3 mx-auto w-full max-w-[600px] text-center text-sm font-semibold text-[#ff0000] bg-blue-600 rounded-lg border border-gray-300 leading-6 uppercase underline")
    assert not unsupported
    assert styles["padding-left"] == "20px" and styles["padding-top"] == "12px" and styles["margin-left"] == "auto"
    assert styles["width"] == "100%" and styles["max-width"] == "600px" and styles["text-align"] == "center"
    assert styles["font-size"] == "14px" and styles["line-height"] == "24px" and styles["font-weight"] == "600" and styles["color"] == "#ff0000"
    assert styles["background-color"] == "#2563eb" and styles["border-radius"] == "8px" and styles["border-width"] == "1px" and styles["border-color"] == "#d1d5db"
    assert styles["text-transform"] == "uppercase" and styles["text-decoration"] == "underline"


def test_less_specific_tailwind_utilities_come_first_whatever_the_order_written():
    styles, _ = tailwind.resolve("pt-1 p-4 px-2")
    assert list(styles) == ["padding", "padding-left", "padding-right", "padding-top"]
    assert styles["padding"] == "16px" and styles["padding-top"] == "4px"


def test_unsupported_tailwind_is_returned_not_dropped():
    styles, unsupported = tailwind.resolve("flex grid md:px-4 hover:bg-red-500 dark:text-white shadow-lg gap-4 bg-brand text-[javascript:x] p-[calc(1px+2px)]")
    assert styles == {}
    assert set(unsupported) >= {"flex", "grid", "md:px-4", "hover:bg-red-500", "dark:text-white", "shadow-lg", "gap-4", "bg-brand"}


def test_a_templates_own_tailwind_colours_are_used():
    styles, unsupported = tailwind.resolve("bg-brand text-brand-dark", {"brand": "#007291", "brand-dark": "#112233"})
    assert not unsupported and styles == {"background-color": "#007291", "color": "#112233"}
    result = build(
        'import { Html, Tailwind, Text } from "@react-email/components";\n'
        "export default () => (<Html><Tailwind config={{ theme: { extend: { colors: { brand: { DEFAULT: '#007291', dark: '#112233' } } } } }}>"
        '<Text className="text-brand bg-brand-dark">x</Text></Tailwind></Html>);'
    )
    assert result.ok and "color:#007291" in result.html and "background-color:#112233" in result.html


def test_arbitrary_properties_must_be_email_safe():
    styles, unsupported = tailwind.resolve("[border-left:1px_solid_#eee] [position:fixed] [color:red;background:url(x)]")
    assert styles == {"border-left": "1px solid #eee"}
    assert "[position:fixed]" in unsupported


def test_classes_outside_tailwind_are_reported():
    result = build('import { Html, Text } from "@react-email/components";\nexport default () => (<Html><Text className="text-red-500">x</Text></Html>);')
    assert result.ok and any("outside <Tailwind>" in w.message for w in result.warnings) and "color:#ef4444" not in result.html
