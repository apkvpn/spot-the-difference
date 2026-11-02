import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import { jobDir } from "@/lib/jobs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: Request, ctx: RouteContext<"/api/jobs/[id]/video">) {
  const { id } = await ctx.params;
  if (!/^[a-z0-9]+$/.test(id)) return new Response("bad id", { status: 400 });
  const file = path.join(jobDir(id), "video.mp4");
  if (!fs.existsSync(file)) return new Response("not ready", { status: 404 });
  const size = fs.statSync(file).size;
  const url = new URL(req.url);
  const headers: Record<string, string> = {
    "Content-Type": "video/mp4",
    "Accept-Ranges": "bytes",
  };
  if (url.searchParams.get("download")) {
    headers["Content-Disposition"] = `attachment; filename="spot-the-difference-${id}.mp4"`;
  }
  const range = req.headers.get("range");
  if (range) {
    const m = /bytes=(\d*)-(\d*)/.exec(range);
    const start = m && m[1] ? parseInt(m[1], 10) : 0;
    const end = m && m[2] ? Math.min(parseInt(m[2], 10), size - 1) : size - 1;
    if (start >= size || start > end) {
      return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${size}` } });
    }
    const stream = Readable.toWeb(fs.createReadStream(file, { start, end })) as ReadableStream;
    return new Response(stream, {
      status: 206,
      headers: { ...headers, "Content-Range": `bytes ${start}-${end}/${size}`, "Content-Length": String(end - start + 1) },
    });
  }
  const stream = Readable.toWeb(fs.createReadStream(file)) as ReadableStream;
  return new Response(stream, { headers: { ...headers, "Content-Length": String(size) } });
}
