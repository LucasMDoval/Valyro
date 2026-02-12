import { Info, HardDrive, Link2, AlertTriangle, ArrowLeft } from 'lucide-react';

export function AboutSection(props: { onBack?: () => void }) {
  return (
    <div className="space-y-6">
      <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Info className="w-5 h-5 text-[#13C1AC]" />
              <h3 className="text-lg font-semibold text-white">Sobre Valyro</h3>
            </div>
            <p className="text-sm text-[#94a3b8] mt-1">
              Una herramienta local para entender mejor el mercado de segunda mano.
            </p>
          </div>

          {props.onBack && (
            <button
              onClick={props.onBack}
              className="px-3 py-2 rounded-lg bg-[#252b3d] text-white hover:bg-[#2d3548] text-sm inline-flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Volver al panel
            </button>
          )}
        </div>
      </div>

      <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
        <h4 className="text-white font-semibold flex items-center gap-2">
          <Info className="w-4 h-4 text-[#13C1AC]" />
          ¿Qué es Valyro?
        </h4>
        <p className="text-sm text-[#94a3b8] mt-3">
          Valyro es una aplicación de análisis de mercado orientada a productos de segunda mano. Te ayuda a:
        </p>
        <ul className="mt-3 text-sm text-[#94a3b8] list-disc pl-5 space-y-1">
          <li>Analizar anuncios desde tu propio ordenador.</li>
          <li>Calcular rangos de precios “normales”, rápidos y lentos.</li>
          <li>Ver cómo evoluciona el precio de un producto con el tiempo.</li>
          <li>Comparar varios productos en una misma tabla.</li>
        </ul>
      </div>

      <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
        <h4 className="text-white font-semibold flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-[#13C1AC]" />
          ¿Dónde se ejecuta?
        </h4>

        <p className="text-sm text-[#94a3b8] mt-3">
          Todo el procesamiento se hace de forma local:
        </p>

        <ul className="mt-3 text-sm text-[#94a3b8] list-disc pl-5 space-y-1">
          <li>No se envían los datos a servidores externos.</li>
          <li>
            La base de datos se guarda en la carpeta <span className="text-white">data/</span> del proyecto.
          </li>
          <li>
            Los informes HTML y gráficos se guardan en <span className="text-white">reports/</span> y{' '}
            <span className="text-white">plots/</span>.
          </li>
        </ul>
      </div>

      <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
        <h4 className="text-white font-semibold flex items-center gap-2">
          <Link2 className="w-4 h-4 text-[#13C1AC]" />
          Relación con Wallapop u otras plataformas
        </h4>

        <p className="text-sm text-[#94a3b8] mt-3">
          Valyro no está afiliado, patrocinado ni aprobado por Wallapop ni por ninguna otra plataforma de compraventa.
          Es simplemente una herramienta técnica que tú ejecutas en tu propio equipo para analizar los datos que obtienes
          a través de tu propia conexión.
        </p>
      </div>

      <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
        <h4 className="text-white font-semibold flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-[#13C1AC]" />
          Responsabilidad de uso
        </h4>

        <p className="text-sm text-[#94a3b8] mt-3">
          Eres responsable de respetar las condiciones de uso de las plataformas que utilices, así como la normativa
          aplicable en materia de scraping, protección de datos y propiedad intelectual. Valyro no se hace responsable
          del uso que se haga de la herramienta.
        </p>
      </div>
    </div>
  );
}
