/**
 * VoxAI Frontend TypeScript Domain Models
 */

export type UserRole = 'OWNER' | 'ADMIN' | 'MEMBER' | 'STAFF' | 'BILLING';

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  is_active: boolean;
  created_at: string;
}

export interface TenantMember {
  user_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  joined_at: string;
}

export interface Business {
  id: string;
  tenant_id: string;
  name: string;
  description?: string;
  industry: string;
  timezone: string;
  phone_number?: string;
  email?: string;
  website?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
}

export interface WorkingHours {
  id: string;
  tenant_id?: string;
  business_id?: string;
  day_of_week: 'MONDAY' | 'TUESDAY' | 'WEDNESDAY' | 'THURSDAY' | 'FRIDAY' | 'SATURDAY' | 'SUNDAY';
  open_time: string | null;
  close_time: string | null;
  is_closed: boolean;
}

export interface Service {
  id: string;
  tenant_id: string;
  business_id: string;
  name: string;
  description?: string;
  duration_minutes: number;
  price: number;
  currency: string;
  category?: string;
  is_active: boolean;
}

export interface AgentConfig {
  id: string;
  tenant_id: string;
  business_id?: string | null;
  name: string;
  role_description: string;
  system_prompt?: string | null;
  greeting_message: string;
  fallback_message: string;
  voice_provider: 'edge' | 'cartesia' | 'deepgram' | 'sarvam' | 'elevenlabs' | 'azure';
  voice_id: string;
  speech_speed: number;
  llm_provider: 'groq' | 'gemini' | 'openai' | 'anthropic';
  llm_model: string;
  temperature: number;
  vad_sensitivity: 'low' | 'normal' | 'high';
  primary_language: string;
  supported_languages: string[];
  transfer_phone_number?: string | null;
  webhook_url?: string | null;
  sms_enabled: boolean;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface VoiceCatalogItem {
  provider: string;
  voice_id: string;
  name: string;
  gender: string;
  accent: string;
  description: string;
  sample_preview_text: string;
  recommended: boolean;
}

export interface PromptPreview {
  compiled_prompt: string;
  agent_name: string;
  business_name?: string | null;
  timezone: string;
  services_count: number;
  working_hours_count: number;
}

export interface Document {
  id: string;
  tenant_id: string;
  business_id: string;
  title: string;
  filename: string;
  file_type: 'pdf' | 'docx' | 'txt' | 'faq' | 'text';
  file_size_bytes: number;
  status: 'PENDING' | 'PROCESSING' | 'READY' | 'FAILED';
  error_message?: string;
  chunk_count: number;
  doc_metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  chunk_metadata?: Record<string, unknown>;
}

export interface Appointment {
  id: string;
  tenant_id: string;
  business_id: string;
  service_id?: string;
  customer_name: string;
  customer_phone: string;
  customer_email?: string;
  scheduled_at: string;
  duration_minutes: number;
  status: 'CONFIRMED' | 'CANCELLED' | 'RESCHEDULED' | 'COMPLETED' | 'NO_SHOW';
  notes?: string;
  created_by_agent: boolean;
  created_at: string;
}

export interface CallTranscriptTurn {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp?: number;
}

export interface Call {
  id: string;
  tenant_id: string;
  business_id: string;
  appointment_id?: string | null;
  caller_phone: string;
  direction: 'INBOUND' | 'OUTBOUND';
  status: 'IN_PROGRESS' | 'COMPLETED' | 'BUSY' | 'NO_ANSWER' | 'FAILED';
  started_at: string;
  ended_at?: string | null;
  duration_seconds: number;
  recording_url?: string | null;
  transcript: CallTranscriptTurn[];
  sentiment: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  intent?: string | null;
  notes?: string | null;
  stt_latency_ms: number;
  llm_latency_ms: number;
  tts_latency_ms: number;
  cost_cents: number;
  created_at: string;
}

export interface CallStats {
  total_calls: number;
  total_duration_minutes: number;
  avg_duration_seconds: number;
  total_cost_usd: number;
  sentiment_breakdown: Record<string, number>;
  avg_stt_latency_ms: number;
  avg_llm_latency_ms: number;
  avg_tts_latency_ms: number;
  avg_e2e_latency_ms: number;
}

export interface TelephonyStatus {
  provider: string;
  is_configured: boolean;
  phone_number_configured: boolean;
  account_configured: boolean;
  vobiz_configured: boolean;
  twilio_configured: boolean;
  active_number?: string | null;
}

export interface OutboundCallResult {
  status: string;
  call_sid: string;
  to_phone: string;
  from_phone?: string | null;
  message: string;
}
