import { useEffect, useState } from 'react';
import { dailyRunNow, getDailyConfig, installDailyTask, removeDailyTask, saveDailyConfig } from '../api/valyro';

type Row = {
  keyword: string;
  min_price?: number | null;
  max_price?: number | null;
  filter_mode?: 'soft' | 'strict' | 'off';
  exclude_bad_text?: boolean;
};

export function DailySection() {
  const [rows, setRows] = useState<Row[]>([]);
  const [defaults, setDefaults] = useState<any>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [scheduleTime, setScheduleTime] = useState<string>('');
  const [taskInstalled, setTaskInstalled] = useState<boolean>(false);
  const [isWindows, setIsWindows] = useState<boolean>(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function reload() {
    const data = await getDailyConfig();
    setRows(data.rows ?? []);
    setDefaults(data.defaults ?? null);
    setWarnings(data.warnings ?? []);
    setScheduleTime(data.schedule_time ?? '');
    setTaskInstalled(!!data.task_installed);
    setIsWindows(!!data.is_windows);
  }

  useEffect(() => {
    reload().catch((e) => setMsg(e?.message ?? String(e)));
  }, []);

  function updateRow(i: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function addRow() {
    setRows((prev) => [
      ...prev,
      { keyword: '', min_price: null, max_price: null, filter_mode: 'soft', exclude_bad_text: true },
    ]);
  }

  function removeRow(i: number) {
    setRows((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function onSave() {
    setBusy(true);
    setMsg(null);
    try {
      await saveDailyConfig(rows);
      setMsg('Guardado.');
      await reload();
    } catch (e: any) {
      setMsg(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onRunNow() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await dailyRunNow();
      setMsg(r.ok ? 'Scrape diario lanzado (mira logs si quieres detalle).' : `Falló: ${r.message}`);
      await reload();
    } catch (e: any) {
      setMsg(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onInstallTask() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await installDailyTask(scheduleTime);
      setMsg(r.ok ? `Tarea instalada/actualizada a las ${r.time}.` : `Falló: ${r.message}`);
      await reload();
    } catch (e: any) {
      setMsg(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onRemoveTask() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await removeDailyTask();
      setMsg(r.ok ? 'Tarea eliminada.' : `Falló: ${r.message}`);
      await reload();
    } catch (e: any) {
      setMsg(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
        <h3 className="text-lg font-semibold text-white">Análisis automático diario</h3>
        <p className="text-sm text-[#94a3b8] mt-1">Edita tus keywords diarias y la programación.</p>

        {warnings.length > 0 && (
          <div className="mt-4 text-sm text-yellow-200 whitespace-pre-wrap">
            {warnings.map((w, i) => (
              <div key={i}>• {w}</div>
            ))}
          </div>
        )}

        <div className="mt-6 overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#2d3548]">
                <th className="text-left py-2 px-3 text-sm text-white">Keyword</th>
                <th className="text-right py-2 px-3 text-sm text-white">Min €</th>
                <th className="text-right py-2 px-3 text-sm text-white">Max €</th>
                <th className="text-left py-2 px-3 text-sm text-white">Filtro</th>
                <th className="text-left py-2 px-3 text-sm text-white">Texto</th>
                <th className="py-2 px-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-[#2d3548]/50">
                  <td className="py-2 px-3">
                    <input
                      className="w-full bg-[#1a1f2e] border border-[#2d3548] rounded-lg px-3 py-2 text-white"
                      value={r.keyword ?? ''}
                      onChange={(e) => updateRow(i, { keyword: e.target.value })}
                      placeholder="Ej: iPhone 14 Pro"
                    />
                  </td>
                  <td className="py-2 px-3 text-right">
                    <input
                      className="w-28 bg-[#1a1f2e] border border-[#2d3548] rounded-lg px-3 py-2 text-white text-right"
                      value={r.min_price ?? ''}
                      onChange={(e) => updateRow(i, { min_price: e.target.value === '' ? null : Number(e.target.value) })}
                      placeholder="—"
                    />
                  </td>
                  <td className="py-2 px-3 text-right">
                    <input
                      className="w-28 bg-[#1a1f2e] border border-[#2d3548] rounded-lg px-3 py-2 text-white text-right"
                      value={r.max_price ?? ''}
                      onChange={(e) => updateRow(i, { max_price: e.target.value === '' ? null : Number(e.target.value) })}
                      placeholder="—"
                    />
                  </td>
                  <td className="py-2 px-3">
                    <select
                      className="bg-[#1a1f2e] border border-[#2d3548] rounded-lg px-3 py-2 text-white"
                      value={(r.filter_mode ?? 'soft') as any}
                      onChange={(e) => updateRow(i, { filter_mode: e.target.value as any })}
                    >
                      <option value="soft">soft</option>
                      <option value="strict">strict</option>
                      <option value="off">off</option>
                    </select>
                  </td>
                  <td className="py-2 px-3">
                    <label className="flex items-center gap-2 text-sm text-[#94a3b8]">
                      <input
                        type="checkbox"
                        checked={r.exclude_bad_text ?? true}
                        onChange={(e) => updateRow(i, { exclude_bad_text: e.target.checked })}
                      />
                      excluir “basura”
                    </label>
                  </td>
                  <td className="py-2 px-3 text-right">
                    <button
                      className="text-sm text-red-300 hover:text-red-200"
                      onClick={() => removeRow(i)}
                      disabled={busy}
                    >
                      borrar
                    </button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td className="py-3 px-3 text-sm text-[#94a3b8]" colSpan={6}>
                    No hay keywords configuradas.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex gap-2">
          <button
            className="px-4 py-2 rounded-lg bg-[#252b3d] text-white hover:bg-[#2d3548]"
            onClick={addRow}
            disabled={busy}
          >
            + Añadir
          </button>

          <button
            className="px-4 py-2 rounded-lg bg-[#13C1AC] text-[#0F172A] font-semibold hover:opacity-90"
            onClick={onSave}
            disabled={busy}
          >
            Guardar
          </button>

          <button
            className="ml-auto px-4 py-2 rounded-lg bg-white text-[#13C1AC] font-semibold hover:bg-white/90"
            onClick={onRunNow}
            disabled={busy}
          >
            Probar ahora
          </button>
        </div>

        <div className="mt-6 border-t border-[#2d3548] pt-4">
          <h4 className="text-white font-semibold">Programación</h4>
          {!isWindows ? (
            <p className="text-sm text-[#94a3b8] mt-1">
              La tarea automática está pensada para Windows (Task Scheduler).
            </p>
          ) : (
            <div className="mt-3 flex items-center gap-3">
              <input
                className="bg-[#1a1f2e] border border-[#2d3548] rounded-lg px-3 py-2 text-white w-28"
                value={scheduleTime}
                onChange={(e) => setScheduleTime(e.target.value)}
                placeholder="09:30"
              />
              <button
                className="px-4 py-2 rounded-lg bg-[#252b3d] text-white hover:bg-[#2d3548]"
                onClick={onInstallTask}
                disabled={busy}
              >
                {taskInstalled ? 'Actualizar' : 'Instalar'}
              </button>
              {taskInstalled && (
                <button
                  className="px-4 py-2 rounded-lg bg-red-500/20 text-red-200 hover:bg-red-500/30"
                  onClick={onRemoveTask}
                  disabled={busy}
                >
                  Quitar tarea
                </button>
              )}
            </div>
          )}
        </div>

        {msg && <div className="mt-4 text-sm text-[#94a3b8] whitespace-pre-wrap">{msg}</div>}
      </div>
    </div>
  );
}
