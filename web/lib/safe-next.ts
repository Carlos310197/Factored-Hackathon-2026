/** Same-site path only. Rejects "//h", "/\h" and tab/CR/LF forms that WHATWG URL parsing turns into another host. */
export function safeNext(v: string | undefined, fallback = "/chat"): string {
  return v && /^\/(?![/\\])[^\\\t\r\n]*$/.test(v) ? v : fallback;
}
