import { useEffect, useState } from 'react';
import { getSetupChecks, runSetupAction } from '../api/valyro';

export function DiagnosticSection() {
  const [checks, setChecks] = useState<any[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  async function reload() {
    const r = await getSetupChecks();
    setChecks(r.checks ?? []);
  }

  useEffect(() => {
    reload().catch((e) => setMsg(e?.message ?? String(e)));
  }, []);

  async function act(action: string) {
    setMsg(null);
    try {
      const r = await runSetupAction(action);
      setMsg(r.message ?? (r.ok ? 'OK' : 'Falló'));
      await reload();
    } catch (e: any) {
      setMsg(e?.message ?? String(e));
    }
  }

  return (
    <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
      <h3 className="text-lg font-semibold text-white">Diagnóstico / Setup</h3>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#2d3548]">
              <th className="text-left py-2 px-3 text-sm text-white">Check</th>
              <th className="text-left py-2 px-3 text-sm text-white">Estado</th>
              <th className="text-left py-2 px-3 text-sm text-white">Detalle</th>
            </tr>
          </thead>
          <tbody>
            {checks.map((c) => (
              <tr key={c.key} className="border-b border-[#2d3548]/50">
                <td className="py-2 px-3 text-sm text-white">{c.label}</td>
                <td className="py-2 px-3 text-sm">
                  <span className={c.ok ? 'text-green-300' : 'text-red-300'}>{c.ok ? 'OK' : 'FAIL'}</span>
                </td>
                <td className="py-2 px-3 text-sm text-[#94a3b8]">{c.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button className="px-4 py-2 rounded-lg bg-[#252b3d] text-white hover:bg-[#2d3548]" onClick={() => act('open_logs')}>
          Abrir logs
        </button>
        <button className="px-4 py-2 rounded-lg bg-[#252b3d] text-white hover:bg-[#2d3548]" onClick={() => act('open_data')}>
          Abrir data
        </button>
        <button className="px-4 py-2 rounded-lg bg-[#252b3d] text-white hover:bg-[#2d3548]" onClick={() => act('fix_playwright')}>
          Arreglar Playwright
        </button>
        <button className="px-4 py-2 rounded-lg bg-[#252b3d] text-white hover:bg-[#2d3548]" onClick={() => act('fix_browsers')}>
          Instalar browsers
        </button>
      </div>

      {msg && <div className="mt-4 text-sm text-[#94a3b8] whitespace-pre-wrap">{msg}</div>}
    </div>
  );
}
