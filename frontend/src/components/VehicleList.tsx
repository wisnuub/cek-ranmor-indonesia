"use client";

import { useState } from "react";
import type { VehicleData } from "@/types/vehicle";
import { formatRupiah } from "@/lib/api";
import {
  Car, Calendar, Palette, MapPin, AlertCircle,
  ChevronDown, ChevronUp, Clock, ExternalLink,
} from "lucide-react";

interface Props {
  results: VehicleData[];
  total: number;
  loading?: boolean;
}

export default function VehicleList({ results, total, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-3 mt-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card animate-pulse">
            <div className="flex gap-3">
              <div className="skeleton w-12 h-12 rounded-xl shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="skeleton h-4 w-40 rounded" />
                <div className="skeleton h-3 w-24 rounded" />
                <div className="skeleton h-3 w-32 rounded" />
              </div>
              <div className="skeleton h-6 w-20 rounded-full" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="card mt-4 text-center py-10">
        <AlertCircle className="w-10 h-10 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500 dark:text-gray-400 font-medium">Tidak ada data ditemukan</p>
        <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
          Database kami masih terus bertumbuh. Coba cari kata kunci lain.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3 mt-4">
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Menampilkan <strong>{results.length}</strong> dari{" "}
        <strong>{total.toLocaleString("id-ID")}</strong> kendaraan ditemukan
      </p>

      {results.map((v, i) => (
        <VehicleCard key={v.plate ?? i} vehicle={v} />
      ))}
    </div>
  );
}

