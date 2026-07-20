export interface RegionInfo {
  code: string;
  prefix: string;
  name: string;
  needs_nik: boolean;
  supported: boolean;
  needs_captcha?: boolean;
}

export interface VehicleData {
  plate: string;
  region: string;
  region_name: string;
  merk?: string;
  model?: string;
  tipe?: string;
  tahun?: number;
  warna?: string;
  jenis?: string;
  bahan_bakar?: string;
  cc?: string;
  pkb_pokok?: number;
  pkb_denda?: number;
  swdkllj_pokok?: number;
  swdkllj_denda?: number;
  total_tagihan?: number;
  jatuh_tempo_pajak?: string;
  jatuh_tempo_stnk?: string;
  status_pajak?: string;
  nama_pemilik?: string;
  alamat?: string;
  sumber?: string;
  catatan?: string;
  errors: string[];
}

export interface CheckResponse {
  status: "ok" | "error" | "nik_required" | "unsupported";
  plate: string;
  region: RegionInfo;
  data?: VehicleData;
  message?: string;
  cached?: boolean;
}

// Search types
export interface SearchParams {
  q?: string;
  region?: string;
  merk?: string;
  jenis?: string;
  warna?: string;
  tahun_min?: number;
  tahun_max?: number;
  limit?: number;
  offset?: number;
}

export interface SearchResult {
  total: number;
  limit: number;
  offset: number;
  results: VehicleData[];
}

export interface DbStats {
  total_vehicles: number;
  by_region: { region: string; name: string; count: number }[];
  top_merks: { merk: string; count: number }[];
}
