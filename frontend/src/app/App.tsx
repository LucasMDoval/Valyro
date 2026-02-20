import { useEffect, useMemo, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { SearchBar } from './components/SearchBar';
import { RecentSearchCard } from './components/RecentSearchCard';
import { PriceChart } from './components/PriceChart';
import { ProductComparisonTable } from './components/ProductComparisonTable';
import { ProductDetailPanel } from './components/ProductDetailPanel';
import { Footer } from './components/Footer';
import { iconForSearchQuery } from './utils/searchIcon';

import { getKeywordSeries, getKeywordStats, listKeywords, scrapeKeyword } from './api/valyro';

import { DailySection } from './sections/DailySection';
import { CompareSection } from './sections/CompareSection';
import { DiagnosticSection } from './sections/DiagnosticSection';
import { LegalSection } from './sections/LegalSection';

type Recent = {
  keyword: string;
  medianPrice: number;
  priceChange: number;
  icon: JSX.Element;
};

type ComparisonRow = {
  keyword: string;
  lastAnalysis: string;
  median: number;
  q1: number;
  q2: number;
  q3: number;
  normalRange: string;
};

export default function App() {
  const [activeSection, setActiveSection] = useState('analyze');
  const [selectedProduct, setSelectedProduct] = useState<Recent | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [tableRows, setTableRows] = useState<ComparisonRow[]>([]);

  // % variación por keyword (cards)
  const [priceChangeByKw, setPriceChangeByKw] = useState<Record<string, number>>({});

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

  async function loadPriceChangesForCards(keywords: string[]) {
    // solo calculamos para las 4 tarjetas (barato y rápido)
    const results = await Promise.allSettled(
      keywords.map(async (kw) => {
        const ser = await getKeywordSeries(kw);
        const sorted = (ser.series ?? [])
          .slice()
          .sort((a, b) => new Date(a.scraped_at).getTime() - new Date(b.scraped_at).getTime());

        if (sorted.length < 2) return [kw, 0] as const;

        const prev = Number(sorted[sorted.length - 2].mediana);
        const last = Number(sorted[sorted.length - 1].mediana);

        if (!isFinite(prev) || prev <= 0 || !isFinite(last)) return [kw, 0] as const;

        const pct = ((last - prev) / prev) * 100;
        return [kw, pct] as const;
      })
    );

    const patch: Record<string, number> = {};
    for (const r of results) {
      if (r.status === 'fulfilled') {
        patch[r.value[0]] = r.value[1];
      }
    }

    setPriceChangeByKw((prev) => ({ ...prev, ...patch }));
  }

  async function loadDashboard() {
    setLoading(true);
    setError(null);
    try {
      const kws = await listKeywords();
      if (kws.length === 0) {
        setTableRows([]);
        setPriceChangeByKw({});
        return;
      }

      const stats = await Promise.all(kws.slice(0, 25).map((kw) => getKeywordStats(kw)));

      const mapped: ComparisonRow[] = stats.map((s) => ({
        keyword: s.keyword,
        lastAnalysis: formatDate(s.scraped_at),
        median: s.stats.mediana,
        q1: s.stats.q1,
        q2: s.stats.q2,
        q3: s.stats.q3,
        normalRange: `${Math.round(s.price_ranges.normal.from)}€ - ${Math.round(s.price_ranges.normal.to)}€`,
      }));

      setTableRows(mapped);

      // calcula % para las tarjetas (top 4)
      const top4 = mapped.slice(0, 4).map((r) => r.keyword);
      await loadPriceChangesForCards(top4);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  const recentSearches: Recent[] = useMemo(() => {
    return tableRows.slice(0, 4).map((r) => ({
      keyword: r.keyword,
      medianPrice: r.median,
      priceChange: priceChangeByKw[r.keyword] ?? 0,
      icon: iconForSearchQuery(r.keyword),
    }));
  }, [tableRows, priceChangeByKw]);

  const priceEvolution = useMemo(() => {
    // Placeholder: hasta que uses /series para pintar histórico en el chart principal
    const median = tableRows[0]?.median ?? 0;
    const labels = ['-7', '-6', '-5', '-4', '-3', '-2', '-1', 'hoy'];
    return labels.map((d) => ({ date: d, price: median }));
  }, [tableRows]);

  const handleTableProductClick = (keyword: string, medianPrice: number) => {
    const product: Recent =
      recentSearches.find((p) => p.keyword === keyword) || {
        keyword,
        medianPrice,
        priceChange: priceChangeByKw[keyword] ?? 0,
        icon: iconForSearchQuery(keyword),
      };
    setSelectedProduct(product);
  };

  return (
    <div className="flex h-screen bg-[#0f1419]">
      <Sidebar activeSection={activeSection} onSectionChange={setActiveSection} />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />

        <main className="flex-1 overflow-y-auto bg-[#0f172a]">
          <div className="p-8">
            {activeSection === 'analyze' && (
              <div className="space-y-8">
                <SearchBar
                  onAnalyze={async (kw, opts) => {
                    await scrapeKeyword(kw, opts);
                    await loadDashboard();
                  }}
                />

                {error && (
                  <div className="bg-red-500/10 border border-red-500/30 text-red-200 rounded-xl p-4 whitespace-pre-wrap">
                    {error}
                  </div>
                )}

                {loading && <div className="text-[#94a3b8] text-sm">Cargando dashboard…</div>}

                {!loading && !error && (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                      {recentSearches.map((p) => (
                        <RecentSearchCard
                          key={p.keyword}
                          keyword={p.keyword}
                          medianPrice={p.medianPrice}
                          priceChange={p.priceChange}
                          icon={p.icon}
                          onClick={() => setSelectedProduct(p)}
                        />
                      ))}
                    </div>

                    <PriceChart
                      data={priceEvolution}
                      productName={selectedProduct?.keyword ?? recentSearches[0]?.keyword ?? '—'}
                    />

                    <ProductComparisonTable products={tableRows} onProductClick={handleTableProductClick} />
                  </>
                )}
              </div>
            )}

            {activeSection === 'auto-analysis' && <DailySection />}
            {activeSection === 'compare' && <CompareSection />}
            {activeSection === 'diagnostic' && <DiagnosticSection />}
            {activeSection === 'legal' && <LegalSection />}

            {activeSection === 'about' && (
              <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548] text-[#94a3b8]">
                Sobre: (migrar texto de web/templates/about.html cuando quieras)
              </div>
            )}

            {activeSection === 'upgrade' && (
              <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548] text-[#94a3b8]">
                Upgrade PRO: (migrar texto de web/templates/upgrade.html cuando quieras)
              </div>
            )}
          </div>
        </main>

        <Footer />
      </div>

      {selectedProduct && (
        <ProductDetailPanel product={selectedProduct} onClose={() => setSelectedProduct(null)} />
      )}
    </div>
  );
}
