"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { RefreshCw, Activity, Database, ArrowLeft } from "lucide-react";
import { getCrawlerStatus, type CrawlerStatus } from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";

const REGION_LABEL: Record<string, string> = {
  jabar:  "Jawa Barat",
  jateng: "Jawa Tengah",
  diy:    "DI Yogyakarta",
  bali:   "Bali",
};

const REGION_PREFIX: Record<string, string> = {
  jabar: "D", jateng: "H", diy: "AB", bali: "DK",
};

function fmt(n: number) {
  return n?.toLocaleString("id-ID") ?? "0";
}

export default function StatusPage() {
  const [data,    setData]    = useState<CrawlerStatus | null>(null);
  const [updated, setUpdated] = useState("");
  const [error,   setError]   = useState("");
  const [loading, setLoading] = useState(true);
  const [spin,    setSpin]    = useState(false);

  const refresh = useCallback(async (manual = false) => {
    if (manual) setSpin(true);
    try {
      const d = await getCrawlerStatus();
      setData(d);
      setError("");
      setUpdated(new Date().toLocaleTimeString("id-ID"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Gagal terhubung ke backend");
    } finally {
      setLoading(false);
      if (manual) setTimeout(() => setSpin(false), 600);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(() => refresh(), 10_000);
    return () => clearInterval(t);
  }, [refresh]);

  const crawlers = data?.crawlers ?? {};
  const db       = data?.db;
  const regions  = Object.keys(crawlers);

  const totalTried = regions.reduce((s, r) => s + (crawlers[r]?.tried ?? 0), 0);
  const totalFound = regions.reduce((s, r) => s + (crawlers[r]?.found ?? 0), 0);
  const anyRunning = regions.some((r) => crawlers[r]?.running);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors">
      {/* Header */}
      <header className="bg-red-600 text-white shadow sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-1 text-white/80 hover:text-white text-sm transition-colors">
              <ArrowLeft className="w-4 h-4" /> Cek Ranmor
            </Link>
            <span className="text-white/40">|</span>
            <h1 className="font-bold text-lg flex items-center gap-1.5">
              <Activity className="w-4 h-4" /> Status Crawler
            </h1>
          </div>
          <div className="flex items-center gap-2">
            {updated && (
              <span className="text-white/60 text-xs hidden sm:block">
                Update: {updated}
              </span>
            )}
            <button
              onClick={() => refresh(true)}
              className="p-2 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
              title="Refresh sekarang"
            >
              <RefreshCw className={`w-4 h-4 ${spin ? "animate-spin" : ""}`} />
            </button>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-5">

        {/* Loading */}
        {loading && (
          <div className="text-center py-16 text-gray-400 dark:text-gray-600">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3" />
            Menghubungi backend...
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-xl p-4">
            <p className="text-red-700 dark:text-red-400 font-semibold">Gagal memuat status</p>
            <p className="text-red-600 dark:text-red-500 text-sm mt-1">{error}</p>
            <p className="text-red-500 dark:text-red-600 text-xs mt-2">
              Backend: <code className="bg-red-100 dark:bg-red-900/50 px-1 rounded">https://api-ranmor.fortunamj.com</code>
            </p>
          </div>
        )}

        {/* Summary bar */}
        {data && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Total DB",      val: fmt(db?.total_vehicles ?? 0), sub: "kendaraan tersimpan",   color: "text-red-600 dark:text-red-400" },
              { label: "Sesi ini — Dicoba", val: fmt(totalTried),         sub: "plat sudah diceka",     color: "text-blue-600 dark:text-blue-400" },
              { label: "Sesi ini — Ditemukan", val: fmt(totalFound),      sub: "kendaraan baru",        color: "text-green-600 dark:text-green-400" },
              { label: "Status",        val: anyRunning ? "JALAN" : "IDLE", sub: `${regions.filter(r => crawlers[r]?.running).length}/${regions.length} region aktif`, color: anyRunning ? "text-green-600 dark:text-green-400" : "text-gray-500 dark:text-gray-400" },
            ].map((s) => (
              <div key={s.label} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
                <p className="text-xs text-gray-400 dark:text-gray-500">{s.label}</p>
                <p className={`text-2xl font-bold mt-0.5 ${s.color}`}>{s.val}</p>
                <p className="text-xs text-gray-400 dark:text-gray-600 mt-0.5">{s.sub}</p>
              </div>
            ))}
          </div>
        )}

        {/* Resume info */}
        {data && (
          <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/50 rounded-xl p-3.5 text-sm text-blue-700 dark:text-blue-400 flex gap-2.5 items-start">
            <span className="text-lg leading-none mt-0.5">💡</span>
            <div>
              <strong>Resume otomatis jika PC mati:</strong> Setiap 200 plat, posisi disimpan ke database.
              Saat backend nyala kembali, crawler lanjut dari plat terakhir — tidak mengulang dari awal.
            </div>
          </div>
        )}

        {/* Per-region crawler cards */}
        {data && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
              <h2 className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <Activity className="w-4 h-4 text-red-500" /> Crawler per Region
              </h2>
              <span className="text-xs text-gray-400 dark:text-gray-600">Auto-refresh 10 detik</span>
            </div>

            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {regions.length === 0 ? (
                <p className="text-gray-400 dark:text-gray-600 text-center py-10">Tidak ada crawler aktif.</p>
              ) : regions.map((region) => {
                const d = crawlers[region];
                const hitRate = d.tried > 0 ? ((d.found / d.tried) * 100).toFixed(2) : "0.00";

                return (
                  <div key={region} className="p-4 sm:p-5 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                    {/* Top row */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2.5">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${d.running ? "bg-green-500 animate-pulse" : "bg-gray-400"}`} />
                        <div>
                          <span className="font-semibold text-gray-900 dark:text-gray-100">
                            {REGION_LABEL[region] ?? region}
                          </span>
                          <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">
                            ({REGION_PREFIX[region] ?? region})
                          </span>
                          <span className={`ml-2 text-xs px-2 py-0.5 rounded-full font-medium ${
                            d.running
                              ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                              : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
                          }`}>
                            {d.running ? "JALAN" : d.status.toUpperCase()}
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-green-600 dark:text-green-400 font-bold text-sm">{fmt(d.found)} ditemukan</p>
                        <p className="text-gray-400 dark:text-gray-600 text-xs">{hitRate}% hit rate</p>
                      </div>
                    </div>

                    {/* Suffix info */}
                    {d.current_suffix && (
                      <p className="text-xs text-gray-500 dark:text-gray-500 mb-3 ml-4">
                        Suffix sekarang: <code className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-gray-700 dark:text-gray-300 font-mono">{d.current_suffix}</code>
                        {d.kab && <> — <span className="text-gray-400">{d.kab}</span></>}
                      </p>
                    )}

                    {/* Stats grid */}
                    <div className="grid grid-cols-3 gap-3 ml-4">
                      <div>
                        <p className="text-xs text-gray-400 dark:text-gray-500">Dicoba sesi ini</p>
                        <p className="font-semibold text-gray-800 dark:text-gray-200 text-sm">{fmt(d.tried)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400 dark:text-gray-500">Plat terakhir</p>
                        <code className="text-xs font-mono bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-2 py-0.5 rounded">{d.last || "—"}</code>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400 dark:text-gray-500">Kosong berturut</p>
                        <p className="font-semibold text-gray-800 dark:text-gray-200 text-sm">{fmt(d.consecutive_empty)}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* DB breakdown */}
        {db && db.by_region.length > 0 && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
            <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center gap-2">
              <Database className="w-4 h-4 text-red-500" />
              <h2 className="font-semibold text-gray-800 dark:text-gray-200">Database</h2>
            </div>
            <div className="p-5 space-y-4">
              {db.by_region.map((r) => (
                <div key={r.region}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 dark:text-gray-300">{r.name || r.region}</span>
                    <span className="font-semibold text-gray-800 dark:text-gray-200">{fmt(r.count)}</span>
                  </div>
                  <div className="w-full bg-gray-100 dark:bg-gray-800 rounded-full h-1.5">
                    <div
                      className="bg-red-500 h-1.5 rounded-full transition-all duration-700"
                      style={{ width: `${db.total_vehicles > 0 ? Math.max((r.count / db.total_vehicles) * 100, 2) : 0}%` }}
                    />
                  </div>
                </div>
              ))}

              {db.top_merks.length > 0 && (
                <div className="pt-3 border-t border-gray-100 dark:border-gray-800">
                  <p className="text-xs text-gray-400 dark:text-gray-500 mb-2">Top Merek:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {db.top_merks.slice(0, 12).map((m) => (
                      <span key={m.merk} className="bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-xs px-2.5 py-1 rounded-full">
                        {m.merk} <span className="font-semibold text-gray-800 dark:text-gray-300">{fmt(m.count)}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* How it works */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm p-5">
          <h2 className="font-semibold text-gray-800 dark:text-gray-200 mb-3">Cara Kerja</h2>
          <div className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
            <p><strong className="text-gray-800 dark:text-gray-200">Smart suffix order:</strong> Suffix per kab/kota diprioritas (contoh: Kota Bandung A–R, Cimahi S–T), lalu brute-force sisa kombinasi.</p>
            <p><strong className="text-gray-800 dark:text-gray-200">Skip threshold:</strong> Default 9999 — scan semua angka di setiap suffix. Bisa diturunkan via API admin untuk lebih cepat.</p>
            <p><strong className="text-gray-800 dark:text-gray-200">Mode:</strong> <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">all</code> — scan semua jenis kendaraan (1–9999).</p>
            <p><strong className="text-gray-800 dark:text-gray-200">Delay:</strong> 1.2 detik/request supaya tidak overload server Samsat.</p>
          </div>
        </div>
      </main>
    </div>
  );
}
