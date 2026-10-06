# Pages, API routes and access

Every route of the deployed system, who may call it, and where that is enforced. Live app:
https://d21y0qq5d8ixnr.cloudfront.net. The specs behind this page are `context/ui-context.md` (BFF route handlers,
surfaces) and `context/architecture-context.md` (invocation contract, access controls).

## Who is who

- **Customer:** `demo01`–`demo20`, password `demo-NN`, then the on-screen OTP. Gets a 15-minute RS256 JWT
  (`role=customer`, `sub` = customer id, `sid` = conversation, `lang`, scopes `inquiry:read dispute:create`).
- **Staff:** `agent.ana`, `agent.luis`, `agent.bia`, password only (no OTP). Gets a staff JWT (`role=agent`). Staff
  credentials are not published: they are in the submission email. The demo-user picker returns customers only.
- The browser never holds an AWS credential or a JWT it can read: tokens live in httpOnly, Secure, SameSite=Lax cookies
  (`cust_session`, `staff_session`). The only token JavaScript sees is the subscribe-only realtime token.

## Pages

| Page | Who | Enforced by |
|---|---|---|
| `/login` | anyone | none. `?staff=1` switches to staff sign-in |
| `/chat` (`?embed=1` inside `/demo`) | customer | `web/proxy.ts` redirects to `/login` without `cust_session`; every call it makes is checked again |
| `/agent`, `/agent/[handoffId]` | staff | `web/proxy.ts` redirects to `/login?staff=1` without `staff_session`; the page verifies the staff JWT (`staffFromCookies`) |
| `/trace/[sid]` | staff | same as `/agent` |
| `/demo` | staff, demo deployments only | same as `/agent`, plus 404 unless `DEMO_MODE=1` (`web/app/demo/page.tsx`) |

`web/proxy.ts` only checks that the cookie exists; the signature, expiry and role are verified by the page and by
every API handler.

## Web API (`web/app/api/…`)

Every handler validates its input with Zod, verifies the cookie's JWT before any logic, and returns
`{data}` or `{error: {code, message}}`.

| Route | Who | Does |
|---|---|---|
| `POST /api/auth/login` | public | Customer login: proxies to the identity service, returns a 120 s login ticket |
| `POST /api/auth/otp` | public (needs a ticket) | Exchanges ticket + OTP for the customer JWT, sets `cust_session`; then, after the response, warms the conversation's agent session (`{"warmup": true}`) |
| `POST /api/auth/staff-login` | public | Staff login (password only), sets `staff_session` |
| `POST /api/auth/logout` | any | Clears the cookie |
| `GET /api/auth/demo-users` | public, demo deployments only | The login page's picker: customers only, never staff (404 outside demo mode) |
| `GET /api/auth/realtime-token` | customer or staff | Subscribe-only AppSync token |
| `GET /api/auth/debug-claims` | staff, demo only | Decoded claims of the customer signed in on the same browser (`/demo` Act 1) |
| `POST /api/chat` | customer | If a person holds the conversation, stores the message and returns `awaiting: human`. Otherwise calls AgentCore with the customer's JWT, the runtime session id and the message id. Writes one JSON log line per call (`status`, `ms`, `sid`, `client_message_id`, `turn_id`) |
| `GET /api/sessions/:sid/messages?after=` | the owning customer, or staff | History. A customer must match both `sid` and `customer_id`; anyone else gets the same 404 as a missing session |
| `POST /api/sessions/:sid/messages` | staff holding the takeover | A staff message; 409 unless `control = human:<that staff user>` |
| `GET /api/handoffs?status=` | staff | Queue |
| `GET /api/handoffs/:id` | staff | The `handoff.v1` packet |
| `POST /api/handoffs/:id/{claim,takeover,return,resolve}` | staff | Case lifecycle (conditional writes; a lost race is a 409) |
| `GET /api/trace/:sid?turn=` | staff | Trace view model built from the decision records |

## Agent (AgentCore Runtime `lb_demo_agent`, endpoint `live`)

`POST /invocations` (AgentCore adds `GET /ping`). Called only by the web server, with the customer's JWT in
`Authorization`; the AgentCore JWT authorizer checks it, and `agent/src/bankagent/app.py` verifies it again. The
customer id comes only from the token's `sub`, never from the body.

| Request body | Result |
|---|---|
| `{message, client_message_id, lang}` | One turn. Reply: `{reply_text, language, awaiting, options[], refs[], data_as_of, turn_id, summary?}`; `summary` (with `card_hash`) only when awaiting a confirmation |
| `{message: "confirm:<card_hash>"}` while awaiting a confirmation | Confirms in code by exact comparison (no model reads it); a stale or wrong hash files nothing and shows the card again |
| `{warmup: true}` | No turn: builds the runtime and reads the caller's accounts once; returns `{warm: true|false}` |

Errors come back as a normal reply with `error`: `auth_required`, `session_expired`, `identity_unavailable`,
`invalid_message`, `duplicate_in_progress`, `turn_failed`. Every request writes one
`request <outcome> <session> <message_id>` log line (see `docs/operations.md`).

## Identity service (API Gateway + Lambda, throttled at 10 req/s, burst 20)

| Route | Does |
|---|---|
| `POST /auth/login` | Customer username + password → login ticket (120 s) |
| `POST /auth/otp` | Ticket + OTP → customer JWT (15 min); refused for staff users |
| `POST /auth/staff/login` | Staff username + password → staff JWT |
| `POST /auth/realtime-token` | A valid JWT → subscribe-only realtime token |
| `GET /auth/demo-users` | Demo picker; customers only |
| `GET /.well-known/openid-configuration`, `GET /jwks.json` | Issuer metadata and public keys (AgentCore and the web server verify tokens with them) |

## Realtime (AppSync Events)

Channels `/session/<sid>`, `/queue/all`, `/trace/<sid>`. A Lambda authorizer checks the realtime token; a customer
may subscribe only to its own `/session/<sid>`, staff to any. Only the publisher Lambdas (IAM, fed by DynamoDB streams)
can publish.

## Trust between services

| From → To | How |
|---|---|
| Browser → web server | httpOnly, Secure, SameSite=Lax cookie with the 15-minute JWT; HTTPS through CloudFront; the load balancer accepts only CloudFront |
| Web server → identity | HTTPS; public login routes, throttled at the API stage |
| Web server → AgentCore | The customer's JWT only; the ECS task role has no `InvokeAgentRuntime` permission |
| Agent → Bedrock | Assumes a cross-account role in the AI Account with an external id; receipts are redacted (no customer or product ids, no fraud fields) |
| Agent → Jev | API key from Secrets Manager (`lb-demo/jev`); Jev sees transactions as aliases, never customer or product ids |
| Agent → S3 serving set, DynamoDB | Execution role: read-only on the serving bucket (`GetObject`, `ListBucket`), item access on the six `lb-demo-*` tables (`DeleteItem` only on checkpoints) (`infra/terraform/agent/iam.tf`) |
| Browser → AppSync | Subscribe-only realtime token → Lambda authorizer → channel check |
| Publisher → AppSync | IAM, `appsync:EventPublish` on this API only |
