# Email Studio: importing React Email code

*Create Email → Import React Email code.* An administrator pastes React Email source (TSX/JSX) from react.email, a project or an AI
assistant. The server turns it into a safe, editable email. **The pasted code is never executed**, on the server or in the browser.

## How it works

```
pasted TSX/JSX ─ parse (tree-sitter) ─ allowlist reader ─ email tree ─ HTML + plain text ─ sanitiser ─ stored
```

1. **Parse.** `modules/email_studio/react_import.py` parses the text with tree-sitter's TSX grammar into a syntax tree. Syntax errors
   are reported with their line.
2. **Read, don't run.** A small interpreter walks the tree and understands only the constructs listed below. Anything else is refused
   with the line it is on and a reason. There is no `eval`, no `Function`, no module loading, no network, no file access.
3. **Build.** The email tree is written out as email HTML (tables, inline styles) by this module's own code, plus a plain-text twin.
4. **Sanitise.** The HTML goes through the same sanitiser as every other email (`sanitize.py`): scripts, handlers, forms, frames, risky
   links and risky CSS are removed, and the page around it is ours.
5. **Store.** `email_studio_versions.react_source` keeps the code exactly as pasted; `body_html` / `body_text` hold what is sent. The
   email is rebuilt on the server from the source on every save, so HTML sent by a browser is never trusted. Publishing rebuilds and
   refuses code that does not build.

Placeholders, brand profiles, signatures, attachments, drafts/versions, test sends, previews and the send history are the existing Email
Studio features; an imported template is just another source type (`react`).

## What can be imported

| Pattern | Notes |
| --- | --- |
| `import { … } from "@react-email/components"` (or `"react-email"`, `"react"`) | the only packages allowed |
| Components `Html Head Preview Body Container Section Row Column Heading Text Button Link Img Hr Tailwind` | `Font` is skipped with a warning |
| Plain HTML tags `div span p a img h1–h6 ul ol li table tr td th strong em br hr …` | `script`, `iframe`, `form`, `input`, `svg`, `video`… are refused |
| `style={{ … }}` objects, constants, spread of constants | only email-safe CSS survives (reported otherwise) |
| `className` inside `<Tailwind>` | the subset below |
| Fixed values: strings, numbers, booleans, objects, arrays, template strings, `+ - * / %`, `&& \|\| ??`, `?:`, `===` … | |
| Your own components in the same file, with props, defaults and children | recursion is capped |
| `list.map(item => <… />)` over a fixed list | at most 200 items |
| `Component.PreviewProps = {…}` | its values become fixed text (reported) |
| `process.env.X` | treated as empty; fallbacks are used (reported) |
| ERPX placeholders `{{student_name}}` | bare in text (`Hi {{student_name}}`), in a string, or in an attribute |
| Bare `&` in text (`Terms & Conditions`) | accepted, as React does |

## What is refused (with the line)

Imports of any other package or file, calls (`fetch`, `eval`, `require`, `Math.random()` …), `new` (including `new Date`, use
`{{current_year}}`), `await`, event handlers (`onClick`), `dangerouslySetInnerHTML`, `<script>`/`<iframe>`/`<form>`, `javascript:` or
`data:` links, hooks, `if`/`for` logic, top-level statements that run code, components that call themselves, files over 200,000
characters, lists over 200 items. If the React code cannot be imported, copy the HTML from the source and use the **HTML Code** tab.

## Tailwind subset

`<Tailwind>` is not run. Each class is looked up in `modules/email_studio/tailwind.py` and turned into an inline style. Supported:
padding/margin (`p-4 px-2 mt-[10px] -mx-1 mx-auto`), width/height and min/max, `text-*` (size, colour, alignment), `font-*`,
`leading-*`, `tracking-*`, `italic underline uppercase …`, `bg-*`, `rounded*`, `border*` (width, side, style, colour),
`opacity-*`, `overflow-*`, `display` (`block inline-block hidden table …`), `align-*`, `whitespace-*`, `list-*`, `border-spacing-*`,
arbitrary values (`text-[#ff0000]`, `w-[600px]`, `leading-[normal]`) and arbitrary properties (`[border-left:1px_solid_#eee]`,
email-safe properties only). Colours are the Tailwind v3 palette plus the colours of the template's own `config` (`theme.colors`,
`theme.extend.colors`). **Not supported and always reported**, never dropped silently: responsive/state variants (`md:`, `hover:`,
`dark:`), flex/grid, shadows, gaps, transforms, custom fonts and spacing from a config.

## Two ways to keep editing

* **Code template** — the source is kept and edited in the code editor (syntax highlighting, line numbers, auto-indent, undo/redo,
  *Format code*, errors marked on their lines). It works even if it can never be converted.
* **Convert to Visual Editor** — builds the email, loads it into the visual editor, compares what the email contained (text, links,
  images) with what the editor kept, lists anything that did not carry over, and only then creates a **new** visual template. The code
  template is never changed, so it remains the original to go back to.

## Verified example

`tests/data/react_email/` holds unmodified community examples from the React Email demo app (MIT licence). All four (`linear-login-code`,
`stripe-welcome`, `github-access-token`, `koala-welcome`) import; of the 22 community examples in the demo app, 19 import and 3 are
refused with a clear reason (`new Date` / `Intl` date formatting, `Array(5)` star ratings).

Minimal example that imports as is (see "Load an example" in the editor):

```tsx
import { Body, Button, Container, Head, Heading, Html, Preview, Section, Text, Tailwind } from "@react-email/components";

export default function Welcome() {
  return (
    <Html>
      <Head><title>Welcome</title></Head>
      <Preview>Your internship starts soon</Preview>
      <Tailwind>
        <Body className="bg-white">
          <Container className="mx-auto max-w-[560px] p-5">
            <Heading className="text-2xl font-bold text-gray-900">Welcome, {{student_name}}</Heading>
            <Text className="text-[16px] leading-6 text-gray-700">We are glad to have you at {{company_name}}.</Text>
            <Section>
              <Button href="{{login_url}}" className="rounded-lg bg-blue-600 px-5 py-3 text-white">Open my dashboard</Button>
            </Section>
          </Container>
        </Body>
      </Tailwind>
    </Html>
  );
}
```

## Deleting templates (same release)

Deleting is **soft**: `deleted_at` / `deleted_by_user_id` are set, nothing is removed. A template flagged `is_system` can never be
deleted (HTTP 403), and one an ERPX email uses cannot be deleted until that email is pointed elsewhere (HTTP 409 naming the email).
Drafts and unused published templates can be deleted and restored from *Recently deleted*. Versions, send history and the audit trail
(automatic, via the audit hooks) are kept.

## Operations notes

* New dependencies: `tree-sitter==0.23.2` and `tree-sitter-typescript==0.23.2` (pinned together; tree-sitter 0.26 crashed under load
  on Windows). Prebuilt wheels exist for Linux, so the API image needs no compiler.
* Migration `0090` adds the soft-delete and `is_system` columns and `react_source`.
