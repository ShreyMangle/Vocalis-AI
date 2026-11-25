import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  CartesianGrid,
} from 'recharts';
import {
  PhoneCall,
  CheckCircle,
  TrendingUp,
  Cpu,
  Sparkles,
  Zap,
  Clock,
  CalendarCheck,
  ShieldCheck,
  ArrowUpRight,
} from 'lucide-react';
import { api } from '../lib/api';
import type { CallStats, Call } from '../types';

const COLORS = ['#10B981', '#3B82F6', '#EF4444', '#F59E0B', '#8B5CF6'];

export const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<CallStats | null>(null);
  const [recentCalls, setRecentCalls] = useState<Call[]>([]);
  const [appointmentsCount, setAppointmentsCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [statsData, callsData, apptsData] = await Promise.all([
        api.getCallStats().catch(() => null),
        api.listCalls(10).catch(() => ({ items: [], total: 0 })),
        api.listAppointments('CONFIRMED').catch(() => ({ items: [], total: 0 })),
      ]);
      setStats(statsData);
      setRecentCalls(callsData.items);
      setAppointmentsCount(apptsData.total);
    } finally {
      setLoading(false);
    }
  };

  // Build real call trend grouped by date from recent calls
  const trendData = recentCalls.length > 0
    ? recentCalls
        .slice()
        .reverse()
        .map((c, idx) => ({
          day: `#${idx + 1} (${new Date(c.started_at || c.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })})`,
          latency: (c.stt_latency_ms || 0) + (c.llm_latency_ms || 0) + (c.tts_latency_ms || 0),
          duration: c.duration_seconds,
        }))
    : [];

  const sentimentData = stats?.sentiment_breakdown
    ? Object.entries(stats.sentiment_breakdown)
        .filter(([, value]) => value > 0)
        .map(([name, value]) => ({ name, value }))
    : [];

  const totalCalls = stats?.total_calls ?? 0;
  const avgDuration = stats?.avg_duration_seconds ?? 0;
  const totalCostUsd = stats?.total_cost_usd ?? 0;
  const avgStt = stats?.avg_stt_latency_ms ?? 0;
  const avgLlm = stats?.avg_llm_latency_ms ?? 0;
  const avgTts = stats?.avg_tts_latency_ms ?? 0;
  const totalLatency = stats?.avg_e2e_latency_ms ?? avgStt + avgLlm + avgTts;

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="p-6 bg-gradient-to-r from-slate-900 via-blue-950/40 to-slate-900 border border-blue-500/30 rounded-2xl relative overflow-hidden shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-blue-500/20 border border-blue-400/30 text-blue-300 text-[10px] font-extrabold uppercase rounded tracking-wider">
              India VoBiz Live Streaming
            </span>
            <span className="text-xs text-slate-400">G.711 mu-law 8kHz Media Pipeline</span>
          </div>
          <h2 className="text-xl font-extrabold text-white">Autonomous Front-Desk Voice Receptionist</h2>
          <p className="text-xs text-slate-300 max-w-2xl">
            Handles live customer inbound calls, queries knowledge base with pgvector, validates doctor appointment calendars, and executes real-time bookings with sub-second response latency.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => navigate('/sandbox')}
            className="px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-2 shadow-lg shadow-blue-600/30 cursor-pointer"
          >
            <Zap className="h-4 w-4 text-yellow-300 fill-yellow-300" />
            Launch Voice Sandbox
          </button>
        </div>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass rounded-xl p-5 border border-slate-800 shadow">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2">
            <span>Total Calls Handled</span>
            <PhoneCall className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-black text-white">{loading ? '—' : totalCalls}</div>
          <p className="text-[11px] text-slate-400 mt-1">
            Avg duration: {avgDuration}s
          </p>
        </div>

        <div className="glass rounded-xl p-5 border border-slate-800 shadow">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2">
            <span>Cumulative Voice Cost</span>
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-black text-emerald-400">${totalCostUsd.toFixed(2)}</div>
          <p className="text-[11px] text-slate-400 mt-1">Across {stats?.total_duration_minutes ?? 0} call mins</p>
        </div>

        <div className="glass rounded-xl p-5 border border-slate-800 shadow">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2">
            <span>Confirmed Appointments</span>
            <CalendarCheck className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-black text-white">{loading ? '—' : appointmentsCount}</div>
          <p className="text-[11px] text-slate-400 mt-1">Active DB bookings</p>
        </div>

        <div className="glass rounded-xl p-5 border border-slate-800 shadow">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2">
            <span>Avg E2E Turnaround</span>
            <Cpu className="w-4 h-4 text-yellow-400" />
          </div>
          <div className="text-2xl font-black text-yellow-400 font-mono">{totalLatency}ms</div>
          <p className="text-[11px] text-slate-400 mt-1">STT {avgStt}ms • LLM {avgLlm}ms • TTS {avgTts}ms</p>
        </div>
      </div>

      {/* Latency Pipeline Card */}
      <div className="glass rounded-xl p-5 border border-slate-800 shadow">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Cpu className="w-4 h-4 text-blue-400" />
              Real-Time Voice Pipeline Latency Telemetry
            </h3>
            <p className="text-xs text-slate-400">Measured turnaround performance across recorded calls</p>
          </div>
          <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded border border-emerald-500/20">
            Target &lt; 800ms
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[11px] text-slate-400 block mb-1">STT (Groq / Deepgram)</span>
            <span className="text-xl font-black text-slate-200 font-mono">{avgStt}ms</span>
          </div>
          <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[11px] text-slate-400 block mb-1">LLM + Tools (Llama 3.3 / Gemini)</span>
            <span className="text-xl font-black text-slate-200 font-mono">{avgLlm}ms</span>
          </div>
          <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[11px] text-slate-400 block mb-1">TTS First-Audio (Edge / Sarvam / Cartesia)</span>
            <span className="text-xl font-black text-slate-200 font-mono">{avgTts}ms</span>
          </div>
          <div className="bg-blue-950/40 p-3.5 rounded-xl border border-blue-500/30 text-center">
            <span className="text-[11px] text-blue-300 font-bold block mb-1">Total Turnaround Latency</span>
            <span className="text-xl font-black text-blue-400 font-mono">{totalLatency}ms</span>
          </div>
        </div>
      </div>

      {/* Visual Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="glass rounded-xl p-5 border border-slate-800 shadow lg:col-span-2">
          <h3 className="text-sm font-bold text-white mb-4">Recent Call Latency & Duration Telemetry</h3>
          <div className="h-64">
            {trendData.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs space-y-2">
                <p>No live call telemetry recorded yet.</p>
                <button
                  onClick={() => navigate('/sandbox')}
                  className="px-3 py-1.5 bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded-lg font-semibold cursor-pointer"
                >
                  Run a test call in Voice Sandbox
                </button>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData}>
                  <defs>
                    <linearGradient id="callsGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="confirmedGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="day" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
                  <Area type="monotone" dataKey="latency" stroke="#3B82F6" fill="url(#callsGradient)" strokeWidth={2} name="E2E Latency (ms)" />
                  <Area type="monotone" dataKey="duration" stroke="#10B981" fill="url(#confirmedGradient)" strokeWidth={2} name="Duration (s)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="glass rounded-xl p-5 border border-slate-800 shadow flex flex-col justify-between">
          <h3 className="text-sm font-bold text-white mb-2">Sentiment Breakdown</h3>
          {sentimentData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-slate-500 text-xs">
              No sentiment data recorded yet.
            </div>
          ) : (
            <>
              <div className="h-48 relative flex items-center justify-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={sentimentData} innerRadius={50} outerRadius={70} paddingAngle={4} dataKey="value">
                      {sentimentData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="space-y-1.5 mt-2">
                {sentimentData.map((item, idx) => (
                  <div key={item.name} className="flex items-center justify-between text-xs text-slate-300">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                      <span className="capitalize">{item.name.toLowerCase()}</span>
                    </div>
                    <span className="font-semibold text-slate-400">{item.value} calls</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
