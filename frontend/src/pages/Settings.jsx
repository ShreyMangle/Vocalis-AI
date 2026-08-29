import { useState, useEffect } from 'react';
import { 
  Bot, 
  Volume2, 
  MessageSquare, 
  Link, 
  Save, 
  CheckCircle, 
  AlertCircle, 
  Sparkles, 
  Sliders, 
  Mic, 
  ShieldCheck, 
  Play, 
  Square,
  Layers
} from 'lucide-react';

const VOICE_OPTIONS = [
  { id: 'en-US-AriaNeural', name: 'Aria (US Female)', desc: 'Warm, professional, empathetic, and crystal clear', gender: 'Female' },
  { id: 'en-US-GuyNeural', name: 'Guy (US Male)', desc: 'Calm, authoritative, and welcoming', gender: 'Male' },
  { id: 'en-GB-SoniaNeural', name: 'Sonia (UK Female)', desc: 'Polished British tone, courteous and refined', gender: 'Female' },
  { id: 'en-US-JennyNeural', name: 'Jenny (US Female)', desc: 'Upbeat, conversational, and energetic', gender: 'Female' },
];

export default function Settings() {
  const [agentName, setAgentName] = useState('Sarah');
  const [voiceId, setVoiceId] = useState('en-US-AriaNeural');
  const [customGreeting, setCustomGreeting] = useState('');
  const [businessFaqs, setBusinessFaqs] = useState('');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [smsEnabled, setSmsEnabled] = useState(1);
  const [speechSpeed, setSpeechSpeed] = useState('+0%');
  const [vadSensitivity, setVadSensitivity] = useState('normal');
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [previewingVoice, setPreviewingVoice] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/settings', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (res.ok) {
        setAgentName(data.agent_name || 'Sarah');
        setVoiceId(data.voice_id || 'en-US-AriaNeural');
        setCustomGreeting(data.custom_greeting || '');
        setBusinessFaqs(data.business_faqs || '');
        setWebhookUrl(data.webhook_url || '');
        setSmsEnabled(data.sms_enabled ?? 1);
        setSpeechSpeed(data.speech_speed || '+0%');
        setVadSensitivity(data.vad_sensitivity || 'normal');
      }
    } catch (err) {
      console.error('Error loading settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSuccessMsg('');
    setErrorMsg('');

    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          agent_name: agentName,
          voice_id: voiceId,
          custom_greeting: customGreeting,
          business_faqs: businessFaqs,
          webhook_url: webhookUrl,
          sms_enabled: smsEnabled,
          speech_speed: speechSpeed,
          vad_sensitivity: vadSensitivity
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to update settings');

      setSuccessMsg('Agent configuration and acoustic tuning saved successfully!');
      setTimeout(() => setSuccessMsg(''), 4000);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setSaving(false);
    }
  };

  const testVoiceSample = () => {
    if (previewingVoice) {
      window.speechSynthesis.cancel();
      setPreviewingVoice(false);
      return;
    }

    if (!('speechSynthesis' in window)) {
      alert('Speech synthesis preview not supported on this browser.');
      return;
    }

    const utterance = new SpeechSynthesisUtterance(
      `Hello! I'm ${agentName}, your AI voice assistant. I can confirm, reschedule, or answer questions regarding your appointment.`
    );
    
    // Adjust browser pitch/rate approximation for instant feedback
    if (speechSpeed === '-10%') utterance.rate = 0.9;
    if (speechSpeed === '+10%') utterance.rate = 1.1;
    if (speechSpeed === '+20%') utterance.rate = 1.25;

    utterance.onend = () => setPreviewingVoice(false);
    utterance.onerror = () => setPreviewingVoice(false);

    setPreviewingVoice(true);
    window.speechSynthesis.speak(utterance);
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-slate-400 flex items-center justify-center gap-2">
        <Sparkles className="h-5 w-5 animate-spin text-blue-500" /> Loading Settings...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
          Voice Agent Tuning & Persona <Sparkles className="h-5 w-5 text-yellow-400 fill-yellow-400" />
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Fine-tune agent persona, acoustic speech pacing, interruption sensitivity, knowledge base FAQs, and webhook triggers.
        </p>
      </div>

      {successMsg && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-300 text-sm flex items-center gap-2">
          <CheckCircle className="h-5 w-5" /> {successMsg}
        </div>
      )}

      {errorMsg && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-300 text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4" /> {errorMsg}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* 1. Agent Persona & Identity */}
        <div className="glass rounded-xl p-6 border border-slate-700/50 space-y-4">
          <div className="flex items-center gap-2 text-slate-200 font-semibold border-b border-slate-800 pb-3">
            <Bot className="h-5 w-5 text-blue-400" />
            <span>Agent Persona & Greetings</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                Virtual Assistant Name
              </label>
              <input
                type="text"
                required
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                placeholder="e.g. Sarah, Clara, Alex"
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                Automated SMS Notifications
              </label>
              <button
                type="button"
                onClick={() => setSmsEnabled(smsEnabled ? 0 : 1)}
                className={`w-full py-2.5 px-4 rounded-lg border text-sm font-semibold flex items-center justify-between transition cursor-pointer ${
                  smsEnabled
                    ? 'bg-blue-600/20 border-blue-500/40 text-blue-300'
                    : 'bg-slate-900 border-slate-700 text-slate-400'
                }`}
              >
                <span>Post-Call SMS Confirmation</span>
                <span className={`px-2 py-0.5 rounded text-xs ${smsEnabled ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-300'}`}>
                  {smsEnabled ? 'Enabled' : 'Disabled'}
                </span>
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Custom Opening Greeting Template
            </label>
            <textarea
              rows={2}
              value={customGreeting}
              onChange={(e) => setCustomGreeting(e.target.value)}
              placeholder="Hi {customer_name}, this is {agent_name} from {business_name}. I'm following up to confirm your booking for {appointment_time}. Will you make it?"
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 text-sm focus:outline-none focus:border-blue-500 font-mono text-xs"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Placeholders: <code className="text-blue-400">{'{customer_name}'}</code>, <code className="text-blue-400">{'{business_name}'}</code>, <code className="text-blue-400">{'{appointment_time}'}</code>, <code className="text-blue-400">{'{agent_name}'}</code>.
            </p>
          </div>
        </div>

        {/* 2. Voice Selection Grid & Speech Tuning */}
        <div className="glass rounded-xl p-6 border border-slate-700/50 space-y-5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2 text-slate-200 font-semibold">
              <Volume2 className="h-5 w-5 text-indigo-400" />
              <span>Voice Profile (Microsoft Edge Neural Engine)</span>
            </div>
            <button
              type="button"
              onClick={testVoiceSample}
              className="px-3 py-1 bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
            >
              {previewingVoice ? <Square className="h-3.5 w-3.5 text-red-400" /> : <Play className="h-3.5 w-3.5 text-indigo-400" />}
              {previewingVoice ? 'Stop Preview' : 'Play Voice Preview'}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {VOICE_OPTIONS.map((v) => (
              <div
                key={v.id}
                onClick={() => setVoiceId(v.id)}
                className={`p-4 rounded-xl border cursor-pointer transition flex flex-col justify-between ${
                  voiceId === v.id
                    ? 'bg-indigo-600/15 border-indigo-500 text-slate-100 shadow-lg shadow-indigo-500/10'
                    : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-sm text-slate-200">{v.name}</span>
                  <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                    {v.gender}
                  </span>
                </div>
                <p className="text-xs text-slate-400">{v.desc}</p>
              </div>
            ))}
          </div>

          {/* Acoustic Speed & VAD Controls */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-slate-800">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                <Sliders className="h-3.5 w-3.5 text-blue-400" /> Speech Rate & Pacing
              </label>
              <select
                value={speechSpeed}
                onChange={(e) => setSpeechSpeed(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="-10%">-10% (Slow & Articulate)</option>
                <option value="+0%">+0% (Natural Speech Default)</option>
                <option value="+10%">+10% (Brisk & Responsive)</option>
                <option value="+20%">+20% (Fast Pace)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                <Mic className="h-3.5 w-3.5 text-emerald-400" /> VAD Interruption Sensitivity
              </label>
              <select
                value={vadSensitivity}
                onChange={(e) => setVadSensitivity(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="high">High (Sub-600ms Interruption & Barge-in)</option>
                <option value="normal">Normal (Standard 800ms Silence Pause)</option>
                <option value="low">Low (Tolerant of Background Noise)</option>
              </select>
            </div>
          </div>
        </div>

        {/* 3. Multi-LLM Provider Failover Architecture */}
        <div className="glass rounded-xl p-6 border border-slate-700/50 space-y-4">
          <div className="flex items-center gap-2 text-slate-200 font-semibold border-b border-slate-800 pb-3">
            <Layers className="h-5 w-5 text-yellow-400" />
            <span>High-Availability LLM Provider Fallback Chain</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-slate-900/90 border border-blue-500/40 text-slate-200">
              <span className="font-bold text-blue-400 block mb-0.5">1. Primary Brain</span>
              <span className="font-semibold block">Groq Llama 3.1-70B</span>
              <span className="text-[10px] text-slate-500">Sub-150ms function calls</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-700 text-slate-300">
              <span className="font-bold text-indigo-400 block mb-0.5">2. Secondary</span>
              <span className="font-semibold block">Google Gemini 1.5 Flash</span>
              <span className="text-[10px] text-slate-500">Fast token generation</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-700 text-slate-300">
              <span className="font-bold text-emerald-400 block mb-0.5">3. Fallback Tier</span>
              <span className="font-semibold block">Anthropic Claude 3.5</span>
              <span className="text-[10px] text-slate-500">Precision reasoning</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-700 text-slate-300">
              <span className="font-bold text-amber-400 block mb-0.5">4. Safe Sandbox</span>
              <span className="font-semibold block">Local Rule Engine</span>
              <span className="text-[10px] text-slate-500">Zero downtime guarantee</span>
            </div>
          </div>
        </div>

        {/* 4. Business Knowledge Base & FAQs */}
        <div className="glass rounded-xl p-6 border border-slate-700/50 space-y-4">
          <div className="flex items-center gap-2 text-slate-200 font-semibold border-b border-slate-800 pb-3">
            <MessageSquare className="h-5 w-5 text-emerald-400" />
            <span>Business Knowledge Base & FAQ Context</span>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Operating Hours, Address, Services, & Cancellation Policy
            </label>
            <textarea
              rows={4}
              value={businessFaqs}
              onChange={(e) => setBusinessFaqs(e.target.value)}
              placeholder="e.g. We are located at 123 Main Street. Parking is free behind the building. Cancellations require 24 hours notice. Services include teeth cleaning ($100) and whitening ($250)."
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 text-sm focus:outline-none focus:border-blue-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              The AI agent uses this context to answer customer questions during confirmation calls before returning to appointment verification.
            </p>
          </div>
        </div>

        {/* 5. Outbound Webhook Integration */}
        <div className="glass rounded-xl p-6 border border-slate-700/50 space-y-4">
          <div className="flex items-center gap-2 text-slate-200 font-semibold border-b border-slate-800 pb-3">
            <Link className="h-5 w-5 text-purple-400" />
            <span>Outbound Call Webhooks (Zapier, Make.com, n8n, CRM)</span>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Webhook Endpoint URL (HMAC SHA-256 Signed)
            </label>
            <input
              type="url"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://hooks.zapier.com/hooks/catch/12345/abcde"
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 text-sm focus:outline-none focus:border-blue-500 font-mono text-xs"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Upon call completion, Vocalis AI sends an HTTP POST payload containing call outcomes, transcripts, and latency metrics to this URL.
            </p>
          </div>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="w-full py-3.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl shadow-lg hover:shadow-blue-500/20 transition flex items-center justify-center gap-2 text-sm cursor-pointer disabled:opacity-50"
        >
          <Save className="h-4.5 w-4.5" />
          {saving ? 'Saving Settings...' : 'Save Agent Settings'}
        </button>
      </form>
    </div>
  );
}
