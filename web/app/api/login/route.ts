import { NextResponse } from "next/server";
import { passwordsMatch, signSession } from "../../../lib/session";

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const password = typeof body.password === "string" ? body.password : "";
  const expected = process.env.DEMO_PASSWORD || "";
  if (!passwordsMatch(password, expected)) {
    return NextResponse.json({ detail: "Incorrect password" }, { status: 401 });
  }
  const secret = process.env.AUTH_SECRET || "";
  if (!secret) {
    return NextResponse.json({ detail: "AUTH_SECRET is not configured" }, { status: 503 });
  }
  const expiresAt = Date.now() + 7 * 24 * 60 * 60 * 1000;
  const response = NextResponse.json({ ok: true });
  response.cookies.set("ih_session", await signSession(secret, expiresAt), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.COOKIE_SECURE === "true",
    path: "/",
    maxAge: 7 * 24 * 60 * 60,
  });
  return response;
}
