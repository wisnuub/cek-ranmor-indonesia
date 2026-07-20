export interface RegionInfo {
  code: string;
  prefix: string;
  name: string;
  needs_nik: boolean;
  supported: boolean;
}

export interface VehicleData {
  plate: string;
  region: string;
  region_name: string;

  // Kendaraan
  merk?: string;
  model?: string;
  tipe?: string;
  tahun?: number;
  warna?: string;
  jenis?: string;
  bahan_bakar?: string;
  cc?: string;

  // Pajak
  pkb_pokok?: number;
  pkb_denda?: number;
  swdkllj_pokok?: number;
  swdkllj_denda?: number;
  total_tagihan?: number;
  jatuh_tempo_pajak?: string;
  jatuh_tempo_stnk?: string;
  status_pajak?: string;

  // Pemilik
  nama_pemilik?: string;
  alamat?: string;

  // Meta
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
