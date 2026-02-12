import { Bell, User } from 'lucide-react';

export function Header() {
  return (
    <header className="bg-[#1e293b] border-b border-[#2d3548] px-8 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white">Bienvenido de nuevo</h2>
          <p className="text-sm text-[#94a3b8] mt-1">Aquí está lo que está pasando con tus análisis hoy</p>
        </div>
        
        <div className="flex items-center gap-4">
          <button className="p-2 hover:bg-[#252b3d] rounded-lg transition-colors relative">
            <Bell className="w-5 h-5 text-[#94a3b8]" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-[#13C1AC] rounded-full"></span>
          </button>
          <button className="flex items-center gap-2 p-2 hover:bg-[#252b3d] rounded-lg transition-colors">
            <div className="w-8 h-8 bg-gradient-to-br from-[#13C1AC] to-[#0E8072] rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-white" />
            </div>
          </button>
        </div>
      </div>
    </header>
  );
}