import { API_URL } from "@/lib/api";

export async function GET() {
  try {
    const res = await fetch(`${API_URL}/healthz`, { cache: "no-store" });
    const body = await res.json();
    return Response.json({ api: res.ok ? body : "unreachable" }, { status: res.ok ? 200 : 502 });
  } catch {
    return Response.json({ api: "unreachable" }, { status: 502 });
  }
}
