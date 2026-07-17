import { useState, useEffect, useRef } from 'react';
import { Play, Square, Mic, MicOff, AlertCircle, Volume2, User, Cpu } from 'lucide-react';

export default function Sandbox() {
  const [appointments, setAppointments] = useState([]);
  const [selectedApptId, setSelectedApptId] = useState('');
  const [callId, setCallId] = useState('');
  const [connected, setConnected] = useState(false);
  const [micActive, setMicActive] = useState(false);
  const [textMode, setTextMode] = useState(false);
  const [textMsg, setTextMsg] = useState('');
  const [logs, setLogs] = useState([]);
  const [audioLatency, setAudioLatency] = useState('0');
  
  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micStreamRef = useRef(null);
  const processorRef = useRef(null);
  const activeSourceNodeRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);
  const decodedQueueRef = useRef([]);
  const isPlayingMp3Ref = useRef(false);
  const mp3AccumulatorRef = useRef(new Uint8Array(0));

  useEffect(() => {
    fetchAppointments();
    return () => {
      disconnectCall();
    };
  }, []);

  const fetchAppointments = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/appointments', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setAppointments(data || []);
      if (data && data.length > 0) {
        setSelectedApptId(data[0].id);
      }
    } catch (err) {
      console.error('Error fetching appts:', err);
    }
  };

  // Web Socket Connection & Pipeline Trigger
  const connectCall = async () => {
    if (!selectedApptId) {
      alert('Please select or create a pending appointment first.');
      return;
    }

    const appt = appointments.find(a => a.id === selectedApptId);
    if (!appt) return;

    setLogs([{ role: 'system', text: `Initiating call sandbox for ${appt.customer_name}...`, time: new Date().toLocaleTimeString() }]);
    setConnected(true);
    setAudioLatency('Initializing...');

    // Generate call record
    const dummyCallId = 'call_sim_' + Math.random().toString(36).substring(2, 9);
    setCallId(dummyCallId);

    // Backend trigger calls
    try {
      const ws = new WebSocket(`ws://localhost:5000/twilio-stream?appointmentId=${selectedApptId}&callId=${dummyCallId}&sandbox=true`);
      wsRef.current = ws;

      ws.onopen = () => {
        setLogs(prev => [...prev, { role: 'system', text: 'Voice channel established. AI agent is speaking greeting...', time: new Date().toLocaleTimeString() }]);
        // Initialize mic recording if not text mode
        if (!textMode) {
          startMicRecording(ws);
        }
      };

      ws.onmessage = async (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.event === 'sandbox_speak_text') {
          // Fallback if no audio API key (mock mode)
          setLogs(prev => [...prev, { role: 'ai', text: msg.text, time: new Date().toLocaleTimeString() }]);
        } else if (msg.event === 'sandbox_audio_mp3') {
          // Play MP3 audio chunk from edge-tts
          playIncomingMp3Chunk(msg.payload);
        } else if (msg.event === 'sandbox_audio') {
          // Play PCM audio chunk from backend
          const base64Payload = msg.payload;
          playIncomingAudioChunk(base64Payload);
        } else if (msg.event === 'sandbox_clear') {
          // Interruption signal - clear client audio buffers
          audioQueueRef.current = [];
          isPlayingRef.current = false;
          decodedQueueRef.current = [];
          isPlayingMp3Ref.current = false;
          mp3AccumulatorRef.current = new Uint8Array(0);
          if (activeSourceNodeRef.current) {
            try { activeSourceNodeRef.current.stop(); } catch {}
          }
          setLogs(prev => [...prev, { role: 'system', text: 'Speech barge-in: queue cleared.', time: new Date().toLocaleTimeString() }]);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket Error:', err);
        setLogs(prev => [...prev, { role: 'system', text: 'Error in audio WebSocket tunnel.', time: new Date().toLocaleTimeString() }]);
      };

      ws.onclose = () => {
        setLogs(prev => [...prev, { role: 'system', text: 'Simulated call ended.', time: new Date().toLocaleTimeString() }]);
        setConnected(false);
        setMicActive(false);
        disconnectCall();
      };
    } catch (err) {
      console.error(err);
      setConnected(false);
    }
  };

  const disconnectCall = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    // Stop recording nodes
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach(track => track.stop());
      micStreamRef.current = null;
    }
    if (audioCtxRef.current) {
      if (audioCtxRef.current.state !== 'closed') {
        audioCtxRef.current.close();
      }
      audioCtxRef.current = null;
    }
    
    setConnected(false);
    setMicActive(false);
  };

  const startMicRecording = async (ws) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;
      setMicActive(true);

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioContextClass({ sampleRate: 16000 });
      audioCtxRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      // ScriptProcessor is deprecated but highly supported for simple downsampling/PCM formatting inline
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      source.connect(processor);
      processor.connect(audioCtx.destination);

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;

        const inputData = e.inputBuffer.getChannelData(0);
        // Convert Float32Array to 16-bit signed Int16Array PCM
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const sample = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        }

        // Base64 encode and emit
        const base64Payload = btoa(
          String.fromCharCode(...new Uint8Array(pcm16.buffer))
        );

        ws.send(JSON.stringify({
          event: 'sandbox_audio',
          payload: base64Payload
        }));
      };

    } catch (err) {
      console.error('Microphone capture failed:', err);
      setLogs(prev => [...prev, { role: 'system', text: 'Failed to access microphone. Swapping to Text Mode.', time: new Date().toLocaleTimeString() }]);
      setTextMode(true);
      setMicActive(false);
    }
  };

  const playIncomingMp3Chunk = async (base64Payload) => {
    const binary = atob(base64Payload);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    try {
      if (!audioCtxRef.current) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioCtxRef.current = new AudioContextClass();
      }
      
      const audioCtx = audioCtxRef.current;
      const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer);
      
      decodedQueueRef.current.push(audioBuffer);
      
      if (!isPlayingMp3Ref.current) {
        playNextDecodedBuffer();
      }
    } catch (err) {
      console.error('Failed to decode MP3 sentence buffer:', err);
    }
  };

  const playNextDecodedBuffer = () => {
    if (decodedQueueRef.current.length === 0) {
      isPlayingMp3Ref.current = false;
      return;
    }

    isPlayingMp3Ref.current = true;
    const buffer = decodedQueueRef.current.shift();

    if (!audioCtxRef.current) return;
    const audioCtx = audioCtxRef.current;

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);
    
    activeSourceNodeRef.current = source;
    
    source.onended = () => {
      playNextDecodedBuffer();
    };
    
    source.start(0);
  };

  const playIncomingAudioChunk = (base64Payload) => {
    // Decode base64 to binary
    const binary = atob(base64Payload);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    // Convert Int16Array back to Float32Array
    const pcm16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 32768.0;
    }

    audioQueueRef.current.push(float32);
    if (!isPlayingRef.current) {
      playNextQueuedAudio();
    }
  };

  const playNextQueuedAudio = () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      return;
    }

    isPlayingRef.current = true;
    const chunk = audioQueueRef.current.shift();

    // Boot AudioContext if not initialized
    if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      audioCtxRef.current = new AudioContextClass({ sampleRate: 16000 });
    }

    const audioCtx = audioCtxRef.current;
    
    // Create an audio buffer
    const audioBuffer = audioCtx.createBuffer(1, chunk.length, 16000);
    audioBuffer.getChannelData(0).set(chunk);

    const source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioCtx.destination);
    
    activeSourceNodeRef.current = source;
    
    source.onended = () => {
      playNextQueuedAudio();
    };

    source.start(0);
  };

  const sendTextMessage = (e) => {
    e.preventDefault();
    if (!textMsg.trim() || !wsRef.current) return;

    setLogs(prev => [...prev, { role: 'user', text: textMsg, time: new Date().toLocaleTimeString() }]);
    
    wsRef.current.send(JSON.stringify({
      event: 'sandbox_text',
      text: textMsg
    }));

    setTextMsg('');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          Voice Agent Sandbox
        </h1>
        <p className="text-slate-400 text-sm">
          Simulate an outbound voice call in real-time. This page downsamples your mic to raw PCM, streams it, and plays the AI pipeline response back.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Settings Panel */}
        <div className="glass rounded-xl p-5 border border-slate-700/50 space-y-4 h-fit">
          <div className="bg-indigo-600/10 border border-indigo-500/20 rounded-lg p-3 text-[11px] text-indigo-300">
            <span className="font-semibold block mb-1">⚡ Complete Free Stack Active:</span>
            Runs completely free using Groq (Llama 3.1 LLM & Whisper STT) + keyless Microsoft Edge Neural TTS voice.
          </div>
          
          <h3 className="text-lg font-semibold text-slate-200">Simulator Settings</h3>
          
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Select Appointment</label>
            <select
              disabled={connected}
              value={selectedApptId}
              onChange={(e) => setSelectedApptId(e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 text-sm focus:outline-none focus:border-blue-500"
            >
              {appointments.length > 0 ? (
                appointments.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.customer_name} ({a.status})
                  </option>
                ))
              ) : (
                <option value="">No Appointments Found</option>
              )}
            </select>
            <p className="text-[10px] text-slate-400 mt-1">Select the appointment identity you want the agent to use on the call.</p>
          </div>

          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300">Text Mode Fallback</span>
              <button
                disabled={connected}
                onClick={() => setTextMode(!textMode)}
                className={`w-12 h-6 rounded-full p-1 transition-all ${textMode ? 'bg-blue-600' : 'bg-slate-700'} relative cursor-pointer`}
              >
                <div className={`w-4 h-4 rounded-full bg-white transition-all transform ${textMode ? 'translate-x-6' : 'translate-x-0'}`} />
              </button>
            </div>
            <p className="text-[10px] text-slate-500">Enable text inputs instead of browser microphone recording for testing without spoken audio.</p>
          </div>

          <div className="pt-4 border-t border-slate-800">
            {!connected ? (
              <button
                onClick={connectCall}
                className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg shadow-lg hover:shadow-emerald-500/20 transition flex items-center justify-center gap-2 text-sm cursor-pointer"
              >
                <Play className="h-4.5 w-4.5" /> Start Simulated Call
              </button>
            ) : (
              <button
                onClick={disconnectCall}
                className="w-full py-3 bg-red-600 hover:bg-red-500 text-white font-semibold rounded-lg shadow-lg hover:shadow-red-500/20 transition flex items-center justify-center gap-2 text-sm cursor-pointer"
              >
                <Square className="h-4.5 w-4.5" /> Hang Up Call
              </button>
            )}
          </div>
        </div>

        {/* Live Call Console */}
        <div className="glass rounded-xl border border-slate-700/50 flex flex-col h-[500px] md:col-span-2">
          {/* Header */}
          <div className="p-4 border-b border-slate-800 bg-slate-900/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
              <span className="text-sm font-semibold text-slate-200">
                {connected ? 'Call Connected' : 'Call Status: Disconnected'}
              </span>
              {connected && (
                <span className="text-xs text-slate-500 font-mono ml-2">({callId})</span>
              )}
            </div>
            {connected && (
              <div className="flex items-center gap-4 text-xs">
                <span className="text-indigo-400 font-mono">
                  Latency: {audioLatency}
                </span>
                <span className="flex items-center gap-1 text-slate-400">
                  <Volume2 className="h-3.5 w-3.5" /> Speaker Active
                </span>
                <span className="flex items-center gap-1 text-slate-400">
                  {micActive ? (
                    <span className="flex items-center gap-1 text-emerald-400 font-medium">
                      <Mic className="h-3.5 w-3.5" /> Mic Live
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-red-400">
                      <MicOff className="h-3.5 w-3.5" /> Mic Muted
                    </span>
                  )}
                </span>
              </div>
            )}
          </div>

          {/* Transcript / Event Stream */}
          <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-slate-950/40">
            {logs.length > 0 ? (
              logs.map((log, idx) => (
                <div key={idx} className={`flex ${log.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {log.role === 'system' ? (
                    <div className="w-full text-center text-xs text-slate-500 italic py-1">
                      {log.text}
                    </div>
                  ) : (
                    <div
                      className={`flex flex-col max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                        log.role === 'ai'
                          ? 'bg-slate-800 text-slate-200 border border-slate-700/50 rounded-tl-none mr-auto'
                          : 'bg-blue-600/20 text-blue-200 border border-blue-500/20 rounded-tr-none ml-auto'
                      }`}
                    >
                      <span className="text-[10px] font-bold uppercase tracking-wider opacity-60 flex items-center gap-1.5 mb-1.5">
                        {log.role === 'ai' ? (
                          <>
                            <Cpu className="h-3 w-3 text-indigo-400" />
                            <span>AI scheduling assistant</span>
                          </>
                        ) : (
                          <>
                            <User className="h-3 w-3 text-blue-400" />
                            <span>customer</span>
                          </>
                        )}
                      </span>
                      <span>{log.text}</span>
                      <span className="text-[9px] opacity-40 text-right mt-1 block">{log.time}</span>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 space-y-2">
                <AlertCircle className="h-8 w-8 opacity-40" />
                <p className="text-xs">No active simulated call session. Select settings and click Start Call above!</p>
              </div>
            )}
          </div>

          {/* Input Panel for Text Mode */}
          {connected && textMode && (
            <form onSubmit={sendTextMessage} className="p-4 border-t border-slate-800 bg-slate-900/20 flex gap-2">
              <input
                type="text"
                value={textMsg}
                onChange={(e) => setTextMsg(e.target.value)}
                placeholder="Type customer reply here (e.g. 'Yes I can make it')..."
                className="flex-1 px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              />
              <button
                type="submit"
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold transition cursor-pointer"
              >
                Send
              </button>
            </form>
          )}

          {connected && !textMode && (
            <div className="p-4 border-t border-slate-800 bg-slate-900/10 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
              <Mic className="h-4 w-4 text-emerald-400 animate-pulse" />
              <span>Microphone streaming live to AI voice agent. Start speaking now. Speak clearly into your microphone!</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
