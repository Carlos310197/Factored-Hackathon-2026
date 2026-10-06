import { safeNext } from "@/lib/safe-next";

export function redirectToStaffLogin(): void {
  const here = safeNext(window.location.pathname + window.location.search, "/agent");
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- full page load on purpose
  window.location.href = `/login?staff=1&next=${encodeURIComponent(here)}`;
}
