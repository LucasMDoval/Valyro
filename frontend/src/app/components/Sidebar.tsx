import { Search, Calendar, User, Crown, Settings, Activity, Info, Scale, Mail } from 'lucide-react';

interface SidebarProps {
  activeSection: string;
  onSectionChange: (section: string) => void;
}

export function Sidebar({ activeSection, onSectionChange }: SidebarProps) {
  const topMenuItems = [
  { id: 'analyze', label: 'Analiza ahora un producto', icon: Search },
  { id: 'compare', label: 'Comparar keywords', icon: Settings },
  { id: 'auto-analysis', label: 'Análisis automático diario', icon: Calendar },
];


  const bottomMenuItems = [
  { id: 'diagnostic', label: 'Diagnóstico / Setup', icon: Activity },
  { id: 'about', label: 'Sobre', icon: Info },
  { id: 'legal', label: 'Legal', icon: Scale },
  { id: 'upgrade', label: 'Upgrade PRO', icon: Crown },
];


  return (
    <aside className="w-64 bg-[#1a1f2e] border-r border-[#2d3548] flex flex-col h-screen">
      {/* Logo y eslogan */}
      <div className="p-6 border-b border-[#2d3548]">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 bg-gradient-to-br from-[#13C1AC] to-[#0E8072] rounded-lg flex items-center justify-center">
            <span className="text-white font-bold">V</span>
          </div>
          <h1 className="text-xl font-bold text-white">Valyro</h1>
        </div>
        <p className="text-sm text-[#94a3b8] italic">convierte datos en decisiones</p>
      </div>

      {/* Menú superior */}
      <nav className="flex-1 p-4">
        <ul className="space-y-1">
          {topMenuItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.id}>
                <button
                  onClick={() => onSectionChange(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors ${
                    activeSection === item.id
                      ? 'bg-[#13C1AC]/20 text-[#13C1AC]'
                      : 'text-[#94a3b8] hover:bg-[#252b3d] hover:text-white'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="text-sm">{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Menú inferior */}
      <nav className="p-4 border-t border-[#2d3548]">
        <ul className="space-y-1">
          {bottomMenuItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.id}>
                <button
                  onClick={() => onSectionChange(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors ${
                    activeSection === item.id
                      ? 'bg-[#13C1AC]/20 text-[#13C1AC]'
                      : 'text-[#94a3b8] hover:bg-[#252b3d] hover:text-white'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="text-sm">{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}