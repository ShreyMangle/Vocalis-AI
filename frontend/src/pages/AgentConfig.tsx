import React, { useEffect, useState } from 'react';
import {
  Bot,
  Volume2,
  PhoneForwarded,
  Save,
  Sparkles,
  Eye,
  CheckCircle,
  Cpu,
} from 'lucide-react';
import { api } from '../lib/api';
import type { AgentConfig, VoiceCatalogItem } from '../types';

export const AgentConfigPage: React.FC = () => {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [voices, setVoices] = useState<VoiceCatalogItem[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [cfg, vList] = await Promise.all([
        api.getAgentConfig(),
        api.getVoices().catch(() => []),
      ]);
      setConfig(cfg);
      setVoices(Array.isArray(vList) ? vList : []);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load agent config');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;

    setSaving(true);
    setSaveSuccess(false);
    setErrorMsg(null);
    try {
      const updated = await api.updateAgentConfig({
        name: config.name,
        role_description: config.role_description,
        greeting_message: config.greeting_message,
        fallback_message: config.fallback_message,
        system_prompt: config.system_prompt || null,
        voice_provider: config.voice_provider,
        voice_id: config.voice_id,
        speech_speed: config.speech_speed,
        llm_provider: config.llm_provider,
        llm_model: config.llm_model,
        temperature: config.temperature,
        transfer_phone_number: config.transfer_phone_number || null,
        sms_enabled: config.sms_enabled,
        is_active: config.is_active,
      });
      setConfig(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async () => {
    try {
      const res = await api.previewPrompt();
      setPreview(res.compiled_prompt);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Preview failed');
    }
  };

  const handleVoicePresetChange = (voiceId: string) => {
    if (!config) return;
    const match = voices.find((v) => v.voice_id === voiceId);
    setConfig({
      ...config,
      voice_id: voiceId,
      voice_provider: (match?.provider as AgentConfig['voice_provider']) || config.voice_provider,
    });
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!config) {
    return (
      <div className="glass rounded-xl p-6 border border-red-500/30 text-xs text-red-400">
        {errorMsg || 'Agent configuration not found for this organization.'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-2">
            Voice Agent Configuration <Bot className="w-5 h-5 text-blue-400" />
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Configure conversational prompt personality, free/cloud neural speech synthesis, LLM model, and escalation rules.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer shadow-lg shadow-blue-600/25 disabled:opacity-50"
        >
          {saving ? (
            'Saving Changes...'
          ) : saveSuccess ? (
            <>
              <CheckCircle className="w-4 h-4 text-emerald-300" /> Saved!
            </>
          ) : (
            <>
              <Save className="w-4 h-4" /> Save Agent Config
            </>
          )}
        </button>
      </div>

      {errorMsg && (
        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400">
          {errorMsg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Personality & Prompts */}
        <div className="glass rounded-xl p-6 border border-slate-800 shadow lg:col-span-2 space-y-4">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            Agent Identity & Core System Instructions
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Receptionist Name</label>
              <input
                type="text"
                value={config.name}
                onChange={(e) => setConfig({ ...config, name: e.target.value })}
                className="w-full px-3.5 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Role Description</label>
              <input
                type="text"
                value={config.role_description}
                onChange={(e) => setConfig({ ...config, role_description: e.target.value })}
                className="w-full px-3.5 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Opening Greeting Message</label>
            <input
              type="text"
              value={config.greeting_message}
              onChange={(e) => setConfig({ ...config, greeting_message: e.target.value })}
              className="w-full px-3.5 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Fallback Phrase</label>
            <input
              type="text"
              value={config.fallback_message}
              onChange={(e) => setConfig({ ...config, fallback_message: e.target.value })}
              className="w-full px-3.5 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-semibold text-slate-300">
                Custom Business Policies & Guardrails
              </label>
              <button
                type="button"
                onClick={handlePreview}
                className="text-[11px] font-semibold text-blue-400 hover:text-blue-300 flex items-center gap-1 cursor-pointer"
              >
                <Eye className="w-3.5 h-3.5" /> Preview Compiled Prompt
              </button>
            </div>
            <textarea
              rows={8}
              value={config.system_prompt || ''}
              onChange={(e) => setConfig({ ...config, system_prompt: e.target.value })}
              placeholder="Optional instructions: e.g., Always ask whether the caller is a new or returning patient before booking."
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white font-mono leading-relaxed"
            />
          </div>

          {preview && (
            <div className="p-4 bg-slate-900/90 border border-blue-500/30 rounded-xl text-xs space-y-2">
              <div className="flex items-center justify-between font-bold text-blue-300">
                <span>Compiled Live System Prompt:</span>
                <button onClick={() => setPreview(null)} className="text-[10px] text-slate-400 hover:text-white cursor-pointer">
                  Close
                </button>
              </div>
              <pre className="text-[11px] text-slate-300 font-mono whitespace-pre-wrap">{preview}</pre>
            </div>
          )}
        </div>

        {/* Right Column: LLM, Acoustics & Telephony Escalation */}
        <div className="space-y-6">
          <div className="glass rounded-xl p-6 border border-slate-800 shadow space-y-4">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Cpu className="w-4 h-4 text-blue-400" />
              LLM Intelligence
            </h2>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">LLM Provider</label>
              <select
                value={config.llm_provider}
                onChange={(e) => {
                  const prov = e.target.value as AgentConfig['llm_provider'];
                  const defaultModels: Record<string, string> = {
                    groq: 'llama-3.3-70b-versatile',
                    gemini: 'gemini-2.0-flash',
                    openai: 'gpt-4o-mini',
                    anthropic: 'claude-3-5-haiku-latest',
                  };
                  setConfig({
                    ...config,
                    llm_provider: prov,
                    llm_model: defaultModels[prov] || config.llm_model,
                  });
                }}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
              >
                <option value="groq">Groq (Free Tier Ultra-Fast)</option>
                <option value="gemini">Google Gemini (Free Tier)</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Model Identifier</label>
              <input
                type="text"
                value={config.llm_model}
                onChange={(e) => setConfig({ ...config, llm_model: e.target.value })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white font-mono"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-slate-300">Temperature</span>
                <span className="font-mono text-blue-400 font-bold">{config.temperature}</span>
              </div>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={config.temperature}
                onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
                className="w-full accent-blue-500 cursor-pointer"
              />
            </div>
          </div>

          <div className="glass rounded-xl p-6 border border-slate-800 shadow space-y-4">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Volume2 className="w-4 h-4 text-emerald-400" />
              Speech Synthesis (TTS)
            </h2>

            {voices.length > 0 && (
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Voice Preset</label>
                <select
                  value={voices.some((v) => v.voice_id === config.voice_id) ? config.voice_id : ''}
                  onChange={(e) => e.target.value && handleVoicePresetChange(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
                >
                  <option value="">Custom Voice ID</option>
                  {voices.map((v) => (
                    <option key={`${v.provider}-${v.voice_id}`} value={v.voice_id}>
                      {v.name} — {v.provider.toUpperCase()} ({v.accent})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Provider</label>
              <select
                value={config.voice_provider}
                onChange={(e) => setConfig({ ...config, voice_provider: e.target.value as AgentConfig['voice_provider'] })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
              >
                <option value="edge">Microsoft Edge Neural (100% Free)</option>
                <option value="sarvam">Sarvam AI bulbul:v3 (India Multilingual)</option>
                <option value="cartesia">Cartesia Sonic (~40ms)</option>
                <option value="deepgram">Deepgram Aura</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Voice Profile ID</label>
              <input
                type="text"
                value={config.voice_id}
                onChange={(e) => setConfig({ ...config, voice_id: e.target.value })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white font-mono"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-slate-300">Speaking Speed</span>
                <span className="font-mono text-blue-400 font-bold">{config.speech_speed}x</span>
              </div>
              <input
                type="range"
                min="0.75"
                max="1.5"
                step="0.05"
                value={config.speech_speed}
                onChange={(e) => setConfig({ ...config, speech_speed: parseFloat(e.target.value) })}
                className="w-full accent-blue-500 cursor-pointer"
              />
            </div>
          </div>

          <div className="glass rounded-xl p-6 border border-slate-800 shadow space-y-4">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <PhoneForwarded className="w-4 h-4 text-amber-400" />
              Telephony Human Escalation
            </h2>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Transfer Phone Number (Reception / Doctor)
              </label>
              <input
                type="tel"
                value={config.transfer_phone_number || ''}
                onChange={(e) => setConfig({ ...config, transfer_phone_number: e.target.value })}
                placeholder="+919876543210"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white font-mono"
              />
              <p className="text-[10px] text-slate-400 mt-1">
                When customer asks for human or inquiry is beyond AI, the call transfers here.
              </p>
            </div>

            <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold text-white block">SMS Booking Confirmation</span>
                <span className="text-[10px] text-slate-400">Send confirmation SMS after booking</span>
              </div>
              <input
                type="checkbox"
                checked={config.sms_enabled}
                onChange={(e) => setConfig({ ...config, sms_enabled: e.target.checked })}
                className="w-4 h-4 accent-blue-500 cursor-pointer rounded"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
