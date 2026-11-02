import fs from "node:fs";
import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { db } from "@/db";
import { jobs } from "@/db/schema";
import { jobDir, spawnWorker, syncJob } from "@/lib/jobs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function load(id: string) {
  if (!/^[a-z0-9]+$/.test(id)) return null;
  const [row] = await db.select().from(jobs).where(eq(jobs.id, id));
  return row ?? null;
}

export async function GET(_req: Request, ctx: RouteContext<"/api/jobs/[id]">) {
  const { id } = await ctx.params;
  const row = await load(id);
  if (!row) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json(await syncJob(row));
}

/** Resume a stalled/failed job (already-encoded segments are reused). */
export async function POST(_req: Request, ctx: RouteContext<"/api/jobs/[id]">) {
  const { id } = await ctx.params;
  const row = await load(id);
  if (!row) return NextResponse.json({ error: "not found" }, { status: 404 });
  const pid = spawnWorker(id);
  await db.update(jobs).set({ pid: pid ?? null, status: "queued", error: null }).where(eq(jobs.id, id));
  return NextResponse.json({ ok: true });
}

export async function DELETE(_req: Request, ctx: RouteContext<"/api/jobs/[id]">) {
  const { id } = await ctx.params;
  const row = await load(id);
  if (!row) return NextResponse.json({ error: "not found" }, { status: 404 });
  if (row.pid) {
    try {
      process.kill(-row.pid, "SIGTERM");
    } catch {}
  }
  fs.rmSync(jobDir(id), { recursive: true, force: true });
  await db.delete(jobs).where(eq(jobs.id, id));
  return NextResponse.json({ ok: true });
}
