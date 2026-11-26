import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Mic2,
  Calendar,
  BookOpen,
  Bot,
  PhoneCall,
  Settings,
  Sparkles,
  Radio,
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Voice Sandbox', href: '/sandbox', icon: Mic2, badge: 'Live AI' },
  { name: 'Appointments', href: '/appointments', icon: Calendar },
  { name: 'Knowledge Base', href: '/knowledge', icon: BookOpen, badge: 'pgvector' },
  { name: 'Voice Agent', href: '/agent', icon: Bot },
  { name: 'Call Logs', href: '/calls', icon: PhoneCall },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-slate-950 border-r border-slate-800/80 flex flex-col shrink-0 h-screen sticky top-0">
      {/* Brand Header */}
      <div className="h-16 flex items-center gap-3 px-6 border-b border-slate-800/80">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/25">
          <Radio className="w-5 h-5 text-white animate-pulse" />
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            <span className="font-extrabold text-white text-base tracking-tight">VoxAI</span>
            <span className="px-1.5 py-0.2 bg-blue-500/20 text-blue-400 text-[10px] font-bold rounded">SaaS</span>
          </div>
          <p className="text-[11px] text-slate-400">Autonomous Voice Ops</p>
        </div>
      </div>

      {/* Nav Links */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
          Core Operations
        </div>
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            end={item.href === '/'}
            className={({ isActive }) =>
              `flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30 shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-900/60'
              }`
            }
          >
            <div className="flex items-center gap-3">
              <item.icon className="w-4 h-4 shrink-0" />
              <span>{item.name}</span>
            </div>
            {item.badge && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-400/20">
                {item.badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Telephony Status Footer */}
      <div className="p-4 border-t border-slate-800/80 m-3 rounded-xl bg-slate-900/40 border">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            VoBiz Primary
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-mono font-bold">
            India TRAI
          </span>
        </div>
        <p className="text-[11px] text-slate-400">
          8kHz G.711 PCMU voice pipeline active with Twilio global failover.
        </p>
      </div>
    </aside>
  );
};
