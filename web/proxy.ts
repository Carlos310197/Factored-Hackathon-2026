import { NextResponse, type NextRequest } from "next/server";

/** Presence check only; pages and handlers verify tokens themselves. */
export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const staffArea = ["/agent", "/trace", "/demo"].some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (staffArea && !req.cookies.has("staff_session")) {
    return NextResponse.redirect(new URL(`/login?staff=1&next=${encodeURIComponent(pathname)}`, req.url));
  }
  if (pathname === "/chat" && !req.cookies.has("cust_session")) {
    const embed = req.nextUrl.searchParams.get("embed") === "1" ? "&embed=1" : "";
    return NextResponse.redirect(new URL(`/login?next=/chat${embed}`, req.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ["/chat/:path*", "/agent/:path*", "/trace/:path*", "/demo/:path*"] };
