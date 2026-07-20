import type { CheckResponse } from "@/types/vehicle";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8000"
    : "https://api-ranmor.fortunamj.com");

export async function checkVehicle(
  plate: string,
  nik?: string
): Promise<CheckResponse> {
  const params = new URLSearchParams({ plate: plate.toUpperCase() });
  if (nik) params.set("nik", nik);

  const res = await fetch(`${API_URL}/check?${params.toString()}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

export async function detectRegion(plate: string) {
  const res = await fetch(
    `${API_URL}/region/${encodeURIComponent(plate.toUpperCase())}`
  );
  if (!res.ok) return null;
  return res.json();
}

export function formatRupiah(amount?: number): string {
  if (amount === undefined || amount === null) return "-";
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    minimumFractionDigits: 0,
  }).format(amount);
}
