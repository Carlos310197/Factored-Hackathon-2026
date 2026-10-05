import { util } from "@aws-appsync/utils";

// UI spec §3 rule 4: customers only their own /session/<sid>; agents any session, /queue/all and traces.
const STAFF_NAMESPACES = ["session", "queue", "trace"];

function allowed(segments, c) {
  if (!c || !segments || segments.length === 0 || segments.indexOf("") !== -1) return false;
  const ns = segments[0];
  if (c.role === "agent") return STAFF_NAMESPACES.indexOf(ns) !== -1;
  if (c.role === "customer") return ns === "session" && segments.length === 2 && segments[1] === c.sid;
  return false;
}

export function onSubscribe(ctx) {
  const identity = ctx.identity || {};
  // Unit 53 left open which field carries the authorizer context, so read both.
  const c = identity.handlerContext || identity.resolverContext;
  console.log("identity keys:", Object.keys(identity));
  if (!allowed(ctx.info.channel.segments, c)) {
    util.unauthorized();
  }
}

export function onPublish(ctx) {
  // Browsers (Lambda-authorizer identity) never publish; IAM publishers carry no handler/resolver context.
  const identity = ctx.identity || {};
  if (identity.handlerContext || identity.resolverContext) util.unauthorized();
  return ctx.events;
}

// APPSYNC_JS rejects calling an inline-exported function from another handler; export the helper here (tests use it).
export { allowed };
