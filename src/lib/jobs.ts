import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { eq } from "drizzle-orm";
import { db } from "@/db";
import { jobs, type Job } from "@/db/schema";

export const ROOT = process.cwd();
export const DATA_DIR = path.join(ROOT, "data");
export const JOBS_DIR = path.join(DATA_DIR, "jobs");
export const FFMPEG = path.join(ROOT, "node_modules", "ffmpeg-static", "ffmpeg");
export const FFPROBE = path.join(ROOT, "node_modules", "ffprobe-static", "bin", "linux", "x64", "ffprobe");

export function jobDir(id: string) {
  if (!/^[a-z0-9]+$/.test(id)) throw new Error("bad id");
  return path.join(JOBS_DIR, id);
}

export type WorkerStatus = {
  status: string;
  progress: number;
  stage: string;
  log: string[];
  report: unknown;
  output: string | null;
  error: string | null;
};

export function readStatus(id: string): WorkerStatus | null {
  try {
    return JSON.parse(fs.readFileSync(path.join(jobDir(id), "status.json"), "utf8"));
  } catch {
    return null;
  }
}

function alive(pid: number | null) {
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

export function spawnWorker(id: string): number | undefined {
  const dir = jobDir(id);
  const out = fs.openSync(path.join(dir, "worker.log"), "a");
  const child = spawn("python3", [path.join(ROOT, "worker", "sdv.py"), dir], {
    cwd: ROOT,
    detached: true,
    stdio: ["ignore", out, out],
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
  });
  child.unref();
  return child.pid;
}

/** Sync DB row with the worker's status.json and return the merged view. */
export async function syncJob(job: Job) {
  const st = readStatus(job.id);
  let status = job.status;
  let progress = job.progress;
  let stage = job.stage;
  let error = job.error;
  let report = job.report;
  if (st) {
    status = st.status;
    progress = st.progress;
    stage = st.stage;
    error = st.error;
    if (st.report) report = st.report;
  }
  const running = status === "running" || status === "queued";
  const stalled = running && !alive(job.pid);
  if (
    status !== job.status ||
    progress !== job.progress ||
    stage !== job.stage ||
    error !== job.error ||
    (st?.report && !job.report)
  ) {
    await db
      .update(jobs)
      .set({ status, progress, stage, error, report: report ?? null, updatedAt: new Date() })
      .where(eq(jobs.id, job.id));
  }
  return {
    ...job,
    status,
    progress,
    stage,
    error,
    report,
    stalled,
    log: st?.log ?? [],
    hasVideo: fs.existsSync(path.join(jobDir(job.id), "video.mp4")),
  };
}
