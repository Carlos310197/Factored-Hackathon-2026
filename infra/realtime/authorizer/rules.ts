// Same rule as handlers/namespace.js (APPSYNC_JS can't import this file); both are tested with test/rules.cases.ts.
const STAFF_NAMESPACES = ["session", "queue", "trace"];

export function channelAllowed(segments: string[], c: { role: string; sid: string } | undefined): boolean {
  if (!c || segments.length === 0) return false;
  const ns = segments[0];
  if (c.role === "agent") return STAFF_NAMESPACES.includes(ns);
  if (c.role === "customer") return ns === "session" && segments.length === 2 && segments[1] === c.sid;
  return false;
}

export function segmentsOf(channel: string): string[] {
  return channel.split("/").filter(Boolean);
}
