import { useEffect, useState } from 'react';
import { 
  Phone, 
  Calendar, 
  Clock, 
  DollarSign, 
  Cpu, 
  ChevronDown, 
  ChevronUp, 
  MessageSquare, 
  Download, 
  Smile, 
  Meh, 
  Frown, 
  AlertTriangle, 
  Tag, 
  Search,
  Filter,
  FileText
} from 'lucide-react';

export default function CallLogs() {
  const [logs, setLogs] = useState([]);
  const [expandedLogId, setExpandedLogId] = useState(null);
  const [outcomeFilter, setOutcomeFilter] = useState('all');
  const [sentimentFilter, setSentimentFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

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

  const handleExportCsv = () => {
    const token = localStorage.getItem('token');
    window.open(`http://localhost:5000/api/calls/export.csv`, '_blank');
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment) {
      case 'Positive':
        return <Smile className="h-3.5 w-3.5 text-emerald-400" />;
      case 'Frustrated':
        return <Frown className="h-3.5 w-3.5 text-red-400" />;
      case 'Urgent':
        return <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />;
      default:
        return <Meh className="h-3.5 w-3.5 text-slate-400" />;
    }
  };

  const filteredLogs = logs.filter((log) => {
    const matchesOutcome = outcomeFilter === 'all' || log.outcome === outcomeFilter;
    const matchesSentiment = sentimentFilter === 'all' || (log.sentiment || 'Neutral') === sentimentFilter;
    const matchesSearch =
      log.customer_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.customer_phone?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (log.intent && log.intent.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesOutcome && matchesSentiment && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-100">Call History & Intelligence</h1>
          <p className="text-slate-400 text-sm">
            Inspect turn-by-turn dialogue transcripts, acoustic latency breakdowns, sentiment, and AI intent tags.
          </p>
        </div>
        <div>
          <button
            onClick={handleExportCsv}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm text-slate-200 font-semibold transition flex items-center gap-2 cursor-pointer shadow"
          >
            <Download className="h-4 w-4 text-blue-400" /> Export CSV Report
          </button>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {/* Outcome Filter */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400 font-medium mr-1">Outcome:</span>
            <select
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value)}
              className="bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-slate-300 py-1.5 px-2.5 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Outcomes</option>
              <option value="confirmed">Confirmed</option>
              <option value="rescheduled">Rescheduled</option>
              <option value="cancelled">Cancelled</option>
              <option value="escalated">Escalated</option>
            </select>
          </div>

          {/* Sentiment Filter */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400 font-medium mr-1">Sentiment:</span>
            <select
              value={sentimentFilter}
              onChange={(e) => setSentimentFilter(e.target.value)}
              className="bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-slate-300 py-1.5 px-2.5 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Sentiments</option>
              <option value="Positive">Positive</option>
              <option value="Neutral">Neutral</option>
              <option value="Urgent">Urgent</option>
              <option value="Frustrated">Frustrated</option>
            </select>
          </div>
        </div>

        {/* Search Query */}
        <div className="relative w-full md:w-64">
          <Search className="h-4 w-4 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search name, phone, intent..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Logs List */}
      <div className="glass rounded-xl border border-slate-700/50 overflow-hidden shadow-xl">
        <div className="divide-y divide-slate-800/80">
          {filteredLogs.length > 0 ? (
            filteredLogs.map((log) => {
              const isExpanded = expandedLogId === log.id;
              const dialogue = parseTranscript(log.transcript);
              const sentiment = log.sentiment || 'Neutral';
              const intent = log.intent || 'Confirmation';

              return (
                <div key={log.id} className="transition-all hover:bg-slate-900/20">
                  {/* Summary Bar */}
                  <div 
                    onClick={() => toggleExpand(log.id)}
                    className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 cursor-pointer select-none"
                  >
                    <div className="flex items-start md:items-center gap-4">
                      <div className="p-2.5 bg-slate-800/80 border border-slate-700/80 rounded-xl text-blue-400">
                        <Phone className="h-5 w-5" />
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
                            {log.duration_seconds}s call
                          </span>
                          <span className="flex items-center gap-0.5 font-semibold text-emerald-400/90">
                            <DollarSign className="h-3.5 w-3.5 text-emerald-500/80" />
                            {(log.cost_cents / 100).toFixed(3)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2.5 self-end md:self-auto">
                      {/* Sentiment Badge */}
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-800/80 border border-slate-700/60 rounded-lg text-xs font-semibold text-slate-300">
                        {getSentimentIcon(sentiment)}
                        <span>{sentiment}</span>
                      </span>

                      {/* Intent Badge */}
                      <span className="hidden sm:inline-flex items-center gap-1 px-2.5 py-1 bg-indigo-950/40 border border-indigo-500/30 rounded-lg text-xs font-medium text-indigo-300">
                        <Tag className="h-3 w-3 text-indigo-400" />
                        <span>{intent}</span>
                      </span>

                      {/* Latency badge */}
                      <div className="hidden lg:flex items-center gap-1 px-2 py-1 bg-slate-800/80 border border-slate-700/60 rounded-md text-xs text-slate-300 font-mono">
                        <Cpu className="h-3.5 w-3.5 text-blue-400" />
                        <span>{log.stt_latency_ms + log.llm_latency_ms + log.tts_latency_ms}ms</span>
                      </div>

                      {/* Outcome badge */}
                      <span
                        className={`inline-flex items-center px-3 py-1 border rounded-full text-xs font-bold uppercase tracking-wider ${
                          log.outcome === 'confirmed'
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                            : log.outcome === 'rescheduled'
                            ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                            : log.outcome === 'cancelled'
                            ? 'bg-red-500/10 border-red-500/30 text-red-400'
                            : log.outcome === 'escalated'
                            ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                            : 'bg-slate-700/10 border-slate-600/30 text-slate-400'
                        }`}
                      >
                        {log.outcome}
                      </span>

                      {isExpanded ? <ChevronUp className="h-5 w-5 text-slate-400" /> : <ChevronDown className="h-5 w-5 text-slate-400" />}
                    </div>
                  </div>

                  {/* Expanded Transcript Area */}
                  {isExpanded && (
                    <div className="px-5 pb-6 pt-3 border-t border-slate-800/80 bg-slate-900/40 grid grid-cols-1 md:grid-cols-3 gap-6">
                      
                      {/* Call Dialogue */}
                      <div className="md:col-span-2 space-y-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-400">
                            <MessageSquare className="h-4 w-4 text-blue-400" />
                            <span>Conversation Transcript</span>
                          </div>
                          {log.notes && (
                            <span className="text-xs text-slate-400 italic">
                              Note: {log.notes}
                            </span>
                          )}
                        </div>

                        <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2 bg-slate-950/60 p-4 border border-slate-800/80 rounded-xl">
                          {dialogue.length > 0 ? (
                            dialogue.map((turn, index) => (
                              <div
                                key={index}
                                className={`flex flex-col max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                                  turn.role === 'assistant'
                                    ? 'bg-slate-800/90 text-slate-200 border border-slate-700/40 self-start mr-auto rounded-tl-none'
                                    : 'bg-blue-600/20 text-blue-100 border border-blue-500/30 self-end ml-auto rounded-tr-none'
                                }`}
                              >
                                <span className="text-[10px] font-bold uppercase tracking-wide opacity-60 mb-1">
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

                      {/* Technical Latency & Telemetry Metrics */}
                      <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-4">
                        <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-400">
                          <Cpu className="h-4 w-4 text-indigo-400" />
                          <span>Pipeline Latency Telemetry</span>
                        </div>

                        <div className="space-y-3 pt-1">
                          <div>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-slate-400">STT (Groq Whisper):</span>
                              <span className="font-mono text-slate-200 font-bold">{log.stt_latency_ms}ms</span>
                            </div>
                            <div className="w-full bg-slate-800 rounded-full h-1.5">
                              <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${Math.min(log.stt_latency_ms / 5, 100)}%` }} />
                            </div>
                          </div>

                          <div>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-slate-400">LLM Brain (Llama 3.1):</span>
                              <span className="font-mono text-slate-200 font-bold">{log.llm_latency_ms}ms</span>
                            </div>
                            <div className="w-full bg-slate-800 rounded-full h-1.5">
                              <div className="bg-indigo-500 h-1.5 rounded-full" style={{ width: `${Math.min(log.llm_latency_ms / 10, 100)}%` }} />
                            </div>
                          </div>

                          <div>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-slate-400">TTS (Edge Neural):</span>
                              <span className="font-mono text-slate-200 font-bold">{log.tts_latency_ms}ms</span>
                            </div>
                            <div className="w-full bg-slate-800 rounded-full h-1.5">
                              <div className="bg-emerald-500 h-1.5 rounded-full" style={{ width: `${Math.min(log.tts_latency_ms / 5, 100)}%` }} />
                            </div>
                          </div>

                          <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                            <span className="text-slate-400 font-medium">Total Turnaround:</span>
                            <span className="font-mono font-bold text-emerald-400 text-sm">
                              {log.stt_latency_ms + log.llm_latency_ms + log.tts_latency_ms}ms
                            </span>
                          </div>
                        </div>
                      </div>

                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="p-12 text-center text-slate-500">
              <Phone className="h-8 w-8 mx-auto mb-2 text-slate-600" />
              <p className="text-sm font-semibold">No call records found matching criteria</p>
              <p className="text-xs text-slate-600 mt-1">Initiate a Sandbox call or outbound campaign to generate logs.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
