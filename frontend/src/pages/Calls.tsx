import React, { useEffect, useState } from 'react';
import {
  PhoneCall,
  PhoneIncoming,
  PhoneOutgoing,
  Clock,
  Cpu,
  FileText,
  Smile,
  Meh,
  Frown,
  CheckCircle,
  XCircle,
  Play,
  Download,
  AlertCircle,
} from 'lucide-react';
import { api } from '../lib/api';
import type { Call } from '../types';

export const Calls: React.FC = () => {
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState<Call | null>(null);

  // Outbound call test state
  const [showOutboundModal, setShowOutboundModal] = useState(false);
  const [outboundPhone, setOutboundPhone] = useState('');
  const [outboundName, setOutboundName] = useState('');
  const [outboundGreeting, setOutboundGreeting] = useState('');
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    fetchCalls();
  }, []);

  const fetchCalls = async () => {
    try {
      const res = await api.listCalls();
      setCalls(res.items);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerOutbound = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!outboundPhone || !outboundName) return;

    setTriggering(true);
    try {
      const res = await api.triggerOutboundCall({
        to_phone: outboundPhone,
        customer_name: outboundName,
        custom_greeting: outboundGreeting || undefined,
      });
      alert(`${res.message} (SID: ${res.call_sid || 'simulated'})`);
      setShowOutboundModal(false);
      setOutboundPhone('');
      setOutboundName('');
      setOutboundGreeting('');
      await fetchCalls();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Call dispatch failed');
    } finally {
      setTriggering(false);
    }
  };

  const handleExportCsv = async () => {
    try {
      await api.exportCallsCsv();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'CSV export failed');
    }
  };

  const getSentimentIcon = (sentiment: string) => {
    if (sentiment === 'POSITIVE') return <Smile className="w-4 h-4 text-emerald-400" />;
    if (sentiment === 'NEGATIVE') return <Frown className="w-4 h-4 text-red-400" />;
    return <Meh className="w-4 h-4 text-slate-400" />;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-2">
            Call Logs & Telemetry <PhoneCall className="w-5 h-5 text-blue-400" />
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time telephony recordings, latency telemetry, transcripts, and customer sentiment analytics.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCsv}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer"
          >
            <Download className="w-4 h-4" /> Export CSV
          </button>
          <button
            onClick={() => setShowOutboundModal(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer shadow-lg shadow-blue-600/25"
          >
            <PhoneOutgoing className="w-4 h-4" /> Place Outbound Call
          </button>
        </div>
      </div>

      {/* Calls Table */}
      <div className="glass rounded-xl border border-slate-800 shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="text-sm font-bold text-white">Telephony History</h2>
          <span className="text-xs text-slate-400">{calls.length} Total Calls</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/60 text-slate-400 border-b border-slate-800 uppercase font-semibold text-[10px] tracking-wider">
              <tr>
                <th className="px-6 py-3">Direction</th>
                <th className="px-6 py-3">Caller Phone</th>
                <th className="px-6 py-3">Duration</th>
                <th className="px-6 py-3">Latency (STT/LLM/TTS)</th>
                <th className="px-6 py-3">Sentiment</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Transcript</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                    Loading call telemetry...
                  </td>
                </tr>
              ) : calls.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                    No calls recorded yet. Make a call in the Sandbox or place an Outbound call.
                  </td>
                </tr>
              ) : (
                calls.map((call) => (
                  <tr key={call.id} className="hover:bg-slate-900/40 transition">
                    <td className="px-6 py-4 font-semibold text-white flex items-center gap-2">
                      {call.direction === 'INBOUND' ? (
                        <PhoneIncoming className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <PhoneOutgoing className="w-4 h-4 text-blue-400" />
                      )}
                      <span>{call.direction}</span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-mono text-slate-200">{call.caller_phone}</div>
                      <div className="font-mono text-[10px] text-slate-400">
                        {new Date(call.started_at || call.created_at).toLocaleString()}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-slate-300 font-mono">
                      {Math.floor(call.duration_seconds / 60)}m {call.duration_seconds % 60}s
                    </td>
                    <td className="px-6 py-4 text-slate-300 font-mono text-[11px]">
                      {call.stt_latency_ms ?? 0}ms / {call.llm_latency_ms ?? 0}ms / {call.tts_latency_ms ?? 0}ms
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1.5 text-xs text-slate-300">
                        {getSentimentIcon(call.sentiment)}
                        <span className="capitalize text-[11px]">{call.sentiment.toLowerCase()}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          call.status === 'COMPLETED'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                        }`}
                      >
                        {call.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => setSelectedCall(call)}
                        className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold transition cursor-pointer"
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Transcript Drawer / Modal */}
      {selectedCall && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass rounded-2xl p-6 border border-slate-800 max-w-xl w-full shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-base font-bold text-white">Call Conversation Transcript</h2>
                <p className="text-xs text-slate-400 font-mono">
                  {selectedCall.caller_phone} • {new Date(selectedCall.started_at || selectedCall.created_at).toLocaleString()} • $
                  {(selectedCall.cost_cents / 100).toFixed(2)}
                </p>
              </div>
              <button
                onClick={() => setSelectedCall(null)}
                className="text-slate-400 hover:text-white text-xs font-semibold px-2 py-1 bg-slate-800 rounded cursor-pointer"
              >
                Close
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 p-3 bg-slate-900/50 rounded-xl">
              {Array.isArray(selectedCall.transcript) && selectedCall.transcript.length > 0 ? (
                selectedCall.transcript.map((turn, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-xl text-xs ${
                      turn.role === 'user'
                        ? 'bg-blue-600/15 border border-blue-500/30 text-blue-100 ml-6'
                        : 'bg-slate-800/80 border border-slate-700 text-slate-200 mr-6'
                    }`}
                  >
                    <span className="block text-[10px] font-bold uppercase tracking-wider opacity-60 mb-1">
                      {turn.role === 'user' ? 'Caller' : 'Voice AI'}
                    </span>
                    <p className="leading-relaxed">{turn.content}</p>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500 italic text-center py-6">
                  No transcript turns recorded for this call.
                </p>
              )}
            </div>

            {selectedCall.notes && (
              <div className="p-3 bg-blue-950/20 border border-blue-500/20 rounded-xl text-xs space-y-1">
                <span className="font-bold text-blue-300">AI Call Notes ({selectedCall.intent || 'Inquiry'}):</span>
                <p className="text-slate-300 text-[11px]">{selectedCall.notes}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Outbound Call Modal */}
      {showOutboundModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass rounded-2xl p-6 border border-slate-800 max-w-md w-full shadow-2xl space-y-4">
            <h2 className="text-base font-bold text-white">Dispatch Outbound Call (VoBiz)</h2>
            <form onSubmit={handleTriggerOutbound} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Customer Name</label>
                <input
                  type="text"
                  required
                  value={outboundName}
                  onChange={(e) => setOutboundName(e.target.value)}
                  placeholder="e.g. Vikram Malhotra"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Phone Number (E.164)</label>
                <input
                  type="tel"
                  required
                  value={outboundPhone}
                  onChange={(e) => setOutboundPhone(e.target.value)}
                  placeholder="+919876543210"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Custom Opening Phrase (Optional)</label>
                <input
                  type="text"
                  value={outboundGreeting}
                  onChange={(e) => setOutboundGreeting(e.target.value)}
                  placeholder="Hello! Calling to confirm your appointment tomorrow."
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOutboundModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={triggering}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-600/25"
                >
                  {triggering ? 'Dialing VoBiz...' : 'Initiate Call'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
