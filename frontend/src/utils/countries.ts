export type CountryBbox = [number, number, number, number];

export interface CountryDefinition {
  name: string;
  iso2: string;
  flag: string;
  bbox: CountryBbox;
}

const COUNTRY_LIST: CountryDefinition[] = [
  { name: "Gaza", iso2: "PS", flag: "🇵🇸", bbox: [34.2, 31.2, 34.6, 31.7] },
  { name: "Taiwan", iso2: "TW", flag: "🇹🇼", bbox: [119.2, 21.8, 122.1, 25.4] },
  { name: "Israel", iso2: "IL", flag: "🇮🇱", bbox: [34.2, 29.4, 35.9, 33.4] },
  { name: "Lebanon", iso2: "LB", flag: "🇱🇧", bbox: [35.1, 33.0, 36.7, 34.7] },
  { name: "Jordan", iso2: "JO", flag: "🇯🇴", bbox: [34.9, 29.0, 39.4, 33.4] },
  { name: "Syria", iso2: "SY", flag: "🇸🇾", bbox: [35.5, 32.0, 42.5, 37.5] },
  { name: "Iraq", iso2: "IQ", flag: "🇮🇶", bbox: [38.5, 29.0, 48.6, 37.4] },
  { name: "Iran", iso2: "IR", flag: "🇮🇷", bbox: [44.0, 25.0, 63.0, 40.0] },
  { name: "Afghanistan", iso2: "AF", flag: "🇦🇫", bbox: [60.5, 29.3, 75.2, 38.7] },
  { name: "Pakistan", iso2: "PK", flag: "🇵🇰", bbox: [60.8, 23.5, 77.9, 37.1] },
  { name: "Turkey", iso2: "TR", flag: "🇹🇷", bbox: [25.6, 35.8, 44.9, 42.1] },
  { name: "Yemen", iso2: "YE", flag: "🇾🇪", bbox: [42.5, 12.0, 54.5, 19.0] },
  { name: "Saudi Arabia", iso2: "SA", flag: "🇸🇦", bbox: [34.5, 16.0, 55.7, 32.5] },
  { name: "Egypt", iso2: "EG", flag: "🇪🇬", bbox: [24.5, 21.5, 36.9, 31.8] },
  { name: "Sudan", iso2: "SD", flag: "🇸🇩", bbox: [21.8, 8.7, 38.6, 22.2] },
  { name: "Ethiopia", iso2: "ET", flag: "🇪🇹", bbox: [32.9, 3.4, 48.0, 14.9] },
  { name: "Ukraine", iso2: "UA", flag: "🇺🇦", bbox: [22.0, 44.0, 40.3, 52.4] },
  { name: "Russia", iso2: "RU", flag: "🇷🇺", bbox: [27.0, 41.2, 180.0, 81.9] },
  { name: "China", iso2: "CN", flag: "🇨🇳", bbox: [73.5, 18.0, 134.8, 53.6] },
  { name: "Venezuela", iso2: "VE", flag: "🇻🇪", bbox: [-73.4, 0.6, -59.8, 12.3] },
];

export const MONITORED_COUNTRIES: Record<string, CountryDefinition> = Object.fromEntries(
  COUNTRY_LIST.map((country) => [country.name, country])
);

const COUNTRY_ALIASES: Record<string, string> = {
  usa: "United States",
  us: "United States",
  "united states": "United States",
  "united kingdom": "United Kingdom",
  uk: "United Kingdom",
  iran: "Iran",
  israel: "Israel",
  russia: "Russia",
  ukraine: "Ukraine",
  syria: "Syria",
  iraq: "Iraq",
  yemen: "Yemen",
  egypt: "Egypt",
  turkey: "Turkey",
  saudi: "Saudi Arabia",
  "saudi arabia": "Saudi Arabia",
  lebanon: "Lebanon",
  jordan: "Jordan",
  afghanistan: "Afghanistan",
  pakistan: "Pakistan",
  china: "China",
  taiwan: "Taiwan",
  venezuela: "Venezuela",
  sudan: "Sudan",
  ethiopia: "Ethiopia",
  gaza: "Gaza",
};

const FALLBACK_FLAGS: Record<string, string> = {
  "United States": "🇺🇸",
  "United Kingdom": "🇬🇧",
};

const BY_AREA = [...COUNTRY_LIST].sort((a, b) => bboxArea(a.bbox) - bboxArea(b.bbox));

export function findCountryByName(name?: string | null): CountryDefinition | null {
  if (!name) return null;
  const trimmed = name.trim();
  if (!trimmed) return null;
  if (MONITORED_COUNTRIES[trimmed]) return MONITORED_COUNTRIES[trimmed];
  const canonical = COUNTRY_ALIASES[trimmed.toLowerCase()];
  if (canonical && MONITORED_COUNTRIES[canonical]) return MONITORED_COUNTRIES[canonical];
  return null;
}

export function countryFlagForName(name?: string | null): string {
  const country = findCountryByName(name);
  if (country) return country.flag;
  if (!name) return "";
  return FALLBACK_FLAGS[name.trim()] || "";
}

export function countryForCoordinates(lat: number, lng: number): CountryDefinition | null {
  const clampedLng = normalizeLongitude(lng);
  for (const country of BY_AREA) {
    if (contains(country.bbox, lat, clampedLng)) return country;
  }
  return null;
}

export function countryLabelFromCoordinates(lat: number, lng: number): string {
  const country = countryForCoordinates(lat, lng);
  if (!country) return "Unknown AOI";
  return `${country.flag} ${country.name}`;
}

function contains([minLng, minLat, maxLng, maxLat]: CountryBbox, lat: number, lng: number): boolean {
  return lng >= minLng && lng <= maxLng && lat >= minLat && lat <= maxLat;
}

function bboxArea([minLng, minLat, maxLng, maxLat]: CountryBbox): number {
  return Math.abs((maxLng - minLng) * (maxLat - minLat));
}

function normalizeLongitude(value: number): number {
  if (!Number.isFinite(value)) return 0;
  let lng = value;
  while (lng < -180) lng += 360;
  while (lng > 180) lng -= 360;
  return lng;
}

