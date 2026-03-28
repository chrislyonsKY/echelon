const RTL_LANGUAGES = new Set(["ar", "fa", "he", "ur"]);

const LANGUAGE_LABELS: Record<string, string> = {
  ar: "Arabic",
  en: "English",
  es: "Spanish",
  fa: "Farsi",
  fr: "French",
  he: "Hebrew",
  ru: "Russian",
  tr: "Turkish",
  uk: "Ukrainian",
  und: "Unknown",
};

type TextBearingRecord = {
  displayTitle?: string | null;
  displayDescription?: string | null;
  title?: string | null;
  description?: string | null;
  titleOriginal?: string | null;
  descriptionOriginal?: string | null;
  titleTranslated?: string | null;
  descriptionTranslated?: string | null;
  language?: string | null;
  textDirection?: string | null;
  signalType?: string;
  rawPayload?: Record<string, unknown>;
};

export function normalizeLanguageCode(value?: string | null): string {
  if (!value) return "und";
  const normalized = value.trim().toLowerCase().replace("_", "-");
  if (!normalized) return "und";
  return normalized.split("-", 1)[0] || "und";
}

export function languageLabel(value?: string | null): string {
  const normalized = normalizeLanguageCode(value);
  return LANGUAGE_LABELS[normalized] || normalized.toUpperCase();
}

export function isRtlLanguage(value?: string | null): boolean {
  return RTL_LANGUAGES.has(normalizeLanguageCode(value));
}

export function textDirectionForRecord(record?: Pick<TextBearingRecord, "textDirection" | "language"> | null): "ltr" | "rtl" {
  if (record?.textDirection === "rtl") return "rtl";
  if (record?.textDirection === "ltr") return "ltr";
  return isRtlLanguage(record?.language) ? "rtl" : "ltr";
}

export function getDisplayTitle(record: TextBearingRecord, fallback?: string): string {
  const payload = record.rawPayload || {};
  const infraType = asString(payload.infra_type)?.replace(/_/g, " ");

  return (
    record.displayTitle ||
    record.titleTranslated ||
    asString(payload.title_translated) ||
    record.titleOriginal ||
    asString(payload.title_original) ||
    record.title ||
    asString(payload.title) ||
    asString(payload.callsign) ||
    asString(payload.name) ||
    infraType ||
    fallback ||
    (record.signalType ? record.signalType.replace(/_/g, " ") : "Untitled")
  );
}

export function getOriginalTitle(record: TextBearingRecord): string | null {
  const payload = record.rawPayload || {};
  return record.titleOriginal || asString(payload.title_original) || record.title || asString(payload.title) || null;
}

export function getDisplayDescription(record: TextBearingRecord): string | null {
  const payload = record.rawPayload || {};
  return (
    record.displayDescription ||
    record.descriptionTranslated ||
    asString(payload.description_translated) ||
    record.descriptionOriginal ||
    asString(payload.description_original) ||
    record.description ||
    asString(payload.description) ||
    null
  );
}

export function getOriginalDescription(record: TextBearingRecord): string | null {
  const payload = record.rawPayload || {};
  return record.descriptionOriginal || asString(payload.description_original) || record.description || asString(payload.description) || null;
}

export function hasTranslation(record: TextBearingRecord): boolean {
  const payload = record.rawPayload || {};
  return Boolean(record.titleTranslated || record.descriptionTranslated || payload.title_translated || payload.description_translated);
}

export function truncateText(value: string | null | undefined, length: number): string {
  const text = (value || "").trim();
  if (!text) return "";
  if (text.length <= length) return text;
  return `${text.slice(0, Math.max(0, length - 1)).trimEnd()}…`;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}
