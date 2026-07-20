"use client";

import { useState, useCallback, useEffect } from "react";
import { Search, SlidersHorizontal, X, Database } from "lucide-react";
import { searchVehicles, getStats, REGIONS, JENIS_LIST } from "@/lib/api";
import type { SearchResult, DbStats } from "@/types/vehicle";
import VehicleList from "@/components/VehicleList";
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function SearchPage() {
  const [q,        setQ]        = useState("");
  const [region,   setRegion]   = useState("");
  const [jenis,    setJenis]    = useState("");
  const [tahunMin, setTahunMin] = useState("");
  const [tahunMax, setTahunMax] = useState("");
  const [showFilter, setShowFilter] = useState(false);

  const [result,  setResult]  = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const [stats,   setStats]   = useState<DbStats | null>(null);
  const [offset,  setOffset]  = useState(0);
  const LIMIT = 30;

  // Load stats on mount
  useEffect(() => {
    getStats().then(setStats).catch(() => null);
  }, []);

  const doSearch = useCallback(async (newOffset = 0) => {
    if (!q.trim() && !region && !jenis && !tahunMin && !tahunMax) {
      setError("Isi minimal satu parameter pencarian");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await searchVehicles({
        q: q.trim() || undefined,
        region: region || undefined,
        jenis: jenis || undefined,
        tahun_min: tahunMin ? Number(tahunMin) : undefined,
        tahun_max: tahunMax ? Number(tahunMax) : undefined,
        limit: LIMIT,
        offset: newOffset,
      });
      setResult(res);
      setOffset(newOffset);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan");
    } finally {
      setLoading(false);
    }
  }, [q, region, jenis, tahunMin, tahunMax]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doSearch(0);
  };

  const clearFilters = () => {
    setRegion(""); setJenis(""); setTahunMin(""); setTahunMax("");
  };

  const activeFilters = [region, jenis, tahunMin, tahunMax].filter(Boolean).length;
  const totalPages = result ? Math.ceil(result.total / LIMIT) : 0;
  const currentPage = Math.floor(offset / LIMIT) + 1;

  return (
    <div className="min-h-screen bg-gradient-to-b from-red-600 via-red-600 to-gray-50 dark:to-gray-950">

      {/* Header */}
      <header className="px-4 pt-10 pb-6">
        <div className="max-w-lg mx-auto flex items-center gap-3">
          <Link href="/" className="text-white/70 hover:text-white transition-colors text-sm">
            ← Cek Plat
          </Link>
          <span className="text-white/40">|</span>
          <h1 className="text-white font-bold text-lg flex-1">Cari Kendaraan</h1>
          <ThemeToggle />
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 pb-16">

        {/* Stats bar */}
        {stats && (
          <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-xl px-4 py-2 mb-4">
            <Database className="w-4 h-4 text-white/70" />
            <p className="text-white/80 text-xs">
              <strong className="text-white">{stats.total_vehicles.toLocaleString("id-ID")}</strong> kendaraan dalam database
              {stats.by_region.length > 0 && (
                <span className="text-white/60"> · {stats.by_region.length} daerah</span>
              )}
            </p>
          </div>
        )}

        {/* Search card */}
        <div className="card shadow-xl shadow-red-900/20 border-0">
          <form onSubmit={handleSubmit} className="space-y-3">

            {/* Keyword input */}
            <div className="relative">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                className="input-field pl-10"
                placeholder="Cari merk / model, e.g. XSR 155, CB400, GSF400..."
                value={q}
                onChange={e => setQ(e.target.value)}
              />
              {q && (
                <button type="button" onClick={() => setQ("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Filter toggle */}
            <button
              type="button"
              onClick={() => setShowFilter(!showFilter)}
              className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              Filter lanjutan
              {activeFilters > 0 && (
                <span className="badge badge-red ml-1">{activeFilters}</span>
              )}
            </button>

            {showFilter && (
              <div className="space-y-2.5 bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 border border-gray-100 dark:border-gray-700">
                {/* Region */}
                <div>
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1 block">Daerah</label>
                  <select
                    className="input-field text-sm py-2"
                    value={region}
                    onChange={e => setRegion(e.target.value)}
                  >
                    <option value="">Semua daerah</option>
                    {REGIONS.map(r => (
                      <option key={r.code} value={r.code}>{r.name}</option>
                    ))}
                  </select>
                </div>

                {/* Jenis */}
                <div>
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1 block">Jenis Kendaraan</label>
                  <select
                    className="input-field text-sm py-2"
                    value={jenis}
                    onChange={e => setJenis(e.target.value)}
                  >
                    <option value="">Semua jenis</option>
                    {JENIS_LIST.map(j => (
                      <option key={j} value={j}>{j}</option>
                    ))}
                  </select>
                </div>

                {/* Tahun range */}
                <div>
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1 block">Tahun</label>
                  <div className="flex gap-2">
                    <input
                      type="number"
                      className="input-field text-sm py-2"
                      placeholder="Dari (e.g. 2000)"
                      value={tahunMin}
                      onChange={e => setTahunMin(e.target.value)}
                      min={1970} max={2025}
                    />
                    <input
                      type="number"
                      className="input-field text-sm py-2"
                      placeholder="Sampai (e.g. 2024)"
                      value={tahunMax}
                      onChange={e => setTahunMax(e.target.value)}
                      min={1970} max={2025}
                    />
                  </div>
                </div>

                {activeFilters > 0 && (
                  <button type="button" onClick={clearFilters}
                    className="text-xs text-red-600 hover:text-red-700 font-medium">
                    Reset filter
                  </button>
                )}
              </div>
            )}

            {error && (
              <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full flex items-center justify-center gap-2">
              {loading ? "Mencari..." : <><Search className="w-4 h-4" /> Cari Kendaraan</>}
            </button>
          </form>
        </div>

        {/* Quick examples */}
        {!result && !loading && (
          <div className="mt-4">
            <p className="text-xs text-gray-400 mb-2 text-center">Contoh pencarian</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {[
                { label: "XSR 155 di Bali", q: "XSR 155", region: "bali" },
                { label: "CB400 di Jakarta", q: "CB400", region: "jakarta" },
                { label: "GSF400 di Jawa", q: "GSF400", region: "" },
                { label: "Semua motor Kawasaki", q: "Kawasaki", region: "" },
                { label: "Motor tahun 2000-an", q: "", region: "bali" },
              ].map((ex, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setQ(ex.q);
                    setRegion(ex.region);
                    if (ex.region) setShowFilter(true);
                    setTimeout(() => doSearch(0), 100);
                  }}
                  className="text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-full px-3 py-1.5 hover:border-red-300 dark:hover:border-red-600 hover:text-red-600 dark:hover:text-red-400 transition-colors shadow-sm"
                >
                  {ex.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Results */}
        <VehicleList
          results={result?.results ?? []}
          total={result?.total ?? 0}
          loading={loading}
        />

        {/* Pagination */}
        {result && result.total > LIMIT && (
          <div className="flex items-center justify-between mt-4">
            <button
              onClick={() => doSearch(offset - LIMIT)}
              disabled={offset === 0 || loading}
              className="text-sm text-gray-600 disabled:opacity-40 hover:text-red-600"
            >
              ← Sebelumnya
            </button>
            <span className="text-xs text-gray-500">
              Hal {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => doSearch(offset + LIMIT)}
              disabled={offset + LIMIT >= result.total || loading}
              className="text-sm text-gray-600 disabled:opacity-40 hover:text-red-600"
            >
              Berikutnya →
            </button>
          </div>
        )}

        {/* Info note */}
        {result && result.total === 0 && !loading && (
          <div className="mt-4 bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
            <p className="text-sm font-medium text-blue-800">Database masih kosong untuk pencarian ini</p>
            <p className="text-xs text-blue-600 mt-1">
              Data terkumpul otomatis saat pengguna cek plat kendaraan, atau admin menjalankan crawler.
              Makin banyak yang pakai → makin banyak data!
            </p>
          </div>
        )}

        <footer className="mt-10 text-center">
          <p className="text-xs text-gray-400">
            Data dari hasil query pengguna & crawler Samsat · Diperbarui real-time
          </p>
        </footer>
      </main>
    </div>
  );
}
