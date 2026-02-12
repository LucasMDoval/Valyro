/* frontend/src/app/api/valyro.ts */

export type ScrapeOptions = {
  min_price?: number;
  max_price?: number;
  filter_mode?: 'soft' | 'strict' | 'off';
  exclude_bad_text?: boolean;
};

// frontend/.env (opcional):
// VITE_API_BASE_URL=http://127.0.0.1:5000/api/v1
const BASE_URL: string = (import.meta as any).env?.VITE_API_BASE_URL ?? '/api/v1';

function apiOrigin(): string {
  try {
    if (BASE_URL.startsWith('http://') || BASE_URL.startsWith('https://')) {
      return new URL(BASE_URL).origin;
    }
  } catch {}
  return window.location.origin;
}

function toAbsoluteUrl(maybeRelative: string): string {
  if (!maybeRelative) return maybeRelative;
  if (maybeRelative.startsWith('http://') || maybeRelative.startsWith('https://')) return maybeRelative;
  return `${apiOrigin()}${maybeRelative.startsWith('/') ? '' : '/'}${maybeRelative}`;
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;

  const res = await fetch(url, init);
  const text = await res.text().catch(() => '');

  if (!res.ok) {
    try {
      const j = JSON.parse(text);
      const msg = j?.error?.message ?? j?.message ?? text ?? `HTTP ${res.status}`;
      throw new Error(msg);
    } catch {
      throw new Error(text || `HTTP ${res.status}`);
    }
  }

  if (!text) return {} as T;
  return JSON.parse(text) as T;
}

/** ====== TIPOS ====== */

export type KeywordStatsResponse = {
  keyword: string;
  scraped_at: string;
  stats: {
    n?: number;
    media?: number;
    mediana: number;
    q1: number;
    q2: number;
    q3: number;
    minimo?: number;
    maximo?: number;
  };
  price_ranges: {
    normal: { from: number; to: number };
    fast?: { from: number; to: number };
    slow?: { from: number; to: number };
    quick?: { from: number; to: number };
  };
  sell_speed?: any;
};

export type KeywordRunsResponse = {
  keyword: string;
  runs: Array<{
    scraped_at: string;
    n: number;
    media: number;
    minimo: number;
    maximo: number;
  }>;
};

export type KeywordSeriesResponse = {
  keyword: string;
  series: Array<{
    scraped_at: string;
    media: number;
    mediana: number;
  }>;
};

export type CompareResponse = {
  comparison: Array<any>;
  plot_url?: string | null;
  selected: string[];
};

/** ====== CORE ====== */

export async function listKeywords(): Promise<string[]> {
  const r: any = await apiJson<any>('/keywords');
  if (Array.isArray(r)) return r;
  if (r && Array.isArray(r.keywords)) return r.keywords;
  return [];
}

export async function getKeywordStats(keyword: string): Promise<KeywordStatsResponse> {
  const kw = encodeURIComponent(keyword);
  return apiJson<KeywordStatsResponse>(`/keyword/${kw}/stats`);
}

export async function scrapeKeyword(keyword: string, opts?: ScrapeOptions): Promise<any> {
  const kw = encodeURIComponent(keyword);
  return apiJson(`/keyword/${kw}/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts ?? {}),
  });
}

/** ====== SERIE (para % variación y gráficas) ====== */

export async function getKeywordSeries(keyword: string): Promise<KeywordSeriesResponse> {
  const kw = encodeURIComponent(keyword);
  return apiJson<KeywordSeriesResponse>(`/keyword/${kw}/series`);
}

/** ====== RUNS / BORRADO ====== */

export async function listKeywordRuns(keyword: string): Promise<KeywordRunsResponse> {
  const kw = encodeURIComponent(keyword);
  return apiJson<KeywordRunsResponse>(`/keyword/${kw}/runs`);
}

export async function deleteRun(keyword: string, scraped_at: string): Promise<{ deleted: number }> {
  const kw = encodeURIComponent(keyword);
  const sa = encodeURIComponent(scraped_at);
  return apiJson(`/keyword/${kw}/runs/${sa}`, { method: 'DELETE' });
}

export async function deleteAllKeyword(keyword: string): Promise<{ deleted: number }> {
  const kw = encodeURIComponent(keyword);
  return apiJson(`/keyword/${kw}`, { method: 'DELETE' });
}

/** ====== REPORT / PLOTS ====== */

export async function generateReport(keyword: string): Promise<{ url: string }> {
  const kw = encodeURIComponent(keyword);
  const r = await apiJson<{ url: string }>(`/keyword/${kw}/report`, { method: 'POST' });
  return { url: toAbsoluteUrl(r.url) };
}

export async function generateMeanMedianPlot(keyword: string): Promise<{ url: string }> {
  const kw = encodeURIComponent(keyword);
  const r = await apiJson<{ url: string }>(`/keyword/${kw}/plot/mean-median`, { method: 'POST' });
  return { url: toAbsoluteUrl(r.url) };
}

/** ====== COMPARE ====== */

export async function compareKeywords(keywords: string[]): Promise<CompareResponse> {
  const r = await apiJson<CompareResponse>(`/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keywords }),
  });

  if (r.plot_url) r.plot_url = toAbsoluteUrl(r.plot_url);
  return r;
}

/** ====== DAILY ====== */

export async function getDailyConfig() {
  return apiJson(`/daily`);
}

export async function saveDailyConfig(rows: any[]) {
  return apiJson(`/daily`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows }),
  });
}

export async function dailyRunNow() {
  return apiJson(`/daily/run_now`, { method: 'POST' });
}

export async function installDailyTask(time: string) {
  return apiJson(`/daily/task/install`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ time }),
  });
}

export async function removeDailyTask() {
  return apiJson(`/daily/task/remove`, { method: 'POST' });
}

/** ====== SETUP / LEGAL ====== */

export async function getSetupChecks() {
  return apiJson(`/setup/checks`);
}

export async function runSetupAction(action: string) {
  return apiJson(`/setup/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  });
}

export async function getLegalHtml() {
  return apiJson(`/legal`);
}
