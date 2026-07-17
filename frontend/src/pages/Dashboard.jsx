import { useEffect, useState } from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { PhoneCall, CheckCircle, TrendingUp, Cpu, DollarSign } from 'lucide-react';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Analytics Dashboard</h1>
          <p className="text-slate-400 text-sm">Real-time performance metrics and appointment confirmation ROI.</p>
        </div>
        <button 
          onClick={fetchStats}
          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-300 font-medium transition cursor-pointer"
        >
          Refresh Data
        </button>
      </div>

      {/* ROI & Financial Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
        <div className="glass rounded-xl p-5 border border-blue-500/10 flex items-start justify-between relative overflow-hidden">
          <div className="space-y-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Recovered Revenue</span>
            <span className="text-3xl font-extrabold text-blue-400 block">${stats?.roi.recoveredRevenue || 0}</span>
            <span className="text-xs text-slate-400 block">ROI estimate (value: ${stats?.roi.avgAppointmentValue}/appt)</span>
          </div>
          <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl">
            <DollarSign className="h-6 w-6 text-blue-400" />
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-indigo-500" />
        </div>

        <div className="glass rounded-xl p-5 border border-emerald-500/10 flex items-start justify-between relative overflow-hidden">
          <div className="space-y-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">No-shows Prevented</span>
            <span className="text-3xl font-extrabold text-emerald-400 block">{stats?.roi.preventedNoShows || 0}</span>
            <span className="text-xs text-slate-400 block">Based on ~18% base no-show rate</span>
          </div>
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
            <TrendingUp className="h-6 w-6 text-emerald-400" />
          </div>
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 to-teal-500" />
        </div>

        <div className="glass rounded-xl p-5 border border-slate-700/50 flex items-start justify-between">
          <div className="space-y-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Confirmed & Rescheduled</span>
            <span className="text-3xl font-extrabold text-slate-100 block">
              {(stats?.appointments.confirmed || 0) + (stats?.appointments.rescheduled || 0)}
            </span>
            <span className="text-xs text-slate-400 block">Confirmed: {stats?.appointments.confirmed} | Resched: {stats?.appointments.rescheduled}</span>
          </div>
          <div className="p-3 bg-slate-800 border border-slate-700 rounded-xl">
            <CheckCircle className="h-6 w-6 text-slate-300" />
          </div>
        </div>

        <div className="glass rounded-xl p-5 border border-slate-700/50 flex items-start justify-between">
          <div className="space-y-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Total Voice Calls</span>
            <span className="text-3xl font-extrabold text-slate-100 block">{stats?.performance.totalCalls || 0}</span>
            <span className="text-xs text-slate-400 block">Total cost: ${(stats?.performance.totalCostCents || 0) / 100}</span>
          </div>
          <div className="p-3 bg-slate-800 border border-slate-700 rounded-xl">
            <PhoneCall className="h-6 w-6 text-slate-300" />
          </div>
        </div>
      </div>

      {/* Latency Dashboard */}
      <div className="glass rounded-xl p-5 border border-indigo-500/10">
        <div className="flex items-center gap-2 mb-4">
          <Cpu className="h-5 w-5 text-indigo-400 animate-pulse" />
          <h2 className="text-lg font-semibold text-slate-200">AI Voice Pipeline Latency (Average Turnaround)</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 text-center">
            <span className="text-xs text-slate-400 block mb-1">STT (Deepgram Speech)</span>
            <span className="text-2xl font-bold text-slate-100">{stats?.performance.avgStt || 0}ms</span>
          </div>
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 text-center">
            <span className="text-xs text-slate-400 block mb-1">LLM (Claude Brain)</span>
            <span className="text-2xl font-bold text-slate-100">{stats?.performance.avgLlm || 0}ms</span>
          </div>
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 text-center">
            <span className="text-xs text-slate-400 block mb-1">TTS (Deepgram Aura Speech)</span>
            <span className="text-2xl font-bold text-slate-100">{stats?.performance.avgTts || 0}ms</span>
          </div>
          <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-4 text-center border-l-2 border-l-blue-500">
            <span className="text-xs text-blue-300 font-semibold block mb-1">Total Conversation Latency</span>
            <span className="text-2xl font-extrabold text-blue-400">{stats?.performance.avgTotal || 0}ms</span>
          </div>
        </div>
      </div>

      {/* Analytics Charts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass rounded-xl p-5 border border-slate-700/50 md:col-span-2">
          <h2 className="text-lg font-semibold text-slate-200 mb-4">Prevented No-Shows vs Outbound Calls</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={weeklyTrends}>
                <defs>
                  <linearGradient id="colorCalls" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorRecovered" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10B981" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="day" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} />
                <Area type="monotone" dataKey="calls" stroke="#3B82F6" fillOpacity={1} fill="url(#colorCalls)" strokeWidth={2} name="Total Calls" />
                <Area type="monotone" dataKey="recovered" stroke="#10B981" fillOpacity={1} fill="url(#colorRecovered)" strokeWidth={2} name="No-Shows Saved" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass rounded-xl p-5 border border-slate-700/50 flex flex-col justify-between">
          <h2 className="text-lg font-semibold text-slate-200 mb-2">Call Outcomes</h2>
          
          <div className="h-48 relative flex items-center justify-center">
            {stats?.outcomes && stats.outcomes.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={stats?.outcomes}
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {stats?.outcomes.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-sm text-slate-500">No outcomes tracked yet</div>
            )}
          </div>

          <div className="space-y-1.5 mt-4">
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
              <div className="text-center text-xs text-slate-500">Add appointments and trigger calls to populate logs.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
