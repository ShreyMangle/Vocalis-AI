import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Building2, LogOut, ShieldCheck, Sparkles } from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, tenant, role, logout } = useAuth();

  return (
    <header className="h-16 bg-slate-950/80 backdrop-blur-md border-b border-slate-800/80 px-8 flex items-center justify-between sticky top-0 z-30">
      {/* Left: Tenant Indicator */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
          <Building2 className="w-3.5 h-3.5 text-blue-400" />
          <span className="font-semibold text-white">{tenant?.name || 'My Organization'}</span>
          <span className="text-[10px] text-slate-400 font-mono">({tenant?.plan || 'PRO'})</span>
        </div>
      </div>

      {/* Right: Telephony Status & User Menu */}
      <div className="flex items-center gap-4">
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="text-slate-300">Sub-second Latency:</span>
          <span className="font-mono text-emerald-400 font-bold">&lt; 500ms</span>
        </div>

        {/* User Card */}
        <div className="flex items-center gap-3 pl-3 border-l border-slate-800">
          <div className="text-right hidden sm:block">
            <p className="text-xs font-semibold text-white">{user?.full_name || 'Admin User'}</p>
            <p className="text-[10px] text-blue-400 font-medium flex items-center justify-end gap-1">
              <ShieldCheck className="w-3 h-3" />
              {role || 'OWNER'}
            </p>
          </div>

          <button
            onClick={logout}
            title="Log Out"
            className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
