/* frontend/src/app/components/ProductDetailPanel.tsx */

import { useEffect, useMemo, useState } from 'react';
import { X, RefreshCw, FileText, LineChart, Trash2 } from 'lucide-react';
import {
  deleteAllKeyword,
  deleteRun,
  generateMeanMedianPlot,
  generateReport,
  getKeywordSeries,
  getKeywordStats,
  listKeywordRuns,
  type KeywordRunsResponse,
  type KeywordSeriesResponse,
  type KeywordStatsResponse,
} from '../api/valyro';

import { LineChart as RLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

type Product = {
  keyword: string;
  medianPrice: number;
  priceChange: number;
  icon?: JSX.Element;
};

export function ProductDetailPanel(props: { product: Product; onClose: () => void }) {
  const kw = props.product.keyword;

  const [stats, setStats] = useState<KeywordStatsResponse | null>(null);
  const [runs, setRuns] = useState<KeywordRunsResponse | null>(null);
  const [series, setSeries] = useState<KeywordSeriesResponse | null>(null);

  const [plotUrl, setPlotUrl] = useState<string | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function formatDate(scrapedAt: string): string {
    const dt = new Date(scrapedAt);
    if (!isNaN(dt.getTime())) {
      const dd = String(dt.getDate()).padStart(2, '0');
      const mm = String(dt.getMonth() + 1).padStart(2, '0');
      const yy = dt.getFullYear();
      return `${dd}/${mm}/${yy}`;
    }
    return scrapedAt;
  }

  async function reloadAll() {
    setLoading(true);
    setErr(null);
    try {
      const [s, r] = await Promise.all([getKeywordStats(kw), listKeywordRuns(kw)]);
      setStats(s);
      setRuns(r);

      // serie temporal es opcional: si el endpoint no existe, no bloquea el panel
      try {
        const ser = await getKeywordSeries(kw);
        setSeries(ser);
      } catch {
        setSeries(null);
      }
    } catch (e: any) {
      setErr(e?.message ?? String(e));
      setStats(null);
      setRuns(null);
      setSeries(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setPlotUrl(null);
    setReportUrl(null);
    reloadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kw]);

  const seriesChartData = useMemo(() => {
    const pts = series?.series ?? [];
    return pts
      .slice()
      .sort((a, b) => new Date(a.scraped_at).getTime() - new Date(b.scraped_at).getTime())
      .map((p) => ({
        date: formatDate(p.scraped_at),
        mediana: p.mediana,
        media: p.media,
      }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series]);

  const median = stats?.stats?.mediana ?? props.product.medianPrice;
  const q1 = stats?.stats?.q1;
  const q3 = stats?.stats?.q3;
  const n = stats?.stats?.n;

  async function onDeleteRun(scraped_at: string) {
    const ok = window.confirm(`¿Borrar esta run?\n${scraped_at}`);
    if (!ok) return;

    setBusy(true);
    setErr(null);
    try {
      await deleteRun(kw, scraped_at);
      await reloadAll();
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteAll() {
    const ok = window.confirm(`¿Borrar TODO el histórico de "${kw}"?\nNo se puede deshacer.`);
    if (!ok) return;

    setBusy(true);
    setErr(null);
    try {
      await deleteAllKeyword(kw);
      props.onClose();
      // el dashboard se refresca cuando vuelvas a abrir / o recargas manualmente
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onReport() {
    setBusy(true);
    setErr(null);
    try {
      const r = await generateReport(kw);
      setReportUrl(r.url);
      window.open(r.url, '_blank', 'noopener,noreferrer');
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onMeanMedianPlot() {
    setBusy(true);
    setErr(null);
    try {
      const r = await generateMeanMedianPlot(kw);
      setPlotUrl(r.url);
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50">
      {/* backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={props.onClose} />

      {/* panel */}
      <div className="absolute right-0 top-0 h-full w-full sm:w-[520px] bg-[#0b1220] border-l border-[#1f2a3a] shadow-2xl flex flex-col">
        {/* header */}
        <div className="p-5 border-b border-[#1f2a3a] flex items-start justify-between gap-3">
          <div>
            <div className="text-white text-lg font-semibold leading-tight">{kw}</div>
            <div className="text-[#94a3b8] text-sm">
              Último análisis: {stats?.scraped_at ? formatDate(stats.scraped_at) : '—'}
            </div>
          </div>

          <button
            className="p-2 rounded-lg hover:bg-white/5 text-[#94a3b8] hover:text-white"
            onClick={props.onClose}
            aria-label="Cerrar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* acciones */}
          <div className="flex flex-wrap gap-2">
            <button
              className="px-3 py-2 rounded-lg bg-[#1e293b] text-white border border-[#2d3548] hover:bg-[#22304a] disabled:opacity-60"
              onClick={() => reloadAll()}
              disabled={loading || busy}
              title="Recargar"
            >
              <span className="inline-flex items-center gap-2 text-sm">
                <RefreshCw className="w-4 h-4" /> Recargar
              </span>
            </button>

            <button
              className="px-3 py-2 rounded-lg bg-white text-[#0f172a] font-semibold hover:bg-white/90 disabled:opacity-60"
              onClick={onReport}
              disabled={loading || busy}
              title="Generar informe HTML"
            >
              <span className="inline-flex items-center gap-2 text-sm">
                <FileText className="w-4 h-4" /> Informe
              </span>
            </button>

            <button
              className="px-3 py-2 rounded-lg bg-[#13C1AC] text-[#0f172a] font-semibold hover:opacity-90 disabled:opacity-60"
              onClick={onMeanMedianPlot}
              disabled={loading || busy}
              title="Generar gráfico mean/median"
            >
              <span className="inline-flex items-center gap-2 text-sm">
                <LineChart className="w-4 h-4" /> Mean/Median
              </span>
            </button>

            <button
              className="ml-auto px-3 py-2 rounded-lg bg-red-500/15 text-red-200 border border-red-500/30 hover:bg-red-500/20 disabled:opacity-60"
              onClick={onDeleteAll}
              disabled={loading || busy}
              title="Borrar todo el histórico de este keyword"
            >
              <span className="inline-flex items-center gap-2 text-sm">
                <Trash2 className="w-4 h-4" /> Borrar todo
              </span>
            </button>
          </div>

          {err && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-200 rounded-xl p-4 text-sm whitespace-pre-wrap">
              {err}
            </div>
          )}

          {/* stats */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#0f1a2b] border border-[#1f2a3a] rounded-xl p-4">
              <div className="text-[#94a3b8] text-xs">Mediana</div>
              <div className="text-white text-xl font-semibold mt-1">{Number(median).toFixed(2)}€</div>
            </div>

            <div className="bg-[#0f1a2b] border border-[#1f2a3a] rounded-xl p-4">
              <div className="text-[#94a3b8] text-xs">Rango normal (Q1–Q3)</div>
              <div className="text-white text-base font-semibold mt-1">
                {q1 != null && q3 != null ? `${Math.round(q1)}€ – ${Math.round(q3)}€` : '—'}
              </div>
            </div>

            <div className="bg-[#0f1a2b] border border-[#1f2a3a] rounded-xl p-4 col-span-2">
              <div className="text-[#94a3b8] text-xs">Items (última run)</div>
              <div className="text-white text-base font-semibold mt-1">{n != null ? n : '—'}</div>
            </div>
          </div>

          {/* gráfico serie (si existe) */}
          {seriesChartData.length > 1 && (
            <div className="bg-[#0f1a2b] border border-[#1f2a3a] rounded-xl p-4">
              <div className="text-white font-semibold">Evolución (mediana)</div>
              <div className="text-[#94a3b8] text-sm mt-1">Por run (histórico)</div>

              <div className="mt-3" style={{ width: '100%', height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <RLineChart data={seriesChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2a3a" />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} stroke="#1f2a3a" />
                    <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} stroke="#1f2a3a" tickFormatter={(v) => `${v}€`} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0b1220',
                        border: '1px solid #1f2a3a',
                        borderRadius: '10px',
                        color: '#fff',
                        fontSize: '12px',
                      }}
                      formatter={(value: number) => [`${Number(value).toFixed(2)}€`, 'Mediana']}
                    />
                    <Line type="monotone" dataKey="mediana" stroke="#13C1AC" strokeWidth={2} dot={false} />
                  </RLineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* plot mean/median */}
          {plotUrl && (
            <div className="bg-[#0f1a2b] border border-[#1f2a3a] rounded-xl p-4">
              <div className="text-white font-semibold">Gráfico mean/median</div>
              <div className="text-[#94a3b8] text-sm mt-1 break-all">{plotUrl}</div>
              <img src={plotUrl} className="mt-3 w-full rounded-lg border border-[#1f2a3a]" />
            </div>
          )}

          {/* runs */}
          <div className="bg-[#0f1a2b] border border-[#1f2a3a] rounded-xl p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-white font-semibold">Histórico de runs</div>
                <div className="text-[#94a3b8] text-sm mt-1">
                  {runs?.runs?.length != null ? `${runs.runs.length} runs` : '—'}
                </div>
              </div>
            </div>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#1f2a3a]">
                    <th className="text-left py-2 px-2 text-xs text-[#94a3b8]">Fecha</th>
                    <th className="text-right py-2 px-2 text-xs text-[#94a3b8]">N</th>
                    <th className="text-right py-2 px-2 text-xs text-[#94a3b8]">Media</th>
                    <th className="text-right py-2 px-2 text-xs text-[#94a3b8]">Min</th>
                    <th className="text-right py-2 px-2 text-xs text-[#94a3b8]">Max</th>
                    <th className="py-2 px-2" />
                  </tr>
                </thead>
                <tbody>
                  {(runs?.runs ?? []).map((r) => (
                    <tr key={r.scraped_at} className="border-b border-[#1f2a3a]/60">
                      <td className="py-2 px-2 text-sm text-white">{formatDate(r.scraped_at)}</td>
                      <td className="py-2 px-2 text-sm text-right text-[#94a3b8]">{r.n}</td>
                      <td className="py-2 px-2 text-sm text-right text-[#94a3b8]">{Number(r.media).toFixed(2)}€</td>
                      <td className="py-2 px-2 text-sm text-right text-[#94a3b8]">{Number(r.minimo).toFixed(0)}€</td>
                      <td className="py-2 px-2 text-sm text-right text-[#94a3b8]">{Number(r.maximo).toFixed(0)}€</td>
                      <td className="py-2 px-2 text-right">
                        <button
                          className="text-xs text-red-200 hover:text-red-100 disabled:opacity-60"
                          onClick={() => onDeleteRun(r.scraped_at)}
                          disabled={busy || loading}
                        >
                          borrar
                        </button>
                      </td>
                    </tr>
                  ))}

                  {!loading && (runs?.runs?.length ?? 0) === 0 && (
                    <tr>
                      <td className="py-3 px-2 text-sm text-[#94a3b8]" colSpan={6}>
                        No hay runs todavía.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {loading && <div className="mt-3 text-sm text-[#94a3b8]">Cargando…</div>}
          </div>

          {/* informe url */}
          {reportUrl && (
            <div className="bg-[#0f1a2b] border border-[#1f2a3a] rounded-xl p-4">
              <div className="text-white font-semibold">Informe</div>
              <a
                href={reportUrl}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-[#13C1AC] break-all hover:underline mt-2 block"
              >
                {reportUrl}
              </a>
            </div>
          )}
        </div>

        {/* footer */}
        <div className="p-4 border-t border-[#1f2a3a] text-xs text-[#94a3b8]">
          {busy ? 'Aplicando cambios…' : ' '}
        </div>
      </div>
    </div>
  );
}
