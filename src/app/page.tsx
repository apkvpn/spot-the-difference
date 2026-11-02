"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type JobRow = { id: string; title: string; status: string; progress: number; stage: string; createdAt: string; hasVideo: boolean };
type Item = { file: File; url: string; diffs: string };

const TYPES: [string, string][] = [
  ["mixed", "ترکیبی (همه)"],
  ["park", "پارک 🌳"],
  ["beach", "ساحل 🏖️"],
  ["space", "فضا 🚀"],
  ["city", "شهر 🏙️"],
  ["farm", "مزرعه 🍎"],
  ["underwater", "زیر دریا 🐟"],
  ["winter", "زمستان ⛄"],
];
const STYLES: [string, string][] = [
  ["mixed", "ترکیبی"],
  ["vivid", "کارتونی پررنگ"],
  ["pastel", "پاستلی"],
  ["night", "شب"],
  ["retro", "رترو"],
];
const STATUS_FA: Record<string, string> = { queued: "در صف", running: "در حال ساخت", done: "آماده ✅", error: "خطا ❌" };

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" className="chip" data-on={on} onClick={onClick}>
      {children}
    </button>
  );
}

export default function Home() {
  const router = useRouter();
  const [duration, setDuration] = useState(5);
  const [source, setSource] = useState<"ai" | "upload">("ai");
  const [items, setItems] = useState<Item[]>([]);
  const [aiCount, setAiCount] = useState(0);
  const [aiDiffs, setAiDiffs] = useState(5);
  const [aiType, setAiType] = useState("mixed");
  const [aiStyle, setAiStyle] = useState("mixed");
  const [episode, setEpisode] = useState("");
  const [channel, setChannel] = useState("");
  const [cta, setCta] = useState(true);
  const [ctaPos, setCtaPos] = useState<string[]>(["end"]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [list, setList] = useState<JobRow[]>([]);

  useEffect(() => {
    const load = () => fetch("/api/jobs").then((r) => r.json()).then(setList).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const addFiles = (fl: FileList | null) => {
    if (!fl) return;
    const arr = Array.from(fl)
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
      .map((file) => ({ file, url: URL.createObjectURL(file), diffs: "" }));
    setItems((p) => [...p, ...arr]);
  };
  const move = (i: number, d: number) =>
    setItems((p) => {
      const n = [...p];
      const j = i + d;
      if (j < 0 || j >= n.length) return p;
      [n[i], n[j]] = [n[j], n[i]];
      return n;
    });

  const autoCount = Math.max(1, Math.floor((duration * 60 - 24) / (38 + 5 + 4.8 * aiDiffs)));

  async function submit() {
    setErr("");
    if (source === "upload" && !items.length) return setErr("حداقل یک تصویر جفتی انتخاب کنید.");
    setBusy(true);
    const fd = new FormData();
    fd.append(
      "settings",
      JSON.stringify({
        duration_min: duration,
        source,
        ai_count: aiCount,
        ai_diffs: aiDiffs,
        ai_type: aiType,
        ai_style: aiStyle,
        episode: episode || null,
        channel,
        cta_enabled: cta,
        cta_positions: ctaPos,
      }),
    );
    if (source === "upload")
      items.forEach((it) => {
        fd.append("images", it.file);
        fd.append("diffs", it.diffs);
      });
    const r = await fetch("/api/jobs", { method: "POST", body: fd });
    const j = await r.json();
    setBusy(false);
    if (!r.ok) return setErr(j.error || "خطا");
    router.push(`/jobs/${j.id}`);
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-8 text-center">
        <h1 className="fredoka text-4xl font-bold md:text-5xl">
          <span className="text-[#ff4f9a]">Spot</span> <span className="text-[#7b4dff]">the</span>{" "}
          <span className="text-[#43c95c]">Difference</span> <span className="text-[#ff8a1f]">Maker</span> 🔍
        </h1>
        <p className="mt-3 text-lg">
          سازنده‌ی ویدیوی MP4 واقعی تفاوت‌یابی برای یوتیوب: ۱۹۲۰×۱۰۸۰، ۶۰ فریم، راوی Kokoro، موسیقی، تایمر و پاسخ‌ها
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="card rainbow-border space-y-6 p-6 lg:col-span-2">
          <div>
            <h2 className="mb-2 text-xl font-extrabold">⏱️ مدت ویدیو</h2>
            <div className="flex flex-wrap gap-2">
              {[5, 10, 15, 20].map((d) => (
                <Chip key={d} on={duration === d} onClick={() => setDuration(d)}>
                  {d} دقیقه
                </Chip>
              ))}
            </div>
          </div>

          <div>
            <h2 className="mb-2 text-xl font-extrabold">🖼️ منبع تصاویر</h2>
            <div className="flex flex-wrap gap-2">
              <Chip on={source === "ai"} onClick={() => setSource("ai")}>
                پیش‌فرض: ساخت خودکار تصاویر 🤖
              </Chip>
              <Chip on={source === "upload"} onClick={() => setSource("upload")}>
                لیست عکس‌های ارسالی شما 📤
              </Chip>
            </div>

            {source === "ai" ? (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="font-semibold">تعداد تصویر</span>
                  <input
                    type="number"
                    min={0}
                    max={40}
                    className="field mt-1"
                    value={aiCount}
                    onChange={(e) => setAiCount(Number(e.target.value))}
                  />
                  <span className="text-sm opacity-70">۰ = خودکار (برای {duration} دقیقه حدود {autoCount} تصویر، شمارش ≥۳۶ ثانیه)</span>
                </label>
                <label className="block">
                  <span className="font-semibold">تعداد تفاوت در هر تصویر</span>
                  <input
                    type="number"
                    min={1}
                    max={7}
                    className="field mt-1"
                    value={aiDiffs}
                    onChange={(e) => setAiDiffs(Number(e.target.value))}
                  />
                </label>
                <label className="block">
                  <span className="font-semibold">نوع صحنه</span>
                  <select className="field mt-1" value={aiType} onChange={(e) => setAiType(e.target.value)}>
                    {TYPES.map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="font-semibold">سبک</span>
                  <select className="field mt-1" value={aiStyle} onChange={(e) => setAiStyle(e.target.value)}>
                    {STYLES.map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="text-sm opacity-75 md:col-span-2">
                  تصاویر کارتونی به‌صورت خودکار تولید می‌شوند و تفاوت‌ها با مختصات دقیق ساخته و بعد به‌صورت عددی دوباره تأیید می‌شوند.
                </p>
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                <label className="block cursor-pointer rounded-2xl border-2 border-dashed border-[#7b4dff] bg-white/70 p-6 text-center font-semibold">
                  ➕ انتخاب تصاویر جفتی (هر فایل = دو تصویر کنار هم چپ/راست یا بالا/پایین)
                  <input type="file" accept="image/*" multiple className="hidden" onChange={(e) => addFiles(e.target.files)} />
                </label>
                <p className="text-sm opacity-75">
                  ترتیب پخش = ترتیب لیست. لیست تفاوت اختیاری است؛ هر خط: <code dir="ltr">x%, y% | 🎈 The balloon is red on the left, but blue on the right</code>{" "}
                  (مختصات نسبت به نیمه‌ی چپ/بالا). هر مورد روی تصویر بررسی می‌شود و موارد نادرست حذف می‌شوند. اگر خالی بماند، تفاوت‌ها خودکار پیدا می‌شوند.
                </p>
                {items.map((it, i) => (
                  <div key={it.url} className="flex gap-3 rounded-2xl bg-white p-3 shadow-sm">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={it.url} alt="" className="h-24 w-40 rounded-xl object-cover" />
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2 text-sm font-bold">
                        <span className="rounded-full bg-[#7b4dff] px-2 text-white">{i + 1}</span>
                        <span className="truncate" dir="ltr">
                          {it.file.name}
                        </span>
                        <span className="mr-auto flex gap-1">
                          <button type="button" className="chip !px-2 !py-0" onClick={() => move(i, -1)}>
                            ▲
                          </button>
                          <button type="button" className="chip !px-2 !py-0" onClick={() => move(i, 1)}>
                            ▼
                          </button>
                          <button type="button" className="chip !px-2 !py-0" onClick={() => setItems((p) => p.filter((_, j) => j !== i))}>
                            ✕
                          </button>
                        </span>
                      </div>
                      <textarea
                        dir="ltr"
                        className="field h-16 text-sm"
                        placeholder="(optional) 30, 45 | 🎈 The balloon is red on the left, but blue on the right"
                        value={it.diffs}
                        onChange={(e) => setItems((p) => p.map((x, j) => (j === i ? { ...x, diffs: e.target.value } : x)))}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="text-xl font-extrabold">🔢 قسمت (اختیاری)</span>
              <input
                type="number"
                min={1}
                className="field mt-1"
                placeholder="مثلاً 12 → «Episode 12» اول ویدیو"
                value={episode}
                onChange={(e) => setEpisode(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-xl font-extrabold">📺 اسم چنل</span>
              <input dir="ltr" className="field mt-1" placeholder="Puzzle Land" value={channel} onChange={(e) => setChannel(e.target.value)} />
              <span className="text-sm opacity-70">برای نمایش روی ویدیو، حروف انگلیسی بنویسید</span>
            </label>
          </div>

          <div>
            <label className="flex items-center gap-2 text-xl font-extrabold">
              <input type="checkbox" className="h-5 w-5 accent-[#ff4f9a]" checked={cta} onChange={(e) => setCta(e.target.checked)} />
              👍🔔 نمایش پیشنهاد لایک و سابسکرایب (با اسم چنل)
            </label>
            {cta && (
              <div className="mt-2 flex flex-wrap gap-2">
                {[
                  ["start", "اول ویدیو"],
                  ["middle", "اواسط ویدیو"],
                  ["end", "انتهای ویدیو"],
                ].map(([v, l]) => (
                  <Chip
                    key={v}
                    on={ctaPos.includes(v)}
                    onClick={() => setCtaPos((p) => (p.includes(v) ? p.filter((x) => x !== v) : [...p, v]))}
                  >
                    {l}
                  </Chip>
                ))}
              </div>
            )}
          </div>

          {err && <p className="rounded-xl bg-red-100 p-3 font-bold text-red-700">{err}</p>}
          <button className="btn w-full text-xl" disabled={busy} onClick={submit}>
            {busy ? "در حال ارسال…" : "🎬 ساخت ویدیوی MP4"}
          </button>
        </section>

        <aside className="card space-y-3 p-5">
          <h2 className="text-xl font-extrabold">📁 ویدیوهای ساخته‌شده</h2>
          {!list.length && <p className="opacity-70">هنوز ویدیویی ساخته نشده.</p>}
          {list.map((j) => (
            <Link key={j.id} href={`/jobs/${j.id}`} className="block rounded-2xl bg-white p-3 shadow-sm hover:shadow-md">
              <div className="text-sm font-bold">{j.title}</div>
              <div className="mt-1 flex items-center justify-between text-xs">
                <span>{STATUS_FA[j.status] ?? j.status}</span>
                <span dir="ltr">{new Date(j.createdAt).toLocaleString("fa-IR")}</span>
              </div>
              {j.status !== "done" && j.status !== "error" && (
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#eee6ff]">
                  <div className="h-full bg-gradient-to-l from-[#ff4f9a] to-[#7b4dff]" style={{ width: `${j.progress}%` }} />
                </div>
              )}
            </Link>
          ))}
        </aside>
      </div>
    </main>
  );
}
