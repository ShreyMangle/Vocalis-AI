import { useEffect, useState } from 'react';
import { Phone, Calendar, Clock, DollarSign, Cpu, ChevronDown, ChevronUp, MessageSquare } from 'lucide-react';

export default function CallLogs() {
  const [logs, setLogs] = useState([]);
  const [expandedLogId, setExpandedLogId] = useState(null);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/calls', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setLogs(data || []);
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  };

  const toggleExpand = (id) => {
    setExpandedLogId(expandedLogId === id ? null : id);
  };

  const parseTranscript = (jsonStr) => {
    try {
      return JSON.parse(jsonStr) || [];
    } catch {
      return [];
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Call History & Logs</h1>
        <p className="text-slate-400 text-sm">Review call details, conversation transcripts, and latency logs.</p>
      </div>

      <div className="glass rounded-xl border border-slate-700/50 overflow-hidden">
        <div className="divide-y divide-slate-800/80">
          {logs.length > 0 ? (
            logs.map((log) => {
              const isExpanded = expandedLogId === log.id;
              const dialogue = parseTranscript(log.transcript);

              return (
                <div key={log.id} className="transition-all hover:bg-slate-900/10">
                  {/* Summary Bar */}
                  <div 
                    onClick={() => toggleExpand(log.id)}
                    className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 cursor-pointer select-none"
                  >
                    <div className="flex items-start md:items-center gap-4">
                      <div className="p-2.5 bg-slate-800 border border-slate-700 rounded-xl">
                        <Phone className="h-5 w-5 text-slate-400" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-200">{log.customer_name}</span>
                          <span className="text-xs text-slate-500 font-mono">{log.customer_phone}</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400 mt-1">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3.5 w-3.5 text-slate-500" />
                            {new Date(log.started_at).toLocaleString()}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5 text-slate-500" />
                            {log.duration_seconds} seconds
                          </span>
                          <span className="flex items-center gap-0.5 font-semibold text-emerald-400/90">
                            <DollarSign className="h-3.5 w-3.5 text-emerald-500/80" />
                            {(log.cost_cents / 100).toFixed(3)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 self-end md:self-auto">
                      {/* Latency badge */}
                      <div className="hidden md:flex items-center gap-1.5 px-2 py-1 bg-slate-800/80 border border-slate-700/60 rounded-md text-xs text-slate-300">
                        <Cpu className="h-3.5 w-3.5 text-indigo-400" />
                        <span>Latency: {log.stt_latency_ms + log.llm_latency_ms + log.tts_latency_ms}ms</span>
                      </div>

                      {/* Outcome badge */}
                      <span
                        className={`inline-flex items-center px-3 py-1 border rounded-full text-xs font-semibold uppercase ${
                          log.outcome === 'confirmed'
                            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                            : log.outcome === 'rescheduled'
                            ? 'bg-blue-500/10 border-blue-500/20 text-blue-400'
                            : log.outcome === 'cancelled'
                            ? 'bg-red-500/10 border-red-500/20 text-red-400'
                            : log.outcome === 'escalated'
                            ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                            : 'bg-slate-700/10 border-slate-600/20 text-slate-400'
                        }`}
                      >
                        {log.outcome}
                      </span>

                      {isExpanded ? <ChevronUp className="h-5 w-5 text-slate-500" /> : <ChevronDown className="h-5 w-5 text-slate-500" />}
                    </div>
                  </div>

                  {/* Expanded Transcript Area */}
                  {isExpanded && (
                    <div className="px-5 pb-6 pt-2 border-t border-slate-800/60 bg-slate-900/30 grid grid-cols-1 md:grid-cols-3 gap-6">
                      
                      {/* Call Dialogue */}
                      <div className="md:col-span-2 space-y-4">
                        <div className="flex items-center gap-1.5 mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">
                          <MessageSquare className="h-4 w-4" />
                          <span>Conversation Transcript</span>
                        </div>

                        <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2 bg-slate-950/40 p-4 border border-slate-800/80 rounded-xl">
                          {dialogue.length > 0 ? (
                            dialogue.map((turn, index) => (
                              <div
                                key={index}
                                className={`flex flex-col max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                                  turn.role === 'assistant'
                                    ? 'bg-slate-800/80 text-slate-200 border border-slate-700/40 self-start mr-auto rounded-tl-none'
                                    : 'bg-blue-600/20 text-blue-200 border border-blue-500/20 self-end ml-auto rounded-tr-none'
                                }`}
                              >
                                <span className="text-[10px] font-bold uppercase tracking-wide opacity-50 mb-1">
                                  {turn.role === 'assistant' ? 'AI Virtual Agent' : 'Customer'}
                                </span>
                                <span>{turn.content}</span>
                              </div>
                            ))
                          ) : (
                            <p className="text-slate-500 text-xs italic text-center py-6">
                              No verbal transcript registered. The call may have disconnected immediately.
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Technical Latency Metrics */}
                      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-4">
                        <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-400">
                          <Cpu className="h-4 w-4 text-indigo-400" />
                          <span>Latency Logs (Average)</span>
                        </div>
                        
                        <div className="space-y-2.5 text-sm">
                          <div className="flex justify-between items-center py-1.5 border-b border-slate-800/50">
                            <span className="text-slate-400">STT (Deepgram Audio)</span>
                            <span className="font-semibold font-mono text-slate-200">{log.stt_latency_ms}ms</span>
                          </div>
                          <div className="flex justify-between items-center py-1.5 border-b border-slate-800/50">
                            <span className="text-slate-400">LLM (Claude Brain)</span>
                            <span className="font-semibold font-mono text-slate-200">{log.llm_latency_ms}ms</span>
                          </div>
                          <div className="flex justify-between items-center py-1.5 border-b border-slate-800/50">
                            <span className="text-slate-400">TTS (Deepgram Aura)</span>
                            <span className="font-semibold font-mono text-slate-200">{log.tts_latency_ms}ms</span>
                          </div>
                          <div className="flex justify-between items-center py-2 text-blue-400 font-semibold bg-blue-900/10 rounded px-2 mt-4 border border-blue-500/10">
                            <span>Total p50/p95 Delay</span>
                            <span className="font-mono">{log.stt_latency_ms + log.llm_latency_ms + log.tts_latency_ms}ms</span>
                          </div>
                        </div>
                      </div>

                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="text-center py-12 text-slate-500 text-sm">
              No voice calls placed yet. Upload appointments and trigger confirmation calls to populate history.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
