const BYDAY_LABELS = {
  MO: "пн",
  TU: "вт",
  WE: "ср",
  TH: "чт",
  FR: "пт",
  SA: "сб",
  SU: "вс",
};

const PRESET_LABELS = {
  daily: "Ежедневно",
  weekdays: "По будням",
  weekly: "Еженедельно",
  monthly: "Ежемесячно",
};

function formatDue(iso) {
  if (!iso) return "без даты";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function presetFromRrule(rrule) {
  if (!rrule) return null;
  if (rrule.startsWith("FREQ=DAILY")) return "daily";
  if (rrule.includes("BYDAY=MO,TU,WE,TH,FR")) return "weekdays";
  if (rrule.startsWith("FREQ=WEEKLY")) return "weekly";
  if (rrule.startsWith("FREQ=MONTHLY")) return "monthly";
  return null;
}

function formatRecurrence(item) {
  if (item?.recurrence_label) return item.recurrence_label;
  if (!item?.is_recurring || !item?.rrule) return "";
  const rrule = item.rrule;
  const preset = presetFromRrule(rrule);
  if (preset === "weekly") {
    for (const [code, label] of Object.entries(BYDAY_LABELS)) {
      if (rrule.includes(`BYDAY=${code}`) && !rrule.includes("MO,TU")) {
        return `${PRESET_LABELS.weekly} (${label})`;
      }
    }
  }
  if (preset === "monthly" && rrule.includes("BYMONTHDAY=")) {
    const day = rrule.split("BYMONTHDAY=")[1].split(";")[0];
    return `${PRESET_LABELS.monthly} (${day}-го)`;
  }
  if (preset && PRESET_LABELS[preset]) return PRESET_LABELS[preset];
  return "да";
}

function itemMeta(item) {
  const parts = [];
  if (item.due_at) parts.push(`📅 ${formatDue(item.due_at)}`);
  if (item.notifications_enabled) parts.push("🔔");
  const recur = formatRecurrence(item);
  if (recur) parts.push(`🔁 ${recur}`);
  return parts.join(" ");
}
