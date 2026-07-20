"use client";

import { useState, useRef, useCallback } from "react";
import { Search, ChevronDown, MapPin, RefreshCw } from "lucide-react";
import { checkVehicle, detectRegion } from "@/lib/api";
import type { CheckResponse, RegionInfo } from "@/types/vehicle";
import ResultCard from "@/components/ResultCard";
import LoadingSkeleton from "@/components/LoadingSkeleton";

// Supported regions badge list
const SUPPORTED = [
  { prefix: "B", name: "Jakarta" },
  { prefix: "D/F/Z/E/T", name: "Jawa Barat" },
  { prefix: "A", name: "Banten" },
  { prefix: "H/G/K/R/AA/AD", name: "Jawa Tengah" },
  { prefix: "AB", name: "DIY" },
  { prefix: "L/W/N/P/AG", name: "Jawa Timur" },
  { prefix: "DK", name: "Bali" },
];

export default function HomePage() {
  const [plate, setPlate] = useState("");
  const [nik, setNik] = useState("");
  const [showNik, setShowNik] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CheckResponse | null>(null);
  const [detectedRegion, setDetectedRegion] = useState<RegionInfo | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Format plate input: auto uppercase & spaces
  const handlePlateChange = useCallback(async (raw: string) => {
    const val = raw.toUpperCase().replace(/[^A-Z0-9 ]/g, "");
    setPlate(val);
    setResult(null);
    setError(null);

    // Auto-detect region after 2+ chars
    const clean = val.replace(/ /g, "");
    if (clean.length >= 1) {
      const info = await detectRegion(clean).catch(() => null);
      setDetectedRegion(info);
      if (info?.needs_nik) setShowNik(true);
    } else {
      setDetectedRegion(null);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanPlate = plate.trim();
    if (!cleanPlate || cleanPlate.length < 4) {
      setError("Masukkan nomor polisi yang valid (min. 4 karakter)");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await checkVehicle(cleanPlate, nik || undefined);
      setResult(res);

      // If NIK required, prompt user
      if (res.status === "nik_required" && !showNik) {
        setShowNik(true);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Terjadi kesalahan. Coba lagi.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-red-600 via-red-600 to-gray-50">

      {/* ── Hero Header ── */}
      <header className="px-4 pt-12 pb-8 text-center">
        <div className="inline-flex items-center gap-2 bg-white/15 backdrop-blur-sm rounded-full px-4 py-1.5 mb-4">
          <span className="text-white/80 text-xs font-medium">🇮🇩 Seluruh Indonesia</span>
        </div>
        <h1 className="text-3xl font-extrabold text-white leading-tight tracking-tight">
          Cek Ranmor
          <span className="block text-red-200">Indonesia</span>
        </h1>
        <p className="text-red-100 text-sm mt-2 max-w-xs mx-auto leading-relaxed">
          Cek pajak kendaraan, data STNK & info ranmor dari seluruh Samsat Indonesia
        </p>
      </header>

      {/* ── Search Card ── */}
      <main className="max-w-lg mx-auto px-4 pb-16">
        <div className="card shadow-xl shadow-red-900/20 border-0">

          {/* Search Form */}
          <form onSubmit={handleSubmit} className="space-y-3">

            {/* Plate Input */}
            <div className="relative">
              <div className="absolute inset-y-0 left-3.5 flex items-center pointer-events-none">
                <span className="text-gray-400 font-mono text-xs font-bold">🚗</span>
              </div>
              <input
                ref={inputRef}
                type="text"
                inputMode="text"
                autoCapitalize="characters"
                autoCorrect="off"
                autoComplete="off"
                spellCheck={false}
                className="input-field pl-10 font-mono uppercase text-base tracking-widest"
                placeholder="B 1234 XYZ"
                value={plate}
                onChange={e => handlePlateChange(e.target.value)}
                maxLength={12}
              />
              {detectedRegion && (
                <div className="absolute inset-y-0 right-3 flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-gray-400" />
                  <span className="text-xs text-gray-500 font-medium">{detectedRegion.name}</span>
                </div>
              )}
            </div>

            {/* NIK Toggle */}
            <button
              type="button"
              onClick={() => setShowNik(!showNik)}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
            >
              <ChevronDown
                className={`w-3.5 h-3.5 transition-transform ${showNik ? "rotate-180" : ""}`}
              />
              {showNik ? "Sembunyikan NIK" : "Tambah NIK (untuk beberapa daerah)"}
              {detectedRegion?.needs_nik && (
                <span className="badge badge-yellow ml-1">Diperlukan</span>
              )}
            </button>

            {showNik && (
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                className="input-field font-mono"
                placeholder="NIK 16 digit (opsional)"
                value={nik}
                onChange={e => setNik(e.target.value.replace(/\D/g, "").slice(0, 16))}
                maxLength={16}
              />
            )}

            {/* Error */}
            {error && (
              <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                ⚠️ {error}
              </p>
            )}

            {/* Submit */}
            <button type="submit" disabled={loading} className="btn-primary w-full flex items-center justify-center gap-2">
              {loading
                ? <><RefreshCw className="w-4 h-4 animate-spin" /> Mencari...</>
                : <><Search className="w-4 h-4" /> Cek Kendaraan</>
              }
            </button>
          </form>
        </div>

        {/* ── Result ── */}
        {loading && <LoadingSkeleton />}
        {result && !loading && <ResultCard result={result} />}

        {/* ── Supported Regions ── */}
        {!result && !loading && (
          <div className="mt-6">
            <p className="text-xs text-gray-500 font-medium text-center mb-3">
              Daerah yang didukung
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUPPORTED.map(r => (
                <div
                  key={r.prefix}
                  className="bg-white border border-gray-200 rounded-lg px-3 py-1.5 flex items-center gap-1.5 shadow-sm"
                >
                  <span className="font-mono text-xs text-red-600 font-bold">{r.prefix}</span>
                  <span className="text-xs text-gray-600">{r.name}</span>
                </div>
              ))}
              <div className="bg-gray-100 border border-gray-200 rounded-lg px-3 py-1.5">
                <span className="text-xs text-gray-400">+ Segera hadir...</span>
              </div>
            </div>
          </div>
        )}

        {/* ── Footer ── */}
        <footer className="mt-10 text-center space-y-1">
          <p className="text-xs text-gray-400">
            Data bersumber langsung dari Samsat masing-masing daerah
          </p>
          <p className="text-xs text-gray-400">
            © 2025 ranmor.fortunamj.com · Tidak berafiliasi dengan instansi pemerintah
          </p>
        </footer>
      </main>
    </div>
  );
}
