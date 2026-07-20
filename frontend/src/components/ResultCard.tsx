"use client";

import type { CheckResponse } from "@/types/vehicle";
import { formatRupiah } from "@/lib/api";
import {
  Car, Calendar, Palette, Fuel, MapPin,
  AlertCircle, CheckCircle, Clock, ExternalLink,
  ShieldAlert, Info,
} from "lucide-react";

interface Props {
  result: CheckResponse;
}

export default function ResultCard({ result }: Props) {
  const { status, data, region, message } = result;

  /* ── NIK Required ─────────────────────────────────────────── */
  if (status === "nik_required") {
    return (
      <div className="card mt-6 space-y-3">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-yellow-100 rounded-xl">
            <ShieldAlert className="w-5 h-5 text-yellow-600" />
          </div>
          <div>
            <p className="font-semibold text-gray-800">NIK Diperlukan</p>
            <p className="text-sm text-gray-500 mt-0.5">
              {region.name} mengharuskan NIK pemilik kendaraan untuk keamanan data.
            </p>
          </div>
        </div>
        <p className="text-sm text-gray-600 bg-yellow-50 border border-yellow-200 rounded-xl p-3">
          Silakan masukkan NIK (16 digit) di kolom opsional di atas, lalu cari lagi.
        </p>
      </div>
    );
  }

  /* ── Unsupported ────────────────────────────────────────────── */
  if (status === "unsupported") {
    return (
      <div className="card mt-6 space-y-3">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-blue-100 rounded-xl">
            <Info className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="font-semibold text-gray-800">Belum Didukung</p>
            <p className="text-sm text-gray-500 mt-0.5">{message}</p>
          </div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-3">
          <p className="text-xs text-blue-700 font-medium">Plat terdeteksi: {region.name} ({region.prefix})</p>
          <p className="text-xs text-blue-600 mt-1">
            Kami sedang menambahkan dukungan untuk lebih banyak daerah. Stay tuned!
          </p>
        </div>
      </div>
    );
  }

  /* ── Error ──────────────────────────────────────────────────── */
  if (!data || (data.errors && data.errors.length > 0 && !data.merk)) {
    return (
      <div className="card mt-6 space-y-3">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-red-100 rounded-xl">
            <AlertCircle className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <p className="font-semibold text-gray-800">Data Tidak Ditemukan</p>
            <p className="text-sm text-gray-500 mt-0.5">
              {data?.errors?.[0] || "Cek nomor polisi dan pastikan kendaraan terdaftar di Samsat."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const totalBayar = data.total_tagihan ?? 0;
  const hasDenda = (data.pkb_denda ?? 0) + (data.swdkllj_denda ?? 0) > 0;
  const statusColor = data.status_pajak === "Lunas"
    ? "badge-green"
    : data.status_pajak === "Belum Lunas"
    ? "badge-red"
    : "badge-gray";

  return (
    <div className="card mt-6 space-y-0 overflow-hidden">

      {/* ── Header ── */}
      <div className="flex items-start gap-3 pb-4 border-b border-gray-100">
        <div className="p-2.5 bg-red-50 rounded-xl">
          <Car className="w-6 h-6 text-red-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-gray-900 text-base leading-tight">
            {[data.merk, data.model, data.tipe].filter(Boolean).join(" ") || "Kendaraan Bermotor"}
          </p>
          <p className="text-xs text-gray-500 mt-0.5 font-mono tracking-widest">{data.plate}</p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className="badge badge-blue">{region.name}</span>
          {data.status_pajak && (
            <span className={`badge ${statusColor}`}>
              {data.status_pajak === "Lunas"
                ? <CheckCircle className="w-3 h-3" />
                : <AlertCircle className="w-3 h-3" />}
              {data.status_pajak}
            </span>
          )}
        </div>
      </div>

      {/* ── Info Kendaraan ── */}
      <div className="py-4 space-y-0">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Informasi Kendaraan
        </p>
        {[
          { icon: <Car className="w-3.5 h-3.5" />, label: "Merk / Model", value: [data.merk, data.model].filter(Boolean).join(" / ") },
          { icon: <Calendar className="w-3.5 h-3.5" />, label: "Tahun", value: data.tahun?.toString() },
          { icon: <Palette className="w-3.5 h-3.5" />, label: "Warna", value: data.warna },
          { icon: <Car className="w-3.5 h-3.5" />, label: "Jenis", value: data.jenis },
          { icon: <Fuel className="w-3.5 h-3.5" />, label: "Bahan Bakar", value: data.bahan_bakar },
          { icon: null, label: "CC", value: data.cc },
        ].filter(r => r.value).map((row, i) => (
          <div key={i} className="info-row">
            <span className="info-label flex items-center gap-1.5">
              {row.icon && <span className="text-gray-400">{row.icon}</span>}
              {row.label}
            </span>
            <span className="info-value">{row.value}</span>
          </div>
        ))}
      </div>

      {/* ── Kepemilikan ── */}
      {(data.nama_pemilik || data.alamat) && (
        <div className="py-4 border-t border-gray-100 space-y-0">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Data Kepemilikan
          </p>
          {data.nama_pemilik && (
            <div className="info-row">
              <span className="info-label">Nama Pemilik</span>
              <span className="info-value">{data.nama_pemilik}</span>
            </div>
          )}
          {data.alamat && (
            <div className="info-row">
              <span className="info-label flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-gray-400" />
                Alamat
              </span>
              <span className="info-value text-xs">{data.alamat}</span>
            </div>
          )}
        </div>
      )}

      {/* ── Masa Berlaku ── */}
      {(data.jatuh_tempo_pajak || data.jatuh_tempo_stnk) && (
        <div className="py-4 border-t border-gray-100 space-y-0">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Masa Berlaku
          </p>
          {data.jatuh_tempo_pajak && (
            <div className="info-row">
              <span className="info-label flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                Pajak JT
              </span>
              <span className="info-value font-mono">{data.jatuh_tempo_pajak}</span>
            </div>
          )}
          {data.jatuh_tempo_stnk && (
            <div className="info-row">
              <span className="info-label flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-gray-400" />
                STNK Berlaku s/d
              </span>
              <span className="info-value font-mono">{data.jatuh_tempo_stnk}</span>
            </div>
          )}
        </div>
      )}

      {/* ── Tagihan Pajak ── */}
      {(data.pkb_pokok || data.total_tagihan) && (
        <div className="py-4 border-t border-gray-100 space-y-0">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Rincian Pajak
          </p>
          {[
            { label: "PKB Pokok", value: data.pkb_pokok },
            { label: "PKB Denda", value: data.pkb_denda, red: true },
            { label: "SWDKLLJ Pokok", value: data.swdkllj_pokok },
            { label: "SWDKLLJ Denda", value: data.swdkllj_denda, red: true },
          ].filter(r => r.value !== undefined && r.value !== null).map((r, i) => (
            <div key={i} className="info-row">
              <span className="info-label">{r.label}</span>
              <span className={`info-value ${r.red && (r.value ?? 0) > 0 ? "text-red-600" : ""}`}>
                {formatRupiah(r.value)}
              </span>
            </div>
          ))}

          {/* Total */}
          {data.total_tagihan !== undefined && (
            <div className={`mt-3 rounded-xl p-4 flex justify-between items-center ${
              totalBayar === 0
                ? "bg-green-50 border border-green-200"
                : "bg-red-50 border border-red-200"
            }`}>
              <div>
                <p className="text-sm font-semibold text-gray-700">
                  {totalBayar === 0 ? "✅ Pajak Lunas" : "⚠️ Total Tagihan"}
                </p>
                {hasDenda && totalBayar > 0 && (
                  <p className="text-xs text-red-500 mt-0.5">Termasuk denda keterlambatan</p>
                )}
              </div>
              <p className={`text-lg font-bold ${
                totalBayar === 0 ? "text-green-700" : "text-red-700"
              }`}>
                {formatRupiah(totalBayar)}
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Footer ── */}
      <div className="pt-3 border-t border-gray-100 flex items-center justify-between">
        <p className="text-xs text-gray-400">
          {result.cached ? "📦 Dari cache" : "🔴 Live"} · Sumber: {region.name}
        </p>
        {data.sumber && (
          <a
            href={data.sumber}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 hover:underline flex items-center gap-1"
          >
            Lihat sumber <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
    </div>
  );
}
