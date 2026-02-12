import { useEffect, useState } from 'react';
import { compareKeywords, getKeywordSeries, listKeywords } from '../api/valyro';
import { CompareEvolutionChart } from '../components/CompareEvolutionChart';


export function CompareSection() {
  const [keywords, setKeywords] = useState<string[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [seriesData, setSeriesData] = useState<any[] | null>(null);


  useEffect(() => {
    listKeywords()
      .then(setKeywords)
      .catch((e) => setErr(e?.message ?? String(e)));
  }, []);

  function toggle(kw: string) {
    setSelected((prev) => ({ ...prev, [kw]: !prev[kw] }));
  }

  async function onCompare() {
    const kws = Object.keys(selected).filter((k) => selected[k]);
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const r = await compareKeywords(kws);
setResult(r);

// ---- cargar series para gráfico ----
const seriesList = await Promise.all(kws.map((k) => getKeywordSeries(k)));

const byTs = new Map<string, any>(); // key = scraped_at
for (const s of seriesList) {
  const kw = s.keyword;
  for (const p of (s.series ?? [])) {
    const ts = p.scraped_at;
    if (!byTs.has(ts)) {
      const d = new Date(ts);
      const dd = String(d.getDate()).padStart(2, "0");
      const mm = String(d.getMonth() + 1).padStart(2, "0");
      const yy = d.getFullYear();
      byTs.set(ts, { date: `${dd}/${mm}/${yy}` });
    }
    byTs.get(ts)[kw] = p.mediana; // comparamos mediana
  }
}

const merged = Array.from(byTs.entries())
  .sort((a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime())
  .map(([, row]) => row);

setSeriesData(merged);

    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
        <h3 className="text-lg font-semibold text-white">Comparar keywords</h3>
        <p className="text-sm text-[#94a3b8] mt-1">Selecciona mínimo 2.</p>

        <div className="mt-4 grid grid-cols-2 gap-2 max-h-[300px] overflow-auto pr-2">
          {keywords.map((kw) => (
            <label key={kw} className="flex items-center gap-2 text-sm text-[#94a3b8]">
              <input type="checkbox" checked={!!selected[kw]} onChange={() => toggle(kw)} />
              {kw}
            </label>
          ))}
        </div>

        <div className="mt-4">
          <button
            className="px-4 py-2 rounded-lg bg-[#13C1AC] text-[#0F172A] font-semibold hover:opacity-90"
            onClick={onCompare}
            disabled={busy}
          >
            Comparar
          </button>
        </div>

        {err && <div className="mt-4 text-sm text-red-200 whitespace-pre-wrap">{err}</div>}
      </div>

      {result?.comparison && (
        <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
          <h4 className="text-white font-semibold mb-3">Resultado</h4>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#2d3548]">
                  <th className="text-left py-2 px-3 text-sm text-white">Keyword</th>
                  <th className="text-left py-2 px-3 text-sm text-white">Última run</th>
                  <th className="text-right py-2 px-3 text-sm text-white">Mediana</th>
                  <th className="text-left py-2 px-3 text-sm text-white">Rango normal</th>
                  <th className="text-left py-2 px-3 text-sm text-white">Rápido</th>
                </tr>
              </thead>
              <tbody>
                {result.comparison.map((r: any) => (
                  <tr key={r.keyword} className="border-b border-[#2d3548]/50">
                    <td className="py-2 px-3 text-sm text-white">{r.keyword}</td>
                    <td className="py-2 px-3 text-sm text-[#94a3b8]">{r.scraped_at}</td>
                    <td className="py-2 px-3 text-sm text-right text-[#13C1AC]">{Number(r.mediana).toFixed(2)}€</td>
                    <td className="py-2 px-3 text-sm text-[#94a3b8]">{r.rango_normal}</td>
                    <td className="py-2 px-3 text-sm text-[#94a3b8]">{r.rango_rapido}</td>
                  </tr>
                ))}
                {seriesData && (
  <CompareEvolutionChart
    title="Comparar evolución de precios"
    data={seriesData}
    keywords={Object.keys(selected).filter((k) => selected[k])}
  />
)}

              </tbody>
            </table>
          </div>

          {result.plot_url && (
            <div className="mt-4">
              <img src={result.plot_url} className="max-w-full rounded-lg border border-[#2d3548]" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
