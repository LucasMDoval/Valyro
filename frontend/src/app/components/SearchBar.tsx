import { Search } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

type ScrapeOpts = {
  min_price?: number;
  max_price?: number;
  filter_mode?: 'soft' | 'strict' | 'off';
  exclude_bad_text?: boolean;
};

export function SearchBar(props: { onAnalyze: (keyword: string, opts: ScrapeOpts) => Promise<void> }) {
  const [searchTerm, setSearchTerm] = useState('');

  // filtros
  const [minPrice, setMinPrice] = useState<string>('');
  const [maxPrice, setMaxPrice] = useState<string>('');
  const [filterMode, setFilterMode] = useState<'soft' | 'strict' | 'off'>('soft');
  const [excludeBadText, setExcludeBadText] = useState<boolean>(true);

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // progreso fake
  const [progress, setProgress] = useState<number>(0);
  const progressTimerRef = useRef<number | null>(null);

  function startFakeProgress() {
    setProgress(1);
    if (progressTimerRef.current) window.clearInterval(progressTimerRef.current);

    progressTimerRef.current = window.setInterval(() => {
      setProgress((p) => {
        if (p < 70) return +(p + 1).toFixed(1);
        if (p < 88) return +(p + 0.4).toFixed(1);
        if (p < 92) return +(p + 0.15).toFixed(2);
        return p;
      });
    }, 500);
  }

  function finishFakeProgress() {
    if (progressTimerRef.current) {
      window.clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
    setProgress(100);
    window.setTimeout(() => setProgress(0), 700);
  }

  useEffect(() => {
    return () => {
      if (progressTimerRef.current) window.clearInterval(progressTimerRef.current);
    };
  }, []);

  const toNumOrUndef = (v: string): number | undefined => {
    const s = (v ?? '').trim();
    if (!s) return undefined;
    const n = Number(s);
    return Number.isFinite(n) ? n : undefined;
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const kw = searchTerm.trim();
    if (!kw) return;

    const opts: ScrapeOpts = {
      min_price: toNumOrUndef(minPrice),
      max_price: toNumOrUndef(maxPrice),
      filter_mode: filterMode,
      exclude_bad_text: excludeBadText,
    };

    setBusy(true);
    setErr(null);
    startFakeProgress();

    try {
      await props.onAnalyze(kw, opts);
      setSearchTerm('');
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      finishFakeProgress();
      setBusy(false);
    }
  };

  return (
    <div className="bg-gradient-to-r from-[#13C1AC] to-[#0E8072] rounded-xl p-8 shadow-lg">
      <div className="max-w-3xl mx-auto">
        <h3 className="text-white text-xl font-semibold mb-2">Analiza ahora un producto</h3>
        <p className="text-white/80 text-sm mb-6">
          Introduce el nombre del producto para obtener estadísticas detalladas del mercado
        </p>

        <form onSubmit={handleSearch} className="flex flex-col gap-3">
          {/* fila 1 */}
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#64748B]" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Ej: iPhone 14 Pro, PS5, MacBook Air..."
                className="w-full pl-12 pr-4 py-3.5 rounded-lg border-0 focus:ring-2 focus:ring-white/50 focus:outline-none text-[#0F172A] placeholder:text-[#64748B] bg-white"
              />
            </div>

            <button
              type="submit"
              disabled={busy}
              className="px-8 py-3.5 bg-white text-[#13C1AC] font-semibold rounded-lg hover:bg-white/90 transition-colors shadow-sm disabled:opacity-60"
            >
              {busy ? 'Analizando…' : 'Analizar'}
            </button>
          </div>

          {/* fila 2: filtros */}
          <div className="flex flex-wrap gap-3 items-center">
            <div className="flex items-center gap-2">
              <span className="text-white/80 text-sm">Min €</span>
              <input
                type="number"
                value={minPrice}
                onChange={(e) => setMinPrice(e.target.value)}
                className="w-28 px-3 py-2 rounded-lg bg-white text-[#0F172A]"
                placeholder="—"
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-white/80 text-sm">Max €</span>
              <input
                type="number"
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
                className="w-28 px-3 py-2 rounded-lg bg-white text-[#0F172A]"
                placeholder="—"
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-white/80 text-sm">Filtro</span>
              <select
                value={filterMode}
                onChange={(e) => setFilterMode(e.target.value as any)}
                className="px-3 py-2 rounded-lg bg-white text-[#0F172A]"
              >
                <option value="soft">soft</option>
                <option value="strict">strict</option>
                <option value="off">off</option>
              </select>
            </div>

            <label className="flex items-center gap-2 text-white/80 text-sm">
              <input
                type="checkbox"
                checked={excludeBadText}
                onChange={(e) => setExcludeBadText(e.target.checked)}
              />
              excluir “basura”
            </label>
          </div>
        </form>

        {/* ✅ AQUÍ VA EL 1.4: justo después del </form> */}
        {progress > 0 && (
          <div className="mt-3">
            <div className="h-2 w-full bg-white/20 rounded-full overflow-hidden">
              <div
                className="h-full bg-white transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="mt-1 text-xs text-white/80">
              Analizando… {Math.floor(progress)}%
            </div>
          </div>
        )}

        {err && <div className="mt-4 text-red-100 text-sm whitespace-pre-wrap">{err}</div>}
      </div>
    </div>
  );
}
