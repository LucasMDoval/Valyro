import { useEffect, useState } from 'react';
import { getLegalHtml } from '../api/valyro';

export function LegalSection() {
  const [html, setHtml] = useState<string>('');
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getLegalHtml()
      .then((r) => setHtml(r.html ?? ''))
      .catch((e) => setErr(e?.message ?? String(e)));
  }, []);

  return (
    <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
      <h3 className="text-lg font-semibold text-white">Legal</h3>
      {err && <div className="mt-4 text-sm text-red-200">{err}</div>}
      <div className="mt-4 text-sm text-[#94a3b8]" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}
