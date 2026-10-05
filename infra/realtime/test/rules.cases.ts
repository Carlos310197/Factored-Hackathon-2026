export const CASES: Array<[string, string[], { role: string; sid: string } | undefined, boolean]> = [
  ["customer own session", ["session", "S-1"], { role: "customer", sid: "S-1" }, true],
  ["customer other session", ["session", "S-2"], { role: "customer", sid: "S-1" }, false],
  ["customer session sub-path", ["session", "S-1", "x"], { role: "customer", sid: "S-1" }, false],
  ["customer queue", ["queue", "all"], { role: "customer", sid: "S-1" }, false],
  ["customer trace", ["trace", "S-1"], { role: "customer", sid: "S-1" }, false],
  ["agent session", ["session", "S-9"], { role: "agent", sid: "STAFF-1" }, true],
  ["agent queue", ["queue", "all"], { role: "agent", sid: "STAFF-1" }, true],
  ["agent trace", ["trace", "S-9"], { role: "agent", sid: "STAFF-1" }, true],
  ["agent unknown namespace", ["admin", "x"], { role: "agent", sid: "STAFF-1" }, false],
  ["no identity", ["session", "S-1"], undefined, false],
  ["unknown role", ["session", "S-1"], { role: "root", sid: "S-1" }, false],
  ["empty path", [], { role: "agent", sid: "STAFF-1" }, false],
];
