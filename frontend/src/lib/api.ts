import type { CheckResponse, SearchParams, SearchResult, DbStats } from "@/types/vehicle";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8000"
    : "https://api-ranmor.fortunamj.com");

export interface CrawlerRegionStatus {
  running: boolean;
  tried: number;
  found: number;
  last: string;
  current_suffix: string;
  kab?: string;
  suffix_found: number;
  consecutive_empty: number;
  status: string;
}

export interface CrawlerStatus {
  crawlers: Record<string, CrawlerRegionStatus>;
  db: DbStats;
}

export async function getCrawlerStatus(): Promise<CrawlerStatus> {
  return apiFetch<CrawlerStatus>("/crawler/status");
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function checkVehicle(plate: string, nik?: string): Promise<CheckResponse> {
  const params = new URLSearchParams({ plate: plate.toUpperCase() });
  if (nik) params.set("nik", nik);
  return apiFetch<CheckResponse>(`/check?${params}`);
}

export async function detectRegion(plate: string) {
  const res = await fetch(`${API_URL}/region/${encodeURIComponent(plate.toUpperCase())}`);
  if (!res.ok) return null;
  return res.json();
}

export async function searchVehicles(params: SearchParams): Promise<SearchResult> {
  const qs = new URLSearchParams();
  if (params.q)         qs.set("q", params.q);
  if (params.region)    qs.set("region", params.region);
  if (params.merk)      qs.set("merk", params.merk);
  if (params.jenis)     qs.set("jenis", params.jenis);
  if (params.warna)     qs.set("warna", params.warna);
  if (params.tahun_min) qs.set("tahun_min", String(params.tahun_min));
  if (params.tahun_max) qs.set("tahun_max", String(params.tahun_max));
  if (params.limit)     qs.set("limit",  String(params.limit));
  if (params.offset)    qs.set("offset", String(params.offset));
  return apiFetch<SearchResult>(`/search?${qs}`);
}

export async function getStats(): Promise<DbStats> {
  return apiFetch<DbStats>("/stats");
}

export function formatRupiah(amount?: number): string {
  if (amount === undefined || amount === null) return "-";
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    minimumFractionDigits: 0,
  }).format(amount);
}

export const REGIONS = [
  { code: "jakarta", name: "DKI Jakarta" },
  { code: "jabar",   name: "Jawa Barat" },
  { code: "banten",  name: "Banten" },
  { code: "jateng",  name: "Jawa Tengah" },
  { code: "diy",     name: "DI Yogyakarta" },
  { code: "jatim",   name: "Jawa Timur" },
  { code: "bali",    name: "Bali" },
];

export const JENIS_LIST = [
  "Sepeda Motor",
  "Mobil Penumpang",
  "Mobil Bus",
  "Mobil Barang",
  "Kendaraan Khusus",
];
