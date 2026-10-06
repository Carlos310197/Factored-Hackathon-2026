import { util } from "@aws-appsync/utils";

// Customers may read only their own /session/<sid>; agents read any session, /queue/all and traces.
const STAFF_NAMESPACES = ["session", "queue", "trace"];

// Not exported: APPSYNC_JS namespace code may export only its handlers (onSubscribe/onPublish).
function allowed(segments, c) {
  if (!c || !segments || segments.length === 0 || segments.indexOf("") !== -1) return false;
  const ns = segments[0];
  if (c.role === "agent") return STAFF_NAMESPACES.indexOf(ns) !== -1;
  if (c.role === "customer") return ns === "session" && segments.length === 2 && segments[1] === c.sid;
  return false;
}

export function onSubscribe(ctx) {
  const identity = ctx.identity || {};
  const c = identity.handlerContext || identity.resolverContext;
  // Object.keys(ctx.identity) is [] in APPSYNC_JS, so log the field name explicitly.
  console.log("auth context field:", identity.handlerContext ? "handlerContext" : identity.resolverContext ? "resolverContext" : "none");
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

