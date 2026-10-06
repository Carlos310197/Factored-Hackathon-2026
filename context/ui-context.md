# UI Context

Read this file only for work in `web/`, or for agent changes that feed the UI (trace payloads, the contract fields). Text under a `· ui §<n>` heading is copied word for word from `docs/design/2026-09-30-ui-design.md`.

## Summary

- **Two visual worlds, light only.** World B (customer: `/login`, `/chat`) is tropical modernist with Schibsted Grotesk. World C (staff: `/agent`, `/trace`, `/demo` canvas) is an instrument panel with Hanken Grotesk and tabular figures.
- **Colours are CSS custom properties** mapped to Tailwind v4 `@theme` tokens. Components never use raw hex values or default palette classes (`zinc-*`, `blue-*`). The only exception is `lib/trace/signals.ts`, which owns the signal hex values.
- **Component library:** assistant-ui primitives with `useExternalStoreRuntime`, styled by us, with no default assistant-ui theme. Custom message parts cover chips, the summary card, receipt chips, system lines and agent messages.
- **Copy:** customer copy lives in the `es`/`pt` dictionaries; staff, trace and demo chrome is English. Customer quotes are always shown in the original.
- **Motion:** the trace block reveal, plus short `motion-safe` entrance fades and typing dots in the customer chat (progress-tracker → Architecture Decisions, UI polish pass); none under `prefers-reduced-motion`.
- **Planning change:** the confirmation card shows merchant, date, amount and reason. `product_last4` was dropped (see `progress-tracker.md` → Architecture Decisions, UI plan #1).

## BFF route handlers (`web/app/api/…`) · ui §6

*(2026-10-06)* Judge-facing summary of every page, route and trust path: `docs/api.md`.

Every handler parses its input with Zod, checks the cookie's JWT (signature, expiry, role or scope) before any logic, and returns `{data} | {error: {code, message}}`.

| Route | Role | Does |
|---|---|---|
| `POST /api/auth/login`, `/otp`, `/staff-login`, `/logout` | public / any | Proxy to the identity service; set or clear the httpOnly cookie. *(2026-10-06)* After a successful `/otp`, `after()` sends `{"warmup": true}` to the conversation's AgentCore session |
| `GET /api/auth/demo-users` | public (demo only) | The login picker: customers only, never staff; 404 outside demo mode |
| `GET /api/auth/realtime-token` | customer, agent | Returns a subscribe-only token (the only token JS ever sees) |
| `GET /api/auth/debug-claims` | agent (demo only) | Decoded claims of the customer token in this browser's `cust_session` cookie (the embedded phone), for Act 1 (§9.1). Disabled outside demo builds. |
| `POST /api/chat` | customer | If `control ≠ agent`: store the message and return `awaiting: human`. Otherwise invoke AgentCore with the Bearer JWT, the runtime session id and the message-id header, and return the §4.7 response. *(2026-10-06)* Logs one JSON line per call (`status`, `ms`, `sid`, `client_message_id`, `turn_id`). |
| `GET /api/sessions/:sid/messages?after=` | owner customer, agent | History; the owner may read any of their past conversations (read-only) |
| `GET /api/customer/sessions` | customer | The customer's conversations (`sessions.by_customer`), newest first, hidden ones left out, current one marked |
| `POST /api/customer/sessions/end` | customer | Ends the current conversation; `/api/chat` then answers 409 `session_ended` |
| `POST /api/customer/sessions/new` | customer | Ends the current one and swaps the cookie for a new session id (IdP `/auth/session/new`, same expiry) |
| `POST /api/customer/sessions/:sid/hide` | owner customer | Takes a past conversation off the list (409 `current_session` for the current one); the record is kept |
| `GET /api/customer/cases` | customer | The signed-in customer's 20 newest disputes (`CustomerCase`), id from the token only |
| `POST /api/sessions/:sid/messages` | agent holding the takeover | Agent message |
| `GET /api/handoffs?status=` | agent | Queue |
| `GET /api/handoffs/:id` | agent | Packet |
| `POST /api/handoffs/:id/{claim,takeover,return,resolve}` | agent | Lifecycle (§5) |
| `GET /api/trace/:sid?turn=` | agent | Trace view model (§8.3) |

## Visual design · ui §7

Both worlds come from the brainstorm mockups (kept locally in `.superpowers/brainstorm/`, not committed). Both are light-only: the demo is projected, and dark mode is out of scope. Colours are CSS custom properties mapped to Tailwind v4 `@theme` tokens; components never use raw hex values.

### World B: customer (`/login`, `/chat`) · ui §7.1

Warm and plain-spoken, drawn from Latin American modernism: saturated cobalt, leaf green and sun yellow on white, with generous round shapes. Typeface: **Schibsted Grotesk** (400/600/800).

| Token | Value | Use |
|---|---|---|
| `b-surface` | `#FFFFFF` | page |
| `b-ink` | `#13203A` | text, device frame on /demo |
| `b-cobalt` | `#1F4FD8` | customer bubble, chips, links |
| `b-leaf` | `#0B7A4B` | primary confirm button, human-agent bubble |
| `b-sun` | `#F2C230` | accent (sparingly) |
| `b-sun-tint` | `#FFF6D6` | confirmation card, "data as of" banner |
| `b-mist` | `#EEF2FB` | assistant bubble, segmented control |
| `b-fog` | `#F4F6FA` | system lines, composer |

- **Radii:** bubbles 18px, with a 4px corner on the speaker's side; cards 20px; chips and buttons are pills.
- **Receipt chips:** green tint `#E3F4EA` / `#0B5A37` for a filed dispute, mist/cobalt for a reference.

### World C: staff (`/agent`, `/trace`, `/demo` canvas) · ui §7.2

Cool, precise and calm. The trace is the hero. Typeface: **Hanken Grotesk** (400/600/700), with tabular figures for all numbers.

| Token | Value | Use |
|---|---|---|
| `c-canvas` | `#F3F5F8` | page |
| `c-panel` | `#FFFFFF` | cards (1px `c-line` ring, no drop shadow) |
| `c-ink` | `#1E2A38` | text, threshold ticks, route strip |
| `c-muted` | `#5B6878` | secondary text |
| `c-line` | `#DCE2EA` | borders |
| `c-track` | `#E8ECF1` | gauge track |
| `c-below` | `#A7B1BE` | below-threshold fill |
| `c-signal` | `#2F6FEB` | primary actions, selection |
| `c-pass` | `#167A4D` | policy pass |
| `c-alert` | `#B52C6C` | policy fail, critical priority |
| `c-warn` | `#EDA100` | high priority |

- **Radii:** 8px for controls, 10px for panels.
- **Priority** is always shown as marker plus word ("Critical"), never as colour alone.

### Trace signal colours · ui §7.3

Each signal keeps its colour in every turn and session; colour follows the signal, never its rank. The 8 slots are the dataviz reference categorical palette, validated with `validate_palette.js --mode light`: all hard checks pass, worst adjacent colour-blind ΔE 9.1. Three slots are under 3:1 contrast against the surface, so every bar carries a visible text label and value.

| Slot | Hex | Signal |
|---|---|---|
| 1 | `#2A78D6` | `intent` (and `confirmation`*) |
| 2 | `#EB6834` | `target_transaction` |
| 3 | `#1BAF7A` | `dispute_reason` |
| 4 | `#EDA100` | `asks_for_human` |
| 5 | `#E87BA4` | `reports_unauthorized_use` |
| 6 | `#008300` | `legal_or_regulator_threat` |
| 7 | `#4A3AA7` | `distress` |
| 8 | `#E34948` | `injection_attempt` |

\* There are 9 questions but only 8 colours that stay distinguishable. `confirmation` shares slot 1: it only decides on the confirm step, where `intent` isn't read, and its row label always names it.

### Motion · ui §7.4

There's one orchestrated moment: **the trace block reveal** when a turn completes. The bars grow from 0 to their value over about 400 ms, staggered by 60 ms, then the route strip fades in. The "Analysing…" stage lights change state without animation. Nothing moves on page load. `prefers-reduced-motion` shows the final state at once.

## Surfaces · ui §8

### Customer chat (`/login`, `/chat`; world B, phone-first, responsive) · ui §8.1

- **Login:** Español/Português segmented control, a labelled demo identity picker, then the OTP (shown on screen, labelled demo). The chosen language sets `lang` in the JWT and selects the UI copy dictionary (`es`, `pt`).
- **Header:** "LATAM Bank" plus a language badge. Below it, a permanent banner: "Información al 17 jun 2026" / "Informações de 17 jun 2026" (from `data_as_of`).

| Contract field | Rendering |
|---|---|
| `reply_text` | Assistant bubble |
| `awaiting: clarification` + `options[]` | Chips. A tap sends the chip text as a normal customer message; it's in the transcript and Jev judges it. |
| `awaiting: confirmation` + `summary` | "Resumen de tu disputa" card (merchant, date, amount, reason, card last4) with *Confirmar y enviar* / *Cambiar algo*, which send those texts as messages |
| `refs[]` | Receipt chips: `DSP-…` (green, "enviada" only after read-back), `HND-…` (reference) |
| `awaiting: human` / `control` event | System line "Una persona del equipo continuará esta conversación"; on takeover "Ana, del equipo de LATAM Bank, se unió"; agent bubbles in leaf with a name |
| turn in flight | Typing indicator; composer stays enabled; messages queue in order |
| 401 | Bottom sheet to sign in again; the conversation stays on screen |

- **assistant-ui:**
  - `useExternalStoreRuntime` over a Zustand store that merges POST replies, pushed `message` events and history, de-duplicated by `message_id`.
  - Thread, composer and message are primitives styled in world B. Chips, the summary card, receipt chips, system lines and agent messages are custom message parts.
  - No default assistant-ui theme.
- **Mis casos / Meus casos:** a header button opens a bottom sheet (dialog; Escape, backdrop and *Cerrar* close it, focus returns to the button) listing the customer's disputes from `GET /api/customer/cases`, fetched on each open: reason, amount, short `DSP-…` id, date and a status pill (`submitted` Enviada, `pending_review` En revisión / Em análise, `resolved`, `rejected`). Empty state "No tienes casos abiertos" / "Você não tem casos abertos". Hidden in embed mode with the rest of the header.
- **Embed mode:** `/chat?embed=1` hides the page chrome and tells the parent its `sid` and turn events through `postMessage` (origin-checked) for `/demo`.

### Agent console (`/agent`, `/agent/[handoffId]`; world C, desktop) · ui §8.2

- **Staff sign-in:** `/login?staff=1` with a labelled staff identity.
- **Queue (left, 290px, live from `/queue`):**
  - Filters: Open · Mine · In takeover · Resolved.
  - Rows show a priority marker plus word, plain-language reason codes, language, amount, age, and who holds it.
  - Newly arrived rows get a one-time highlight.
- **Case header:** `HND-…`, customer id (no names exist in the curated data), language, data as-of, session, opened time, and a status pill.
  - Actions follow the lifecycle: **Claim** → **Take over chat** → **Return to assistant** / **Resolve…** (outcome code plus a note).
  - Buttons that aren't allowed are hidden, not disabled.
- **Packet tab:**
  - **Left column:** the customer request (original plus English), verified facts with receipt ids, actions taken.
  - **Right column:**
    - **"Why it came to you":** mini gauges for the signals that crossed, using the §7.3 colours;
    - policy checks with pass/fail marks;
    - open questions (at most 3).
- **Conversation tab:**
  - The transcript, showing customer, assistant, agent and system messages.
  - The composer is enabled only while this agent holds the takeover. The agent writes in the customer's language; the UI shows a reminder of that language.
- **Trace tab:** the §8.3 component for the session, with the newest turn on top, live over `/trace/<sid>`.

### Trace component (shared: console tab, `/trace/[sid]`, `/demo`) · ui §8.3

One **turn block** per turn: the customer quote plus English line, then the turn's duration, then:

1. **Open bars (at most 4)**, chosen in this order:
   1. escalation flags that crossed;
   2. the choice questions the chosen path read (`intent` always; `target_transaction` and `dispute_reason` on the dispute path; `confirmation` on the confirm step);
   3. the closest flag below threshold, only if a slot is left.

   Each bar:
   - a 0–1 track with the threshold tick labelled with its value;
   - the fill is `c-below` below the threshold, or the signal's §7.3 colour above it;
   - the value is labelled at the end of the fill;
   - the verdict is text plus icon: `✓ act`, `? below → clarify`, `⚑ handoff`, `⚑ offer human`, `⛔ blocked`.

   Choice questions also show the runner-up and margin. `target_transaction` also shows the resolver's top 3 and the top feature contributions from the `kind: model` record (for example "amount within 1% · date in range").
2. **A folded line:** "▸ N more signals below threshold · highest `<signal>` `<value>`", which expands to all bars.
3. **Reply check line**, from `verify_reply`: "Reply check k/n claims supported · no unverified promises". It expands when anything failed, and shows the regeneration or template fallback.
4. **Error rows** for `kind: error` records: "Jev unavailable → clarify", "Resolver failed → Jev alone".
5. **Route strip** (`c-ink`): the policy results that mattered (fails first), then "Route: `<edge>` · `<priority>`".

- **View model:** `GET /api/trace/:sid?turn=` maps `decision_records` to this structure on the server, including the question-set and thresholds versions (shown in a hover tooltip). The component only renders.
- **Collapsed state:** older turns collapse to the route strip.
- **Standalone page:** `/trace/[sid]` stacks every turn, with a header showing session, customer and language.

## Demo stage (`/demo`; staff sign-in; world C canvas, projector width ≥ 1280px) · ui §9

A stepper at the top: **1 Sign in → 2 Live conversation → 3 Scenarios → 4 Handoff**. The phone is the real `/chat?embed=1` inside a `b-ink` device frame; the customer and staff cookies coexist.

### Act 1: Sign in (once) · ui §9.1

The phone shows the real login. The right panel, "What just happened", checks off each step as it happens:

1. OTP verified.
2. Access token issued: the decoded claims (customer `sub`, session `sid`, language, scopes, expiry) from `/api/auth/debug-claims`, as text rows.
3. Realtime token issued: subscribe-only, this session's channel only.
4. First message: the AgentCore authorizer ✓, then the agent's own re-check ✓ ("the customer id comes from the token, never from the message"). This row completes on the first `turn_complete`.

### Act 2: Live conversation · ui §9.2

The presenter types freely.

- **While a turn runs,** the trace panel shows "Analysing turn N…" with four stage lights: Understand, Decide, Act, Verify reply. They light from the slim `/trace/<sid>` `record` events (`understand`/`extract`/`jev` → Understand, `route` → Decide, `tool`/`policy` → Act, `verify_reply` → Verify reply). No numbers show before the turn completes.
- **On `turn_complete`,** the block is fetched and revealed (§7.4). Earlier turns collapse to their route strips.

### Act 3: Scenarios · ui §9.3

A presenter rail on the left:

- **Scenario chips** (ES/PT), one per agent-core definition-of-done case:
  1. account inquiry (ES);
  2. decline explanation (PT);
  3. dispute filed after confirmation (ES);
  4. ambiguous → clarify;
  5. unsupported → abstain;
  6. unauthorized → handoff;
  7. injection refused;
  8. expired token.
- **Each chip starts a fresh conversation** with the demo identity tagged for it (§4.9). It puts the first scripted message into the phone's composer; the presenter presses send. Multi-turn scripts show the next message as the next chip.
- **Expired token:** the chip signs in with a 30-second token and prompts the presenter to wait, then send.
- **Handoff ticker** (from `/queue`): "HND-… arrived · critical" with *Open in console ↗*, for the takeover part of the demo.

### Act 4: Handoff (added 2026-10-05, not in ui §9)

The phone stays on the left; the right panel is the human-agent side of the same conversation (`components/demo/HandoffPanel.tsx`): one line with the as-is report's evidence medians for disputes (37.0 h first response, 15.5 d to resolve, 69.8 % still open), then the real console (`ConsoleWithTabs` with `caseOnly`: no queue, no top bar) on the newest handoff whose `session_id` is the phone's session, so Take over / Resolve and the composer work as in `/agent`. Until one exists it says so.

### Console stats (`/agent`, added 2026-10-05)

- Queue filter chips carry counts ("Open 3", "Mine 1"; `Console` loads all four filters at once), and the queue header shows the oldest open case's age.
- `CaseStats` under the case header: turns, mean reply time, template fallbacks (from `/api/trace/:sid`) and how long after the handoff the case was claimed (or how long it has waited).

## Accessibility and language · ui §11

- **Contrast:** WCAG 2.2 AA for text in both worlds. Signal colours under 3:1 always sit beside a text label and value (§7.3).
- **Screen readers:** new messages are announced through `aria-live="polite"` on the thread; the trace reveal announces "Turn N: route handoff".
- **Keyboard:**
  - every action is reachable, including chips and the summary card;
  - visible focus rings (`c-signal` / `b-cobalt`);
  - the console queue supports arrow keys and Enter.
- **Reduced motion:** see §7.4.
- **Copy:**
  - Customer copy lives in `es` and `pt` dictionaries. Money is formatted by currency code (COP without decimals, agent-core §6.3). Dates use the locale.
  - Staff copy is in English. Customer quotes are always shown in the original, with the English gloss from `extract` when there is one.
- **Plain language:** sentence case, active verbs, and the same action names across a flow ("Claim" → "Claimed").
