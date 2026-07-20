"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { getCrawlerStatus, getStats, type CrawlerStatus } from "@/lib/api";
import type { DbStats } from "@/types/vehicle";

const REGION_LABEL: Record<string, string> = {
  jabar:  "Jawa Barat (D)",
  jateng: "Jawa Tengah (H)",
  diy:    "DI Yogyakarta (AB)",
  bali:   "Bali (DK)",
};

function fmt(n: number) {
  return n.toLocaleString("id-ID");
}

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
      <div
        className="bg-red-500 h-2 rounded-full transition-all duration-700"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export default function StatusPage() {
  const [crawler, setCrawler]     = useState<CrawlerStatus | null>(null);
  const [stats,   setStats]       = useState<DbStats | null>(null);
  const [updated, setUpdated]     = useState<string>("");
  const [error,   setError]       = useState<string>("");
  const [loading, setLoading]     = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([getCrawlerStatus(), getStats()]);
      setCrawler(c);
      setStats(s);
      setError("");
      setUpdated(new Date().toLocaleTimeString("id-ID"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Gagal terhubung ke backend");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 10_000); // auto-refresh every 10s
    return () => clearInterval(timer);
  }, [refresh]);

  const activeRegions = crawler ? Object.keys(crawler.active) : [];
  // Total crawl rate estimate: all regions combined
  const totalTried = crawler
    ? activeRegions.reduce((s, r) => s + (crawler.active[r]?.tried ?? 0), 0)
    : 0;
  const totalFound = crawler
    ? activeRegions.reduce((s, r) => s + (crawler.active[r]?.found ?? 0), 0)
    : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-red-600 text-white py-4 px-6 shadow">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div>
            <Link href="/" className="text-white/80 text-sm hover:text-white">
              ← Cek Ranmor
            </Link>
            <h1 className="text-xl font-bold mt-0.5">Status Crawler</h1>
          </div>
          <div className="text-right text-sm text-white/70">
            {updated && <p>Update: {updated}</p>}
            <p className="text-xs">Auto-refresh 10 detik</p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        {loading && (
          <div className="text-center py-12 text-gray-500">Menghubungi backend...</div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700">
            <strong>Error:</strong> {error}
            <p className="text-sm mt-1 text-red-600">
              Pastikan backend berjalan di{" "}
              <code className="bg-red-100 px-1 rounded">http://localhost:8000</code>
            </p>
          </div>
        )}

        {/* DB Stats */}
        {stats && (
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-4 text-lg">
              Database Kendaraan
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-red-50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-red-600">{fmt(stats.total_vehicles)}</p>
                <p className="text-xs text-gray-500 mt-1">Total Kendaraan</p>
              </div>
              {stats.by_region.slice(0, 3).map((r) => (
                <div key={r.region} className="bg-gray-50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-gray-700">{fmt(r.count)}</p>
                  <p className="text-xs text-gray-500 mt-1">{r.name || r.region}</p>
                </div>
              ))}
            </div>

            {stats.top_merks.length > 0 && (
              <div className="mt-4">
                <p className="text-sm text-gray-500 mb-2">Top Merek Kendaraan:</p>
                <div className="flex flex-wrap gap-2">
                  {stats.top_merks.slice(0, 10).map((m) => (
                    <span
                      key={m.merk}
                      className="bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded-full"
                    >
                      {m.merk} ({fmt(m.count)})
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Crawler summary */}
        {crawler && (
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-800 text-lg">Crawler Background</h2>
              <div className="flex gap-3 text-sm">
                <span className="text-gray-500">Sesi ini: <strong className="text-gray-800">{fmt(totalTried)}</strong> dicoba</span>
                <span className="text-green-600 font-semibold">{fmt(totalFound)} ditemukan</span>
              </div>
            </div>

            {/* Resume notice */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-sm text-blue-700">
              <strong>Resume otomatis:</strong> Jika PC mati atau backend restart, crawler akan
              lanjut dari plat terakhir yang sudah dicoba — tidak mengulang dari awal.
            </div>

            <div className="space-y-4">
              {activeRegions.map((region) => {
                const d = crawler.active[region];
                const isRunning = d.running;
                // Motor range ~4000 plates per suffix, rough total estimate per suffix
                const hitRate = d.tried > 0 ? ((d.found / d.tried) * 100).toFixed(2) : "0.00";

                return (
                  <div
                    key={region}
                    className="border border-gray-100 rounded-lg p-4 bg-gray-50"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-block w-2 h-2 rounded-full ${
                              isRunning ? "bg-green-500 animate-pulse" : "bg-gray-400"
                            }`}
                          />
                          <span className="font-semibold text-gray-800">
                            {REGION_LABEL[region] || region}
                          </span>
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                              isRunning
                                ? "bg-green-100 text-green-700"
                                : "bg-gray-200 text-gray-600"
                            }`}
                          >
                            {isRunning ? "JALAN" : d.status.toUpperCase()}
                          </span>
                        </div>
                        {d.kab && (
                          <p className="text-xs text-gray-500 mt-0.5 ml-4">
                            Suffix: <strong>{d.current_suffix}</strong> — {d.kab}
                          </p>
                        )}
                      </div>
                      <div className="text-right text-sm">
                        <p className="text-green-600 font-bold">{fmt(d.found)} ditemukan</p>
                        <p className="text-gray-400 text-xs">{hitRate}% hit rate</p>
                      </div>
                    </div>

                    <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
                      <div>
                        <p className="text-gray-400 text-xs">Dicoba sesi ini</p>
                        <p className="font-semibold text-gray-700">{fmt(d.tried)}</p>
                      </div>
                      <div>
                        <p className="text-gray-400 text-xs">Plat terakhir</p>
                        <code className="text-xs bg-gray-200 px-1.5 py-0.5 rounded text-gray-700">
                          {d.last || "-"}
                        </code>
                      </div>
                      <div>
                        <p className="text-gray-400 text-xs">Kosong berturut</p>
                        <p className="font-semibold text-gray-700">{fmt(d.consecutive_empty)}</p>
                      </div>
                    </div>

                    <ProgressBar value={d.suffix_found} max={Math.max(d.suffix_found, 10)} />
                    <p className="text-xs text-gray-400 mt-1">
                      {fmt(d.suffix_found)} ditemukan di suffix {d.current_suffix || "—"}
                    </p>
                  </div>
                );
              })}

              {activeRegions.length === 0 && !loading && (
                <p className="text-gray-500 text-center py-6">
                  Belum ada crawler yang berjalan.
                </p>
              )}
            </div>
          </div>
        )}

        {/* How it works */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="font-semibold text-gray-800 text-lg mb-3">Cara Kerja</h2>
          <div className="space-y-2 text-sm text-gray-600">
            <p>
              <strong>Smart suffix order:</strong> Crawler mengutamakan suffix yang diketahui
              per kab/kota terlebih dahulu (mis. Kota Bandung → A-R, Cimahi → S,T, dst),
              lalu brute-force sisa kombinasi.
            </p>
            <p>
              <strong>Resume otomatis:</strong> Setiap 200 plat dicoba, posisi disimpan ke
              database. Jika backend restart, crawler lanjut dari checkpoint terakhir.
            </p>
            <p>
              <strong>Mode saat ini:</strong> <code className="bg-gray-100 px-1 rounded">all</code> —
              scan semua jenis kendaraan (mobil, motor, bus, barang) nomor 1–9999.
            </p>
            <p>
              <strong>Delay:</strong> 1.2 detik antar request agar tidak overload server Samsat.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
