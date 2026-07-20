"use client";

import type { VehicleData } from "@/types/vehicle";
import { formatRupiah } from "@/lib/api";
import { Car, Calendar, Palette, MapPin, AlertCircle } from "lucide-react";

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
        <p className="text-gray-500 font-medium">Tidak ada data ditemukan</p>
        <p className="text-sm text-gray-400 mt-1">
          Database kami masih terus bertumbuh. Coba cari kata kunci lain.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3 mt-4">
      <p className="text-xs text-gray-500">
        Menampilkan <strong>{results.length}</strong> dari <strong>{total.toLocaleString("id-ID")}</strong> kendaraan ditemukan
      </p>

      {results.map((v, i) => (
        <VehicleCard key={v.plate ?? i} vehicle={v} />
      ))}
    </div>
  );
}

function VehicleCard({ vehicle: v }: { vehicle: VehicleData }) {
  const name = [v.merk, v.model, v.tipe].filter(Boolean).join(" ") || "Kendaraan";
  const hasTax = v.total_tagihan !== undefined && v.total_tagihan !== null;
  const lunas  = v.status_pajak === "Lunas" || v.total_tagihan === 0;

  return (
    <div className="card hover:shadow-md transition-shadow duration-150">
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className={`p-2.5 rounded-xl shrink-0 ${
          v.jenis?.toLowerCase().includes("motor")
            ? "bg-orange-50"
            : "bg-blue-50"
        }`}>
          <Car className={`w-5 h-5 ${
            v.jenis?.toLowerCase().includes("motor")
              ? "text-orange-500"
              : "text-blue-500"
          }`} />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <p className="font-bold text-gray-900 text-sm leading-tight truncate">{name}</p>
          <p className="font-mono text-xs text-gray-500 tracking-widest mt-0.5">{v.plate}</p>

          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1.5">
            {v.tahun && (
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <Calendar className="w-3 h-3" /> {v.tahun}
              </span>
            )}
            {v.warna && (
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <Palette className="w-3 h-3" /> {v.warna}
              </span>
            )}
            {v.region_name && (
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <MapPin className="w-3 h-3" /> {v.region_name}
              </span>
            )}
          </div>
        </div>

        {/* Right — pajak */}
        <div className="text-right shrink-0">
          {hasTax && (
            <span className={`badge text-xs ${lunas ? "badge-green" : "badge-red"}`}>
              {lunas ? "Lunas" : "Belum Lunas"}
            </span>
          )}
          {v.total_tagihan !== undefined && v.total_tagihan > 0 && (
            <p className="text-xs text-red-600 font-semibold mt-1">
              {formatRupiah(v.total_tagihan)}
            </p>
          )}
          {v.jatuh_tempo_pajak && (
            <p className="text-xs text-gray-400 mt-0.5">JT: {v.jatuh_tempo_pajak}</p>
          )}
        </div>
      </div>
    </div>
  );
}
