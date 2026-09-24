import { NextResponse, type NextRequest } from "next/server";

const ALLOWED =
  /^(stats|categories|settings|settings\/secrets|settings\/test|fleet|fleet\/cloud\/(start|stop)|bots|models|leads|leads\/export|leads\/purge-synthetic|leads\/[0-9a-fA-F-]{36}|jobs|jobs\/[0-9a-fA-F-]{36}|jobs\/[0-9a-fA-F-]{36}\/(start|pause|stop|logs)|hosts|hosts\/[a-z0-9_]+|hosts\/[a-z0-9_]+\/(test|start|stop|refresh)|performance|errors|activity)$/;

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const joined = path.join("/");
  if (!ALLOWED.test(joined)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  const base = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
  const token = process.env.INTERNAL_API_TOKEN || "";
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const response = await fetch(`${base}/${joined}${request.nextUrl.search}`, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
    cache: "no-store",
  });
  const out = new Headers();
  const type = response.headers.get("content-type");
  if (type) out.set("Content-Type", type);
  const disposition = response.headers.get("content-disposition");
  if (disposition) out.set("Content-Disposition", disposition);
  return new NextResponse(await response.arrayBuffer(), { status: response.status, headers: out });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
