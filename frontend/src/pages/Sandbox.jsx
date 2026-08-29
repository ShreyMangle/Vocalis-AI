import { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Square, 
  Mic, 
  MicOff, 
  AlertCircle, 
  Volume2, 
  User, 
  Cpu, 
  Download, 
  Activity, 
  Sparkles,
  Waves
} from 'lucide-react';

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
  const [recordedAudioUrl, setRecordedAudioUrl] = useState(null);
  const [audioLevel, setAudioLevel] = useState(0);
  
  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micStreamRef = useRef(null);
  const processorRef = useRef(null);
  const analyserRef = useRef(null);
  const activeSourceNodeRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);
  const decodedQueueRef = useRef([]);
  const isPlayingMp3Ref = useRef(false);
  const mp3AccumulatorRef = useRef(new Uint8Array(0));
  const canvasRef = useRef(null);
  const animationFrameRef = useRef(null);
  const recordedChunksRef = useRef([]);

  useEffect(() => {
    fetchAppointments();
    return () => {
      disconnectCall();
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
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

    setLogs([{ role: 'system', text: `Initiating voice call session for ${appt.customer_name}...`, time: new Date().toLocaleTimeString() }]);
    setConnected(true);
    setAudioLatency('Initializing...');
    setRecordedAudioUrl(null);
    recordedChunksRef.current = [];

    const dummyCallId = 'call_sim_' + Math.random().toString(36).substring(2, 9);
    setCallId(dummyCallId);

    try {
      const ws = new WebSocket(`ws://localhost:5000/twilio-stream?appointmentId=${selectedApptId}&callId=${dummyCallId}&sandbox=true`);
      wsRef.current = ws;

      ws.onopen = () => {
        setLogs(prev => [...prev, { role: 'system', text: 'Bidirectional audio channel established. AI agent is speaking greeting...', time: new Date().toLocaleTimeString() }]);
        if (!textMode) {
          startMicRecording(ws);
        }
      };

      ws.onmessage = async (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.event === 'sandbox_speak_text') {
          setLogs(prev => [...prev, { role: 'ai', text: msg.text, time: new Date().toLocaleTimeString() }]);
        } else if (msg.event === 'sandbox_audio_mp3') {
          playIncomingMp3Chunk(msg.payload);
        } else if (msg.event === 'sandbox_audio') {
          playIncomingAudioChunk(msg.payload);
        } else if (msg.event === 'sandbox_clear') {
          audioQueueRef.current = [];
          isPlayingRef.current = false;
          decodedQueueRef.current = [];
          isPlayingMp3Ref.current = false;
          mp3AccumulatorRef.current = new Uint8Array(0);
          if (activeSourceNodeRef.current) {
            try { activeSourceNodeRef.current.stop(); } catch {}
          }
          setLogs(prev => [...prev, { role: 'system', text: 'Voice interruption detected: audio queue cleared.', time: new Date().toLocaleTimeString() }]);
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
        finalizeRecording();
        disconnectCall();
      };
    } catch (err) {
      console.error(err);
      setConnected(false);
    }
  };

  const finalizeRecording = () => {
    if (recordedChunksRef.current.length > 0) {
      const blob = new Blob(recordedChunksRef.current, { type: 'audio/webm' });
      const url = URL.createObjectURL(blob);
      setRecordedAudioUrl(url);
    }
  };

  const disconnectCall = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
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
    setAudioLevel(0);
  };

  const startMicRecording = async (ws) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      micStreamRef.current = stream;

      // Track media recorder for call playback download
      try {
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            recordedChunksRef.current.push(e.data);
          }
        };
        mediaRecorder.start(250);
      } catch {}

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioContextClass();
      audioCtxRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 64;
      analyserRef.current = analyser;
      source.connect(analyser);

      // Start oscilloscope loop
      startWaveformVisualizer();

      // ScriptProcessor to downsample to 16kHz PCM
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      const sampleRate = audioCtx.sampleRate;
      const targetSampleRate = 16000;
      const ratio = sampleRate / targetSampleRate;

      processor.onaudioprocess = (e) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;

        const inputData = e.inputBuffer.getChannelData(0);
        
        // Calculate RMS Level for VAD meter
        let sum = 0;
        for (let i = 0; i < inputData.length; i++) {
          sum += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sum / inputData.length);
        setAudioLevel(Math.min(rms * 400, 100));

        // Downsample to 16kHz
        const outputLength = Math.floor(inputData.length / ratio);
        const outputData = new Int16Array(outputLength);

        for (let i = 0; i < outputLength; i++) {
          const sampleIndex = Math.floor(i * ratio);
          let s = inputData[sampleIndex];
          s = Math.max(-1, Math.min(1, s));
          outputData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // Convert Int16Array to Base64
        const uint8 = new Uint8Array(outputData.buffer);
        let binary = '';
        const len = uint8.byteLength;
        for (let i = 0; i < len; i++) {
          binary += String.fromCharCode(uint8[i]);
        }
        const base64Data = btoa(binary);

        ws.send(JSON.stringify({
          event: 'media',
          media: {
            payload: base64Data
          }
        }));
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);
      setMicActive(true);
    } catch (err) {
      console.error('Microphone Access Error:', err);
      setLogs(prev => [...prev, { role: 'system', text: `Microphone permission denied: ${err.message}`, time: new Date().toLocaleTimeString() }]);
      setMicActive(false);
    }
  };

  const startWaveformVisualizer = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const analyser = analyserRef.current;

    const render = () => {
      animationFrameRef.current = requestAnimationFrame(render);
      if (!analyser) return;

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      analyser.getByteFrequencyData(dataArray);

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const barWidth = (canvas.width / bufferLength) * 2;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * canvas.height;

        // Gradient neon color
        const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
        gradient.addColorStop(0, '#3b82f6');
        gradient.addColorStop(0.5, '#6366f1');
        gradient.addColorStop(1, '#10b981');

        ctx.fillStyle = gradient;
        ctx.fillRect(x, canvas.height - barHeight, barWidth - 2, barHeight);
        x += barWidth;
      }
    };

    render();
  };

  // Decode MP3 audio from Edge TTS directly on client
  const playIncomingMp3Chunk = async (base64Mp3) => {
    try {
      const binaryString = atob(base64Mp3);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioCtxRef.current = new AudioContextClass();
      }
      const audioCtx = audioCtxRef.current;

      const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer.slice(0));
      decodedQueueRef.current.push(audioBuffer);

      if (!isPlayingMp3Ref.current) {
        playNextMp3();
      }
    } catch (err) {
      console.error('Error decoding MP3 chunk:', err);
    }
  };

  const playNextMp3 = () => {
    if (decodedQueueRef.current.length === 0) {
      isPlayingMp3Ref.current = false;
      return;
    }

    isPlayingMp3Ref.current = true;
    const audioBuffer = decodedQueueRef.current.shift();
    const audioCtx = audioCtxRef.current;

    if (!audioCtx || audioCtx.state === 'closed') return;

    const source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioCtx.destination);
    activeSourceNodeRef.current = source;

    source.onended = () => {
      playNextMp3();
    };

    source.start(0);
  };

  const playIncomingAudioChunk = (base64Payload) => {
    const binary = atob(base64Payload);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

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

    if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      audioCtxRef.current = new AudioContextClass({ sampleRate: 16000 });
    }

    const audioCtx = audioCtxRef.current;
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
        <h1 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
          Live Voice Sandbox Simulator <Waves className="h-6 w-6 text-blue-400" />
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Simulate bidirectional phone calls directly in browser. Downsamples your microphone to 16kHz PCM, detects voice activity, and synthesizes natural neural responses in real time.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Settings Panel */}
        <div className="glass rounded-xl p-5 border border-slate-700/50 space-y-4 h-fit shadow-xl">
          <div className="bg-gradient-to-r from-blue-600/15 to-indigo-600/15 border border-blue-500/30 rounded-xl p-3.5 text-xs text-blue-300">
            <span className="font-bold flex items-center gap-1.5 mb-1 text-slate-100">
              <Sparkles className="h-4 w-4 text-yellow-400" /> Keyless Free Stack Active:
            </span>
            Runs on Groq (Llama 3.1 LLM & Whisper STT) + keyless Edge Neural TTS voice streaming.
          </div>
          
          <h3 className="text-md font-semibold text-slate-200 border-b border-slate-800 pb-2">
            Call Target Identity
          </h3>
          
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Select Appointment Slot
            </label>
            <select
              disabled={connected}
              value={selectedApptId}
              onChange={(e) => setSelectedApptId(e.target.value)}
              className="w-full px-3 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 text-sm focus:outline-none focus:border-blue-500"
            >
              {appointments.length > 0 ? (
                appointments.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.customer_name} ({a.status}) — {new Date(a.scheduled_at).toLocaleDateString()}
                  </option>
                ))
              ) : (
                <option value="">No Appointments Available</option>
              )}
            </select>
            <p className="text-[10px] text-slate-500 mt-1">Agent will confirm or reschedule this customer booking.</p>
          </div>

          <div className="space-y-3 pt-2 border-t border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300">Text Mode (No Mic)</span>
              <button
                disabled={connected}
                onClick={() => setTextMode(!textMode)}
                className={`w-12 h-6 rounded-full p-1 transition-all ${textMode ? 'bg-blue-600' : 'bg-slate-700'} relative cursor-pointer`}
              >
                <div className={`w-4 h-4 rounded-full bg-white transition-all transform ${textMode ? 'translate-x-6' : 'translate-x-0'}`} />
              </button>
            </div>
            <p className="text-[10px] text-slate-500">Enable text keyboard inputs instead of browser microphone.</p>
          </div>

          {/* VAD Level Meter */}
          {connected && !textMode && (
            <div className="pt-2">
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Mic Input Volume:</span>
                <span className="font-mono text-emerald-400">{Math.round(audioLevel)}%</span>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
                <div 
                  className="h-2 bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-400 transition-all duration-75"
                  style={{ width: `${audioLevel}%` }}
                />
              </div>
            </div>
          )}

          {/* Call Recording Download Button */}
          {recordedAudioUrl && (
            <div className="pt-2">
              <a
                href={recordedAudioUrl}
                download={`vocalis_call_${callId}.webm`}
                className="w-full py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition"
              >
                <Download className="h-3.5 w-3.5 text-blue-400" /> Download Session Recording
              </a>
            </div>
          )}

          <div className="pt-4 border-t border-slate-800">
            {!connected ? (
              <button
                onClick={connectCall}
                className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl shadow-lg hover:shadow-emerald-500/20 transition flex items-center justify-center gap-2 text-sm cursor-pointer"
              >
                <Play className="h-4.5 w-4.5" /> Start Simulated Call
              </button>
            ) : (
              <button
                onClick={disconnectCall}
                className="w-full py-3 bg-red-600 hover:bg-red-500 text-white font-semibold rounded-xl shadow-lg hover:shadow-red-500/20 transition flex items-center justify-center gap-2 text-sm cursor-pointer"
              >
                <Square className="h-4.5 w-4.5" /> Hang Up Call
              </button>
            )}
          </div>
        </div>

        {/* Live Call Console */}
        <div className="glass rounded-xl border border-slate-700/50 flex flex-col h-[560px] md:col-span-2 shadow-xl overflow-hidden">
          {/* Header */}
          <div className="p-4 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-emerald-500 animate-pulse shadow-lg shadow-emerald-500/50' : 'bg-slate-600'}`} />
              <span className="text-sm font-semibold text-slate-200">
                {connected ? 'Call Connected & Streaming' : 'Ready to Connect'}
              </span>
              {connected && (
                <span className="text-xs text-slate-500 font-mono">({callId})</span>
              )}
            </div>
            {connected && (
              <div className="flex items-center gap-3 text-xs">
                <span className="flex items-center gap-1 text-slate-400">
                  <Volume2 className="h-3.5 w-3.5 text-blue-400" /> Audio On
                </span>
                <span className="flex items-center gap-1">
                  {micActive ? (
                    <span className="flex items-center gap-1 text-emerald-400 font-medium">
                      <Mic className="h-3.5 w-3.5" /> Mic Live
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-red-400">
                      <MicOff className="h-3.5 w-3.5" /> Muted
                    </span>
                  )}
                </span>
              </div>
            )}
          </div>

          {/* Oscilloscope Waveform Canvas */}
          {connected && !textMode && (
            <div className="h-16 bg-slate-950/80 border-b border-slate-800/80 flex items-center justify-center px-4 relative overflow-hidden">
              <canvas ref={canvasRef} width={500} height={50} className="w-full h-12" />
              <span className="absolute bottom-1 right-3 text-[9px] text-slate-500 font-mono">
                REALTIME SPECTROGRAM
              </span>
            </div>
          )}

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
                          ? 'bg-slate-800/90 text-slate-200 border border-slate-700/50 rounded-tl-none mr-auto'
                          : 'bg-blue-600/20 text-blue-100 border border-blue-500/30 rounded-tr-none ml-auto'
                      }`}
                    >
                      <span className="text-[10px] font-bold uppercase tracking-wider opacity-60 flex items-center gap-1.5 mb-1">
                        {log.role === 'ai' ? (
                          <>
                            <Cpu className="h-3 w-3 text-indigo-400" />
                            <span>AI Virtual Assistant</span>
                          </>
                        ) : (
                          <>
                            <User className="h-3 w-3 text-blue-400" />
                            <span>Customer</span>
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
              <div className="flex flex-col items-center justify-center h-full text-slate-500 space-y-2 py-12">
                <AlertCircle className="h-8 w-8 opacity-40 text-slate-600" />
                <p className="text-xs">No active simulated call session. Click 'Start Simulated Call' to begin.</p>
              </div>
            )}
          </div>

          {/* Input Panel for Text Mode */}
          {connected && textMode && (
            <form onSubmit={sendTextMessage} className="p-4 border-t border-slate-800 bg-slate-900/40 flex gap-2">
              <input
                type="text"
                value={textMsg}
                onChange={(e) => setTextMsg(e.target.value)}
                placeholder="Type customer spoken response (e.g. 'Yes please confirm my appointment')..."
                className="flex-1 px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              />
              <button
                type="submit"
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition cursor-pointer"
              >
                Send
              </button>
            </form>
          )}

          {connected && !textMode && (
            <div className="p-3.5 border-t border-slate-800 bg-slate-900/30 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
              <Mic className="h-4 w-4 text-emerald-400 animate-pulse" />
              <span>Microphone listening. Speak naturally to confirm, reschedule, or cancel your appointment.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
