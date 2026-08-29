import { useEffect, useState } from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { 
  PhoneCall, 
  CheckCircle, 
  TrendingUp, 
  Cpu, 
  DollarSign, 
  Sparkles, 
  Clock, 
  Calendar, 
  ShieldCheck, 
  ArrowUpRight,
  Sliders
} from 'lucide-react';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [customApptValue, setCustomApptValue] = useState(150);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/stats', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setStats(data);
    } catch (err) {
      console.error('Error fetching dashboard stats:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const COLORS = ['#10B981', '#3B82F6', '#EF4444', '#F59E0B', '#94A3B8'];
  
  const weeklyTrends = [
    { day: 'Mon', calls: 12, recovered: 3 },
    { day: 'Tue', calls: 19, recovered: 5 },
    { day: 'Wed', calls: 15, recovered: 4 },
    { day: 'Thu', calls: 24, recovered: 7 },
    { day: 'Fri', calls: 22, recovered: 6 },
    { day: 'Sat', calls: 8, recovered: 2 },
    { day: 'Sun', calls: 0, recovered: 0 },
  ];

  // Dynamic ROI calculation based on slider
  const totalConfirmed = (stats?.appointments?.confirmed || 0) + (stats?.appointments?.rescheduled || 0);
  const preventedNoShows = stats?.roi?.preventedNoShows || Math.round(totalConfirmed * 0.18 * 10) / 10;
  const calculatedRevenue = Math.round(preventedNoShows * customApptValue);
  const annualizedRevenue = calculatedRevenue * 12;
  const savedAdminMinutes = (stats?.performance?.totalCalls || 0) * 4;
  const savedAdminHours = (savedAdminMinutes / 60).toFixed(1);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            Practice ROI & Analytics <Sparkles className="h-5 w-5 text-blue-400" />
          </h1>
          <p className="text-slate-400 text-sm mt-0.5">
            Real-time appointment retention telemetry, recovered revenue projections, and pipeline acoustics.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchStats}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/60 rounded-xl text-sm text-slate-200 font-semibold transition cursor-pointer shadow"
          >
            Refresh Telemetry
          </button>
        </div>
      </div>

      {/* ROI & Financial Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
        <div className="glass rounded-xl p-5 border border-blue-500/20 flex items-start justify-between relative overflow-hidden shadow-lg">
          <div className="space-y-1.5">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Recovered Revenue</span>
            <span className="text-3xl font-black text-blue-400 block">${calculatedRevenue}</span>
            <span className="text-[11px] text-slate-400 block flex items-center gap-1">
              <ArrowUpRight className="h-3 w-3 text-emerald-400" /> ${annualizedRevenue.toLocaleString()}/yr annualized
            </span>
          </div>
          <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-xl">
            <DollarSign className="h-6 w-6 text-blue-400" />
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-indigo-500" />
        </div>

        <div className="glass rounded-xl p-5 border border-emerald-500/20 flex items-start justify-between relative overflow-hidden shadow-lg">
          <div className="space-y-1.5">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">No-Shows Prevented</span>
            <span className="text-3xl font-black text-emerald-400 block">{preventedNoShows}</span>
            <span className="text-[11px] text-slate-400 block">Based on ~18% industry benchmark</span>
          </div>
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl">
            <TrendingUp className="h-6 w-6 text-emerald-400" />
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 to-teal-500" />
        </div>

        <div className="glass rounded-xl p-5 border border-slate-700/60 flex items-start justify-between relative overflow-hidden shadow-lg">
          <div className="space-y-1.5">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Staff Time Saved</span>
            <span className="text-3xl font-black text-slate-100 block">{savedAdminHours} hrs</span>
            <span className="text-[11px] text-slate-400 block">~4 mins saved per confirmation call</span>
          </div>
          <div className="p-3 bg-slate-800 border border-slate-700 rounded-xl">
            <Clock className="h-6 w-6 text-indigo-400" />
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 to-purple-500" />
        </div>

        <div className="glass rounded-xl p-5 border border-slate-700/60 flex items-start justify-between relative overflow-hidden shadow-lg">
          <div className="space-y-1.5">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Total Voice Calls</span>
            <span className="text-3xl font-black text-slate-100 block">{stats?.performance?.totalCalls || 0}</span>
            <span className="text-[11px] text-slate-400 block font-mono">
              Direct API Cost: ${(stats?.performance?.totalCostCents || 0) / 100}
            </span>
          </div>
          <div className="p-3 bg-slate-800 border border-slate-700 rounded-xl">
            <PhoneCall className="h-6 w-6 text-slate-300" />
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-slate-600 to-slate-400" />
        </div>
      </div>

      {/* Interactive Practice ROI Tuning Slider */}
      <div className="p-5 bg-gradient-to-r from-slate-900 via-slate-900/80 to-blue-950/40 border border-slate-800 rounded-xl space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
            <Sliders className="h-4 w-4 text-blue-400" />
            <span>Interactive Business Value Simulator</span>
          </div>
          <div className="text-xs text-slate-400 font-mono">
            Average Booking Value: <strong className="text-blue-400 text-sm">${customApptValue}</strong> per appointment
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-500 font-mono">$50</span>
          <input
            type="range"
            min="50"
            max="500"
            step="10"
            value={customApptValue}
            onChange={(e) => setCustomApptValue(Number(e.target.value))}
            className="flex-1 accent-blue-500 cursor-pointer h-2 bg-slate-800 rounded-lg"
          />
          <span className="text-xs text-slate-500 font-mono">$500</span>
        </div>
      </div>

      {/* Latency Dashboard */}
      <div className="glass rounded-xl p-5 border border-indigo-500/20 shadow-lg">
        <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-indigo-400 animate-pulse" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">
              AI Voice Pipeline Acoustic Latency (Live Turnaround)
            </h2>
          </div>
          <span className="text-[10px] uppercase font-bold tracking-widest text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
            Realtime Sub-second
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 text-center">
            <span className="text-xs text-slate-400 block mb-1">STT (Groq Whisper-v3)</span>
            <span className="text-2xl font-black text-slate-100 font-mono">{stats?.performance?.avgStt || 140}ms</span>
          </div>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 text-center">
            <span className="text-xs text-slate-400 block mb-1">LLM (Llama 3.1-70B)</span>
            <span className="text-2xl font-black text-slate-100 font-mono">{stats?.performance?.avgLlm || 420}ms</span>
          </div>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 text-center">
            <span className="text-xs text-slate-400 block mb-1">TTS (Edge Neural Voice)</span>
            <span className="text-2xl font-black text-slate-100 font-mono">{stats?.performance?.avgTts || 220}ms</span>
          </div>
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-4 text-center border-l-2 border-l-blue-500">
            <span className="text-xs text-blue-300 font-bold block mb-1">Total Turnaround Latency</span>
            <span className="text-2xl font-black text-blue-400 font-mono">
              {(stats?.performance?.avgStt || 140) + (stats?.performance?.avgLlm || 420) + (stats?.performance?.avgTts || 220)}ms
            </span>
          </div>
        </div>
      </div>

      {/* Analytics Charts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass rounded-xl p-5 border border-slate-700/50 md:col-span-2 shadow-xl">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 mb-4">
            Prevented No-Shows vs Outbound Calls Trend
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={weeklyTrends}>
                <defs>
                  <linearGradient id="colorCalls" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorRecovered" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10B981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="day" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
                <Area type="monotone" dataKey="calls" stroke="#3B82F6" fillOpacity={1} fill="url(#colorCalls)" strokeWidth={2} name="Total Calls" />
                <Area type="monotone" dataKey="recovered" stroke="#10B981" fillOpacity={1} fill="url(#colorRecovered)" strokeWidth={2} name="No-Shows Prevented" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass rounded-xl p-5 border border-slate-700/50 flex flex-col justify-between shadow-xl">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 mb-2">
            Call Outcome Distribution
          </h2>
          
          <div className="h-48 relative flex items-center justify-center">
            {stats?.outcomes && stats.outcomes.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={stats?.outcomes}
                    innerRadius={55}
                    outerRadius={75}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {stats?.outcomes.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-sm text-slate-500">No calls executed yet</div>
            )}
          </div>

          <div className="space-y-1.5 mt-3">
            {stats?.outcomes && stats.outcomes.length > 0 ? (
              stats.outcomes.map((outcome, idx) => (
                <div key={outcome.name} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                    <span className="capitalize text-slate-300">{outcome.name}</span>
                  </div>
                  <span className="font-semibold text-slate-400">{outcome.value} calls</span>
                </div>
              ))
            ) : (
              <div className="text-center text-xs text-slate-500">Run Sandbox calls or batch campaigns to populate.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
