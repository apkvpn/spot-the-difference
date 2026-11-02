export type Report = {
  pictures: { index: number; name: string; file: string; diffs: { n: number; emoji: string; text: string; src?: string }[] }[];
  analysis: { file: string; notes: string[]; ok: boolean }[];
  excluded: { file: string; reason: string }[];
  warnings: string[];
  timestamps: { t: number; ts: string; label: string }[];
  countdown: number;
  narration: boolean;
  episode: number | null;
  probe: { width: number; height: number; fps: string; duration: number; size_mb: number };
};

export function buildPost(r: Report, channel: string, minutes: number) {
  const n = r.pictures.length;
  const diffCounts = r.pictures.map((p) => p.diffs.length);
  const total = diffCounts.reduce((a, b) => a + b, 0);
  const same = diffCounts.every((c) => c === diffCounts[0]);
  const per = same ? `${diffCounts[0]}` : `${Math.min(...diffCounts)}-${Math.max(...diffCounts)}`;
  const ep = r.episode ? ` #${r.episode}` : "";
  const sec = r.countdown;
  const titles: [string, string][] = [
    [`Find ${per} Differences in ${sec} Seconds!${ep}`, `${per} تفاوت را در ${sec} ثانیه پیدا کن!`],
    [`Spot the Difference: ${n} Fun Picture Puzzles${ep}`, `تفاوت‌یابی: ${n} پازل تصویری سرگرم‌کننده`],
    [`Can You Find All ${total} Differences?${ep}`, `می‌توانی هر ${total} تفاوت را پیدا کنی؟`],
    [`Only Sharp Eyes Find All Differences${ep}`, `فقط چشم‌های تیزبین همه‌ی تفاوت‌ها را پیدا می‌کنند`],
    [`Spot ${per} Differences Before Time Runs Out${ep}`, `قبل از تمام شدن وقت ${per} تفاوت را پیدا کن`],
    [`${minutes} Minute Spot the Difference Challenge${ep}`, `چالش ${minutes} دقیقه‌ای تفاوت‌یابی`],
    [`Relaxing Spot the Difference Brain Game${ep}`, `بازی فکری آرامش‌بخش تفاوت‌یابی`],
    [`Test Your Eyes: Find the Differences${ep}`, `چشم‌هایت را امتحان کن: تفاوت‌ها را پیدا کن`],
    [`Cute Cartoon Picture Puzzles for Everyone${ep}`, `پازل‌های تصویری کارتونی بامزه برای همه`],
    [`How Many Differences Can You Spot?${ep}`, `چند تفاوت می‌توانی پیدا کنی؟`],
  ];
  const stamps = r.timestamps.map((t) => `${t.ts} ${t.label}`).join("\n");
  const ch = channel ? ` on ${channel}` : "";
  const descEn =
    `Can you spot all the differences? 🔍 ${n} picture puzzles, ${per} differences each, ${sec} seconds per picture. ` +
    `Watch the timer, then check the answers with circles and arrows!\n\n` +
    `Comment how many you found and subscribe${ch} for new puzzles every week! 👍🔔\n\n⏱️ Timestamps\n${stamps}`;
  const descFa =
    `می‌توانی همه‌ی تفاوت‌ها را پیدا کنی؟ 🔍 ${n} پازل تصویری، هر کدام ${per} تفاوت، و ${sec} ثانیه برای هر تصویر. ` +
    `بعد از تمام شدن تایمر، جواب‌ها با دایره و فلش نشان داده می‌شوند!\n\n` +
    `در کامنت بنویس چندتا پیدا کردی و برای پازل‌های جدید سابسکرایب کن! 👍🔔`;
  const hashtags = ["#spotthedifference", "#findthedifference", "#puzzle", "#braingames", "#picturepuzzle", "#eyetest", "#brainteaser"];
  const tags = [
    "spot the difference", "find the difference", "spot the difference game", "picture puzzle", "brain game",
    "puzzle game", "find 5 differences", "eye test", "brain teaser", "visual puzzle", "kids puzzle", "family game",
  ];
  const pinned = `How many did you find? 0 to ${total} 👇 (${n} pictures, ${per} differences each)`;
  const tips = [
    "Made for kids: اگر مخاطب اصلی کودکان هستند «Yes» بزنید (کامنت‌ها و اعلان‌ها محدود می‌شوند)؛ برای مخاطب عمومی «No».",
    "عدد تفاوت‌ها در تیتر با ویدیو یکی است؛ ادعاهایی مثل «۹۹٪ نمی‌توانند» آماری بی‌پایه‌اند — بهتر است استفاده نشوند.",
    "تامنیل: یک تصویر از ویدیو + عدد تفاوت‌ها + رنگ‌های روشن.",
    "تایم‌استمپ‌ها از زمان‌بندی خود فایل محاسبه شده‌اند و Chapters یوتیوب را می‌سازند (اولین باید 0:00 باشد).",
  ];
  return { titles, descEn, descFa, stamps, hashtags, tags, pinned, tips };
}
