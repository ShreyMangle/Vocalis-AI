import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Square,
  Mic,
  MicOff,
  AlertCircle,
  Volume2,
  User,
  Cpu,
  Radio,
  Sparkles,
  Zap,
  ArrowRight,
  Database,
  CalendarCheck,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../lib/api';

interface LogMessage {
  id: string;
  role: 'system' | 'ai' | 'user' | 'tool';
  text: string;
  time: string;
  metadata?: Record<string, unknown>;
}

export const Sandbox: React.FC = () => {
  const [connected, setConnected] = useState(false);
  const [micActive, setMicActive] = useState(false);
  const [textMode, setTextMode] = useState(true);
  const [inputText, setInputText] = useState('');
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [latency, setLatency] = useState<string>('0ms');
  const [audioLevel, setAudioLevel] = useState<number>(0);

  const wsRef = useRef<WebSocket | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      disconnect();
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, []);

  const addLog = (role: LogMessage['role'], text: string, metadata?: Record<string, unknown>) => {
    setLogs((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substring(7),
        role,
        text,
        time: new Date().toLocaleTimeString(),
        metadata,
      },
    ]);
  };

  const connect = () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const wsUrl = apiUrl.replace(/^http/, 'ws') + '/api/v1/telephony/sandbox';

    addLog('system', 'Connecting to real-time voice pipeline WebSocket...');
    setConnected(true);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        addLog('system', 'VoBiz 8kHz PCMU voice tunnel established. Waiting for AI greeting...');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.event === 'sandbox_audio') {
            // Received audio chunk
            addLog('ai', 'AI is speaking (G.711 mu-law base64 audio frame streamed)');
          } else if (data.event === 'sandbox_speak_text') {
            addLog('ai', data.text);
          } else if (data.event === 'tool_call') {
            addLog('tool', `Tool Executed: ${data.name}`, data.args);
          } else if (data.event === 'clear') {
            addLog('system', 'Barge-in triggered: Caller interrupted AI speech. Audio buffer cleared.');
          }
        } catch {
          // non-json
        }
      };

      ws.onerror = (err) => {
        console.error('WS error', err);
        addLog('system', 'Error in WebSocket stream tunnel.');
      };

      ws.onclose = () => {
        addLog('system', 'Sandbox session disconnected.');
        setConnected(false);
        setMicActive(false);
      };
    } catch (err) {
      console.error(err);
      setConnected(false);
    }
  };

  const disconnect = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
    setMicActive(false);
  };

  const handleSendText = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    addLog('user', inputText);

    const payload = {
      event: 'sandbox_text',
      text: inputText,
    };
    wsRef.current.send(JSON.stringify(payload));
    setInputText('');
  };

  const triggerBargeIn = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    const payload = {
      event: 'media',
      media: {
        payload: '/////////w==', // high energy test frame
      },
    };
    wsRef.current.send(JSON.stringify(payload));
    addLog('system', 'Manual barge-in signal dispatched to pipeline.');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-2">
            Interactive Voice Sandbox <Radio className="w-5 h-5 text-blue-400 animate-pulse" />
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Test the live VoBiz/Twilio bidirectional audio stream, VAD barge-in interruption, and AI tool calling in real time.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {!connected ? (
            <button
              onClick={connect}
              className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-2 shadow-lg shadow-blue-600/30 cursor-pointer"
            >
              <Play className="w-3.5 h-3.5 fill-white" /> Start Sandbox Session
            </button>
          ) : (
            <>
              <button
                onClick={triggerBargeIn}
                className="px-3.5 py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-400 border border-amber-500/30 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer"
              >
                <Zap className="w-3.5 h-3.5" /> Simulate Barge-In
              </button>
              <button
                onClick={disconnect}
                className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer"
              >
                <Square className="w-3.5 h-3.5 fill-red-400" /> Disconnect
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Console Box */}
      <div className="glass rounded-2xl border border-slate-800 shadow-2xl overflow-hidden flex flex-col h-[640px]">
        {/* Stream Status Bar */}
        <div className="h-12 bg-slate-900/80 px-6 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <span
                className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`}
              />
              {connected ? 'WebSocket Stream Connected' : 'Stream Offline'}
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-[11px] text-slate-400 font-mono">Carrier: VoBiz India 8kHz PCMU</span>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <button
              onClick={() => setTextMode(!textMode)}
              className="text-[11px] font-semibold text-blue-400 hover:text-blue-300 transition"
            >
              Mode: {textMode ? 'Text Simulation' : 'Audio Stream'}
            </button>
          </div>
        </div>

        {/* Conversation Logs View */}
        <div className="flex-1 p-6 overflow-y-auto space-y-4 bg-slate-950/40">
          {logs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-3">
              <Radio className="w-10 h-10 opacity-30 text-blue-400" />
              <p className="text-xs">
                No active call simulation. Click <strong>"Start Sandbox Session"</strong> to begin.
              </p>
            </div>
          ) : (
            logs.map((log) => {
              if (log.role === 'system') {
                return (
                  <div key={log.id} className="text-center py-1">
                    <span className="text-[11px] text-slate-400 italic bg-slate-900/50 px-3 py-1 rounded-full border border-slate-800">
                      {log.text}
                    </span>
                  </div>
                );
              }

              if (log.role === 'tool') {
                return (
                  <div key={log.id} className="mx-auto max-w-lg bg-indigo-950/30 border border-indigo-500/30 rounded-xl p-3 text-xs text-indigo-300 space-y-1">
                    <div className="flex items-center gap-2 font-bold text-indigo-200">
                      <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                      <span>{log.text}</span>
                    </div>
                    {log.metadata && (
                      <pre className="text-[10px] text-slate-400 font-mono bg-slate-900/80 p-2 rounded overflow-auto">
                        {JSON.stringify(log.metadata, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              }

              const isUser = log.role === 'user';
              return (
                <div key={log.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm ${
                      isUser
                        ? 'bg-blue-600/20 border border-blue-500/30 text-blue-100 rounded-tr-none'
                        : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider opacity-60 mb-1">
                      {isUser ? (
                        <>
                          <User className="w-3 h-3 text-blue-400" />
                          <span>Customer (Caller)</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3 h-3 text-emerald-400" />
                          <span>VoxAI Voice Agent</span>
                        </>
                      )}
                    </div>
                    <p className="leading-relaxed">{log.text}</p>
                    <span className="block text-[9px] opacity-40 text-right mt-1.5">{log.time}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Bottom Input Area */}
        {connected ? (
          <form onSubmit={handleSendText} className="p-4 border-t border-slate-800 bg-slate-900/50 flex gap-2">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Type simulated caller response (e.g. 'Can I book an appointment with Dr. Sharma tomorrow?')..."
              className="flex-1 px-4 py-2.5 bg-slate-950 border border-slate-700/80 rounded-xl text-sm text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition cursor-pointer flex items-center gap-1.5"
            >
              <span>Speak</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        ) : (
          <div className="p-4 border-t border-slate-800 bg-slate-900/30 text-center text-xs text-slate-400">
            Click "Start Sandbox Session" above to interact with Sarah (AI Receptionist).
          </div>
        )}
      </div>
    </div>
  );
};
