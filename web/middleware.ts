import { NextResponse, type NextRequest } from "next/server";
import { verifySession } from "./lib/session";

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname === "/login" || pathname.startsWith("/api/login")) {
    return NextResponse.next();
  }
  const ok = await verifySession(request.cookies.get("ih_session")?.value, process.env.AUTH_SECRET || "");
  if (ok) return NextResponse.next();
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ detail: "Sign in required" }, { status: 401 });
  }
  const url = request.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|favicon.svg|icon.svg).*)"],
};