function VehicleCard({ vehicle: v }: { vehicle: VehicleData }) {
  const [expanded, setExpanded] = useState(false);

  const name    = [v.merk, v.model, v.tipe].filter(Boolean).join(" ") || "Kendaraan";
  const isMotor = v.jenis?.toLowerCase().includes("motor");
  const hasTax  = v.total_tagihan !== undefined && v.total_tagihan !== null;
  const lunas   = v.status_pajak === "Lunas" || v.total_tagihan === 0;

  // Ada detail yang bisa ditampilkan?
  const hasDetail = !!(
    v.jatuh_tempo_pajak || v.jatuh_tempo_stnk ||
    v.nama_pemilik      || v.total_tagihan !== undefined ||
    v.pkb_pokok         || v.no_rangka
  );

  return (
    <div className="card overflow-hidden p-0">
      {/* ── Row utama (selalu tampil) ── */}
      <button
        className="w-full text-left p-4 hover:bg-gray-50 dark:hover:bg-gray-800/60
                   transition-colors duration-150 focus:outline-none
                   focus:ring-2 focus:ring-inset focus:ring-red-400"
        onClick={() => hasDetail && setExpanded(e => !e)}
        aria-expanded={expanded}
      >
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div className={`p-2.5 rounded-xl shrink-0 ${
            isMotor
              ? "bg-orange-50 dark:bg-orange-900/30"
              : "bg-blue-50 dark:bg-blue-900/30"
          }`}>
            <Car className={`w-5 h-5 ${
              isMotor ? "text-orange-500" : "text-blue-500"
            }`} />
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <p className="font-bold text-gray-900 dark:text-gray-100 text-sm leading-tight truncate">
              {name}
            </p>
            <p className="font-mono text-xs text-gray-500 dark:text-gray-400 tracking-widest mt-0.5">
              {v.plate}
            </p>

            <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1.5">
              {v.tahun && (
                <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                  <Calendar className="w-3 h-3" /> {v.tahun}
                </span>
              )}
              {v.warna && (
                <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                  <Palette className="w-3 h-3" /> {v.warna}
                </span>
              )}
              {v.region_name && (
                <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                  <MapPin className="w-3 h-3" /> {v.region_name}
                </span>
              )}
            </div>
          </div>

          {/* Kanan — status + chevron */}
          <div className="flex flex-col items-end gap-1 shrink-0">
            {hasTax && (
              <span className={`badge text-xs ${lunas ? "badge-green" : "badge-red"}`}>
                {lunas ? "Lunas" : "Belum Lunas"}
              </span>
            )}
            {v.total_tagihan !== undefined && v.total_tagihan > 0 && (
              <p className="text-xs text-red-600 dark:text-red-400 font-semibold">
                {formatRupiah(v.total_tagihan)}
              </p>
            )}
            {hasDetail && (
              <span className="text-gray-400 dark:text-gray-500 mt-1">
                {expanded
                  ? <ChevronUp className="w-4 h-4" />
                  : <ChevronDown className="w-4 h-4" />}
              </span>
            )}
          </div>
        </div>
      </button>

      {/* ── Detail panel (expand) ── */}
      {expanded && hasDetail && (
        <div className="border-t border-gray-100 dark:border-gray-800 px-4 pb-4 pt-3 space-y-0 bg-gray-50/50 dark:bg-gray-800/30">

          {/* Masa berlaku */}
          {(v.jatuh_tempo_pajak || v.jatuh_tempo_stnk) && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1.5">
                Masa Berlaku
              </p>
              {v.jatuh_tempo_pajak && (
                <div className="info-row">
                  <span className="info-label flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-gray-400" /> Pajak JT
                  </span>
                  <span className="info-value font-mono">{v.jatuh_tempo_pajak}</span>
                </div>
              )}
              {v.jatuh_tempo_stnk && (
                <div className="info-row">
                  <span className="info-label flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-gray-400" /> STNK s/d
                  </span>
                  <span className="info-value font-mono">{v.jatuh_tempo_stnk}</span>
                </div>
              )}
            </div>
          )}

          {/* Rincian pajak */}
          {(v.pkb_pokok || v.total_tagihan !== undefined) && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1.5">
                Rincian Pajak
              </p>
              {v.pkb_pokok !== undefined && (
                <div className="info-row">
                  <span className="info-label">PKB Pokok</span>
                  <span className="info-value">{formatRupiah(v.pkb_pokok)}</span>
                </div>
              )}
              {!!v.pkb_denda && (
                <div className="info-row">
                  <span className="info-label">Denda PKB</span>
                  <span className="info-value text-red-500 dark:text-red-400">{formatRupiah(v.pkb_denda)}</span>
                </div>
              )}
              {v.swdkllj_pokok !== undefined && (
                <div className="info-row">
                  <span className="info-label">SWDKLLJ</span>
                  <span className="info-value">{formatRupiah(v.swdkllj_pokok)}</span>
                </div>
              )}
              {!!v.swdkllj_denda && (
                <div className="info-row">
                  <span className="info-label">Denda SWDKLLJ</span>
                  <span className="info-value text-red-500 dark:text-red-400">{formatRupiah(v.swdkllj_denda)}</span>
                </div>
              )}
              {v.total_tagihan !== undefined && (
                <div className={`mt-2 rounded-xl px-4 py-3 flex justify-between items-center ${
                  lunas
                    ? "bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800"
                    : "bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800"
                }`}>
                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                    {lunas ? "✅ Pajak Lunas" : "⚠️ Total Tagihan"}
                  </p>
                  <p className={`text-base font-bold ${
                    lunas ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400"
                  }`}>
                    {formatRupiah(v.total_tagihan)}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Kepemilikan */}
          {v.nama_pemilik && (
            <div className="info-row">
              <span className="info-label">Pemilik</span>
              <span className="info-value">{v.nama_pemilik}</span>
            </div>
          )}
          {v.no_rangka && (
            <div className="info-row">
              <span className="info-label">No. Rangka</span>
              <span className="info-value font-mono text-xs">{v.no_rangka}</span>
            </div>
          )}

          {/* Cek live */}
          <div className="pt-3 mt-1">
            <a
              href={`/?plate=${encodeURIComponent(v.plate ?? "")}`}
              className="flex items-center justify-center gap-2 w-full rounded-xl
                         bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800
                         text-red-600 dark:text-red-400 text-xs font-semibold py-2.5
                         hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Cek Pajak Live untuk {v.plate}
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
