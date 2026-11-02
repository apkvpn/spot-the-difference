import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { desc } from "drizzle-orm";
import { NextResponse } from "next/server";
import { db } from "@/db";
import { jobs } from "@/db/schema";
import { FFMPEG, FFPROBE, jobDir, spawnWorker, syncJob } from "@/lib/jobs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DURATIONS = [5, 10, 15, 20];
const TYPES = ["mixed", "park", "beach", "space", "city", "farm", "underwater", "winter"];
const STYLES = ["mixed", "vivid", "pastel", "night", "retro"];

export async function GET() {
  const rows = await db.select().from(jobs).orderBy(desc(jobs.createdAt)).limit(30);
  const out = await Promise.all(rows.map((r) => syncJob(r)));
  return NextResponse.json(out.map(({ log: _log, ...r }) => r));
}

export async function POST(req: Request) {
  const fd = await req.formData();
  const raw = fd.get("settings");
  if (typeof raw !== "string") return NextResponse.json({ error: "settings missing" }, { status: 400 });
  const s = JSON.parse(raw) as Record<string, unknown>;
  const duration = Number(s.duration_min);
  if (!DURATIONS.includes(duration)) return NextResponse.json({ error: "مدت نامعتبر" }, { status: 400 });
  const source = s.source === "upload" ? "upload" : "ai";
  const id = crypto.randomBytes(6).toString("hex");
  const dir = jobDir(id);
  fs.mkdirSync(path.join(dir, "input"), { recursive: true });

  const images: { file: string; original: string; diffs: string }[] = [];
  if (source === "upload") {
    const files = fd.getAll("images").filter((f): f is File => typeof f !== "string");
    const diffs = fd.getAll("diffs").map((d) => (typeof d === "string" ? d : ""));
    if (!files.length) return NextResponse.json({ error: "هیچ تصویری ارسال نشد" }, { status: 400 });
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const ext = (path.extname(f.name) || ".png").toLowerCase().replace(/[^.a-z0-9]/g, "");
      const name = `${String(i).padStart(3, "0")}${ext}`;
      fs.writeFileSync(path.join(dir, "input", name), Buffer.from(await f.arrayBuffer()));
      images.push({ file: name, original: f.name, diffs: diffs[i] ?? "" });
    }
  }
  const episode = s.episode ? Math.max(1, Math.min(9999, Number(s.episode) || 0)) : null;
  const positions = Array.isArray(s.cta_positions)
    ? (s.cta_positions as string[]).filter((p) => ["start", "middle", "end"].includes(p))
    : [];
  const config = {
    duration_min: duration,
    source,
    images,
    ai_count: Math.max(0, Math.min(40, Number(s.ai_count) || 0)),
    ai_diffs: Math.max(1, Math.min(7, Number(s.ai_diffs) || 5)),
    ai_type: TYPES.includes(String(s.ai_type)) ? s.ai_type : "mixed",
    ai_style: STYLES.includes(String(s.ai_style)) ? s.ai_style : "mixed",
    episode,
    channel: String(s.channel ?? "").slice(0, 40),
    cta_enabled: Boolean(s.cta_enabled),
    cta_positions: positions,
    seed: Math.floor(Math.random() * 100000),
    ffmpeg: FFMPEG,
    ffprobe: FFPROBE,
  };
  fs.writeFileSync(path.join(dir, "config.json"), JSON.stringify(config, null, 2));
  const title =
    `${episode ? `قسمت ${episode} • ` : ""}${duration} دقیقه • ` +
    (source === "upload" ? `${images.length} تصویر شما` : `تصاویر خودکار (${config.ai_type}/${config.ai_style})`);
  const settings = { ...config, ffmpeg: undefined, ffprobe: undefined };
  await db.insert(jobs).values({ id, title, settings, status: "queued", stage: "در صف" });
  const pid = spawnWorker(id);
  const { eq } = await import("drizzle-orm");
  await db.update(jobs).set({ pid: pid ?? null }).where(eq(jobs.id, id));
  return NextResponse.json({ id });
}
