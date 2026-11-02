"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { buildPost, type Report } from "@/lib/post";

type JobView = {
  id: string;
  title: string;
  status: string;
  progress: number;
  stage: string;
  error: string | null;
  report: Report | null;
  stalled: boolean;
  log: string[];
  hasVideo: boolean;
  settings: { channel?: string; duration_min?: number };
};

function Copy({ text }: { text: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      type="button"
      className="chip !px-3 !py-1 text-sm"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setOk(true);
        setTimeout(() => setOk(false), 1200);
      }}
    >
      {ok ? "کپی شد ✓" : "کپی"}
    </button>
  );
}

const SRC_FA: Record<string, string> = { user: "از لیست شما (تأیید شد)", auto: "پیدا شده خودکار", generated: "ساخته‌شده و تأیید عددی" };

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<JobView | null>(null);
  const [showPost, setShowPost] = useState(false);

  useEffect(() => {
    let stop = false;
    const load = async () => {
      const r = await fetch(`/api/jobs/${id}`);
      if (!r.ok) return;
      const j = (await r.json()) as JobView;
      if (!stop) setJob(j);
      if (!stop && j.status !== "done" && j.status !== "error") setTimeout(load, 3000);
    };
    load();
    return () => {
      stop = true;
    };
  }, [id]);

  if (!job) return <main className="p-10 text-center">در حال بارگذاری…</main>;
  const r = job.report;
  const post = r ? buildPost(r, job.settings.channel ?? "", job.settings.duration_min ?? 5) : null;

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/" className="chip">
          → بازگشت
        </Link>
        <h1 className="text-2xl font-extrabold">{job.title}</h1>
        <button
          className="chip mr-auto !border-red-200 text-red-600"
          onClick={async () => {
            if (!confirm("حذف این ویدیو؟")) return;
            await fetch(`/api/jobs/${id}`, { method: "DELETE" });
            router.push("/");
          }}
        >
          حذف
        </button>
      </div>

      {job.status !== "done" && (
        <section className="card rainbow-border space-y-3 p-6">
          <div className="flex items-center justify-between font-bold">
            <span>{job.status === "error" ? "❌ خطا" : `⚙️ ${job.stage}`}</span>
            <span>{job.progress}%</span>
          </div>
          <div className="h-4 overflow-hidden rounded-full bg-[#eee6ff]">
            <div className="h-full bg-gradient-to-l from-[#ff4f9a] via-[#ffc928] to-[#7b4dff] transition-all" style={{ width: `${job.progress}%` }} />
          </div>
          {job.error && <p className="rounded-xl bg-red-50 p-3 text-red-700">{job.error}</p>}
          {(job.stalled || job.status === "error") && (
            <button
              className="btn"
              onClick={async () => {
                await fetch(`/api/jobs/${id}`, { method: "POST" });
                location.reload();
              }}
            >
              🔁 ادامه‌ی ساخت (بخش‌های آماده دوباره ساخته نمی‌شوند)
            </button>
          )}
          <pre dir="rtl" className="max-h-60 overflow-auto rounded-xl bg-[#2b1650] p-3 text-xs leading-6 text-[#e9e1ff]">
            {job.log.join("\n") || "…"}
          </pre>
          <p className="text-sm opacity-70">ساخت ویدیو در پس‌زمینه انجام می‌شود؛ می‌توانید صفحه را ببندید و بعداً برگردید.</p>
        </section>
      )}

      {job.status === "done" && job.hasVideo && r && (
        <>
          <section className="card rainbow-border space-y-4 p-4">
            <video controls preload="metadata" className="w-full rounded-2xl bg-black" src={`/api/jobs/${id}/video`} />
            <div className="flex flex-wrap items-center gap-3">
              <a className="btn" href={`/api/jobs/${id}/video?download=1`}>
                ⬇️ دانلود MP4
              </a>
              <span className="text-sm" dir="ltr">
                {r.probe.width}×{r.probe.height} • {r.probe.fps} fps • {Math.floor(r.probe.duration / 60)}:
                {String(Math.round(r.probe.duration % 60)).padStart(2, "0")} • {r.probe.size_mb} MB • H.264 + AAC
              </span>
              <span className="text-sm">
                شمارش هر تصویر: {r.countdown} ثانیه • راوی: {r.narration ? "Kokoro (af_heart)" : "بدون راوی"} • سلامت فایل: ffprobe + decode کامل ✓
              </span>
            </div>
          </section>

          <section className="card space-y-4 p-6">
            <h2 className="text-xl font-extrabold">✅ چه چیزی تأیید یا حذف شد</h2>
            {r.warnings.map((w, i) => (
              <p key={i} className="rounded-xl bg-amber-50 p-3 text-amber-800">
                ⚠️ {w}
              </p>
            ))}
            {r.excluded.map((e, i) => (
              <p key={i} className="rounded-xl bg-red-50 p-3 text-red-700">
                🚫 کنار گذاشته شد: <b dir="ltr">{e.file}</b> — {e.reason}
              </p>
            ))}
            {r.analysis.some((a) => a.notes.length) && (
              <div className="space-y-2">
                <h3 className="font-bold">تغییرات نسبت به لیست شما:</h3>
                {r.analysis
                  .filter((a) => a.notes.length)
                  .map((a, i) => (
                    <div key={i} className="rounded-xl bg-white p-3 text-sm">
                      <b dir="ltr">{a.file}</b>
                      <ul className="mt-1 list-disc pr-5">
                        {a.notes.map((n, k) => (
                          <li key={k}>{n}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
              </div>
            )}
            <div className="grid gap-3 md:grid-cols-2">
              {r.pictures.map((p) => (
                <div key={p.index} className="rounded-2xl bg-white p-4">
                  <div className="mb-2 font-bold">
                    تصویر {p.index}: <span dir="ltr">{p.name}</span> — {p.diffs.length} تفاوت
                  </div>
                  <ol className="space-y-1 text-sm" dir="ltr">
                    {p.diffs.map((d) => (
                      <li key={d.n} className="flex gap-2">
                        <span className="font-bold text-[#ff3b3b]">{d.n}.</span>
                        <span>
                          {d.emoji} {d.text}
                          <span className="mr-1 text-xs opacity-60" dir="rtl">
                            {" "}
                            ({SRC_FA[d.src ?? ""] ?? ""})
                          </span>
                        </span>
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          </section>

          <section className="card space-y-4 p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-extrabold">📝 ۱۰ تیتر و پست کامل یوتیوب</h2>
              <button className="btn" onClick={() => setShowPost((s) => !s)}>
                {showPost ? "بستن" : "نوشتن تیتر و پست"}
              </button>
            </div>
            {showPost && post && (
              <div className="space-y-5">
                <div className="space-y-2">
                  <h3 className="font-bold">تیترها</h3>
                  {post.titles.map(([en, fa], i) => (
                    <div key={i} className="flex items-start gap-2 rounded-xl bg-white p-3">
                      <div className="flex-1">
                        <div dir="ltr" className="fredoka text-lg">
                          {i + 1}. {en}
                        </div>
                        <div className="text-sm opacity-75">{fa}</div>
                      </div>
                      <Copy text={en} />
                    </div>
                  ))}
                </div>
                {[
                  ["توضیحات (انگلیسی + تایم‌استمپ)", post.descEn, "ltr"],
                  ["ترجمه‌ی فارسی توضیحات", post.descFa, "rtl"],
                  ["تایم‌استمپ‌ها", post.stamps, "ltr"],
                  ["هشتگ‌ها (۳ تای اول مهم‌ترین)", post.hashtags.join(" "), "ltr"],
                  ["تگ‌ها", post.tags.join(", "), "ltr"],
                  ["کامنت سنجاق‌شده", post.pinned, "ltr"],
                ].map(([label, text, dir]) => (
                  <div key={label} className="rounded-xl bg-white p-3">
                    <div className="mb-1 flex items-center justify-between font-bold">
                      {label} <Copy text={text} />
                    </div>
                    <pre dir={dir as "ltr" | "rtl"} className="whitespace-pre-wrap font-sans text-sm">
                      {text}
                    </pre>
                  </div>
                ))}
                <ul className="list-disc space-y-1 pr-5 text-sm">
                  {post.tips.map((t, i) => (
                    <li key={i}>{t}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
