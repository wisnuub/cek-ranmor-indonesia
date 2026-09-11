/**
 * Beberapa daerah (mis. Jawa Tengah) tidak mengembalikan nama model kendaraan
 * yang sesungguhnya — field "tipe"/"model" dari API-nya cuma mengulang merk
 * atau CC. Helper di sini menyaring info yang benar-benar deskriptif, dan
 * kalau tidak ada, membuat judul fallback dari jenis + merk + CC
 * (contoh: "Motor Honda 110cc", "Minibus Mitsubishi 1499cc").
 */

interface VehicleLike {
  merk?: string | null;
  model?: string | null;
  tipe?: string | null;
  jenis?: string | null;
  cc?: string | null;
}

export function isMotorJenis(jenis?: string | null): boolean {
  const j = (jenis ?? "").toUpperCase();
  if (j.includes("MOBIL")) return false;
  return j.includes("SPM") || j.includes("SEPEDA MOTOR") || j.includes("MOTOR");
}

export function jenisLabel(jenis?: string | null): string {
  const j = (jenis ?? "").toUpperCase();
  if (isMotorJenis(jenis)) return "Motor";
  if (j.includes("MINIBUS")) return "Minibus";
  if (j.includes("BUS")) return "Bus";
  if (j.includes("PICK")) return "Pick Up";
  if (j.includes("TRUK") || j.includes("TRUCK")) return "Truk";
  if (j.includes("SEDAN")) return "Sedan";
  if (j.includes("JEEP")) return "Jeep";
  if (j.includes("MOBIL") || j.includes("PENUMPANG")) return "Mobil";
  return "Kendaraan";
}

export function vehicleDisplayName(v: VehicleLike, fallback = "Kendaraan Bermotor"): string {
  const parts = [v.merk, v.model, v.tipe].filter(Boolean) as string[];
  const unique = parts.filter(
    (val, i) => parts.findIndex((x) => x.toLowerCase() === val.toLowerCase()) === i
  );

  // Lebih dari satu nilai unik → ada info model/tipe yang sesungguhnya deskriptif
  if (unique.length > 1) return unique.join(" ");

  // Cuma merk (atau kosong) — susun judul dari jenis + merk + cc
  if (v.merk && v.cc) return `${jenisLabel(v.jenis)} ${v.merk} ${v.cc}cc`;

  return unique.join(" ") || fallback;
}
