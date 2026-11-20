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
  day_of_week: 'MONDAY' | 'TUESDAY' | 'WEDNESDAY' | 'THURSDAY' | 'FRIDAY' | 'SATURDAY' | 'SUNDAY';
  open_time: string;
  close_time: string;
  is_closed: boolean;
  break_start?: string;
  break_end?: string;
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
  business_id: string;
  agent_name: string;
  prompt_template: string;
  default_language: string;
  voice_provider: 'cartesia' | 'deepgram' | 'edge' | 'elevenlabs';
  voice_id: string;
  speech_speed: number;
  transfer_phone_number?: string;
  webhook_url?: string;
  fallback_behavior: string;
  sms_confirmation_enabled: boolean;
  active_hours_only: boolean;
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

export interface Call {
  id: string;
  tenant_id: string;
  business_id: string;
  call_sid?: string;
  direction: 'INBOUND' | 'OUTBOUND';
  status: 'IN_PROGRESS' | 'COMPLETED' | 'BUSY' | 'NO_ANSWER' | 'FAILED';
  from_number: string;
  to_number: string;
  duration_seconds: number;
  recording_url?: string;
  transcript?: string;
  sentiment: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  intent?: string;
  call_summary?: string;
  stt_latency_ms?: number;
  llm_latency_ms?: number;
  tts_latency_ms?: number;
  cost_usd: number;
  created_at: string;
}

export interface CallStats {
  total_calls: number;
  answered_calls: number;
  completed_calls: number;
  total_duration_seconds: number;
  avg_duration_seconds: number;
  total_cost_usd: number;
  avg_stt_latency_ms: number;
  avg_llm_latency_ms: number;
  avg_tts_latency_ms: number;
  sentiment_breakdown: Record<string, number>;
  outcome_breakdown: Record<string, number>;
}
