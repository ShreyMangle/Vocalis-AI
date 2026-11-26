/**
 * VoxAI API Client
 * Typed fetch client with JWT token management and multi-tenant routing.
 */

import type {
  AgentConfig,
  Appointment,
  Business,
  Call,
  CallStats,
  Document,
  DocumentChunk,
  OutboundCallResult,
  PromptPreview,
  Service,
  TelephonyStatus,
  Tenant,
  TenantMember,
  User,
  VoiceCatalogItem,
  WorkingHours,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiClient {
  private getHeaders(isFormData = false): HeadersInit {
    const headers: Record<string, string> = {};
    if (!isFormData) {
      headers['Content-Type'] = 'application/json';
    }
    const token = localStorage.getItem('token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const isFormData = options.body instanceof FormData;
    const url = `${BASE_URL}${endpoint}`;
    const headers = { ...this.getHeaders(isFormData), ...options.headers };

    const res = await fetch(url, { ...options, headers });

    if (res.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/register')) {
      localStorage.removeItem('token');
      localStorage.removeItem('refreshToken');
      window.location.href = '/login';
      throw new Error('Session expired. Please login again.');
    }

    if (!res.ok) {
      let errorMessage = `HTTP error ${res.status}`;
      try {
        const errorJson = await res.json();
        if (errorJson.error?.message) {
          errorMessage = errorJson.error.message;
        } else if (typeof errorJson.detail === 'string') {
          errorMessage = errorJson.detail;
        } else if (Array.isArray(errorJson.detail)) {
          errorMessage = errorJson.detail
            .map((d: any) => (d.msg ? `${d.loc ? d.loc.slice(1).join('.') + ': ' : ''}${d.msg}` : JSON.stringify(d)))
            .join('; ');
        } else if (errorJson.message) {
          errorMessage = errorJson.message;
        }
      } catch {
        // use fallback
      }
      throw new Error(errorMessage);
    }

    if (res.status === 204) {
      return {} as T;
    }

    return res.json();
  }

  // ── Auth ──────────────────────────────────────────────────────────────────
  async register(data: {
    email: string;
    password: string;
    full_name: string;
    tenant_name?: string;
    business_name?: string;
    phone_number?: string;
  }) {
    const payload = {
      ...data,
      business_name: data.business_name || data.tenant_name,
      tenant_name: data.tenant_name || data.business_name,
    };
    return this.request<{ user: User; tenant: Tenant; tokens: { access_token: string; refresh_token: string } }>(
      '/api/v1/auth/register',
      { method: 'POST', body: JSON.stringify(payload) }
    );
  }

  async login(data: { email: string; password: string }) {
    return this.request<{ access_token: string; refresh_token: string; token_type: string }>(
      '/api/v1/auth/login',
      { method: 'POST', body: JSON.stringify(data) }
    );
  }

  async getMe() {
    return this.request<{ user: User; tenant: Tenant; role: string }>('/api/v1/auth/me');
  }

  // ── Business Profile ──────────────────────────────────────────────────────
  async getBusiness() {
    return this.request<Business>('/api/v1/business');
  }

  async updateBusiness(data: Partial<Business>) {
    return this.request<Business>('/api/v1/business', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async getWorkingHours() {
    return this.request<WorkingHours[]>('/api/v1/business/working-hours');
  }

  async updateWorkingHours(
    schedule: { day_of_week: WorkingHours['day_of_week']; open_time: string | null; close_time: string | null; is_closed: boolean }[]
  ) {
    return this.request<WorkingHours[]>('/api/v1/business/working-hours', {
      method: 'PUT',
      body: JSON.stringify({ schedule }),
    });
  }

  // ── Services ──────────────────────────────────────────────────────────────
  async listServices(category?: string) {
    const query = category ? `?category=${encodeURIComponent(category)}` : '';
    return this.request<{ items: Service[]; total: number }>(`/api/v1/business/services${query}`);
  }

  async createService(data: Partial<Service>) {
    return this.request<Service>('/api/v1/business/services', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateService(id: string, data: Partial<Service>) {
    return this.request<Service>(`/api/v1/business/services/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteService(id: string) {
    return this.request<void>(`/api/v1/business/services/${id}`, {
      method: 'DELETE',
    });
  }

  // ── Agent Configuration ───────────────────────────────────────────────────
  async getAgentConfig() {
    return this.request<AgentConfig>('/api/v1/agents');
  }

  async updateAgentConfig(data: Partial<AgentConfig>) {
    return this.request<AgentConfig>('/api/v1/agents', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async getVoices() {
    return this.request<VoiceCatalogItem[]>('/api/v1/agents/voices');
  }

  async previewPrompt() {
    return this.request<PromptPreview>('/api/v1/agents/preview-prompt', {
      method: 'POST',
    });
  }

  // ── Knowledge Base (RAG) ──────────────────────────────────────────────────
  async listDocuments() {
    return this.request<{ items: Document[]; total: number }>('/api/v1/business/documents');
  }

  async uploadDocument(file: File, title?: string) {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);

    return this.request<Document>('/api/v1/business/documents/upload', {
      method: 'POST',
      body: formData,
    });
  }

  async createFAQ(data: { title: string; items: { question: string; answer: string; category?: string }[] }) {
    return this.request<Document>('/api/v1/business/documents/faq', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getDocumentChunks(documentId: string) {
    return this.request<DocumentChunk[]>(`/api/v1/business/documents/${documentId}/chunks`);
  }

  async deleteDocument(documentId: string) {
    return this.request<void>(`/api/v1/business/documents/${documentId}`, {
      method: 'DELETE',
    });
  }

  async searchKnowledge(query: string, top_k = 3) {
    return this.request<{
      query: string;
      results: {
        chunk_id: string;
        document_id: string;
        document_title: string;
        content: string;
        similarity_score: number;
        metadata: Record<string, unknown>;
      }[];
      total_found: number;
    }>('/api/v1/business/documents/search', {
      method: 'POST',
      body: JSON.stringify({ query, top_k }),
    });
  }

  // ── Appointments ──────────────────────────────────────────────────────────
  async listAppointments(status?: string) {
    const query = status ? `?status=${encodeURIComponent(status)}` : '';
    return this.request<{ items: Appointment[]; total: number }>(`/api/v1/appointments${query}`);
  }

  async createAppointment(data: {
    customer_name: string;
    customer_phone: string;
    customer_email?: string;
    service_id?: string;
    scheduled_at: string;
    duration_minutes: number;
    notes?: string;
  }) {
    return this.request<Appointment>('/api/v1/appointments', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getAvailableSlots(date: string, duration_minutes = 30) {
    return this.request<{
      date: string;
      business_timezone: string;
      slots: { start_time: string; end_time: string; formatted_time: string }[];
    }>(
      `/api/v1/appointments/availability/slots?target_date=${encodeURIComponent(date)}&duration_minutes=${duration_minutes}`
    );
  }

  // ── Calls & Telemetry ─────────────────────────────────────────────────────
  async listCalls(limit = 50, offset = 0) {
    return this.request<{ items: Call[]; total: number }>(`/api/v1/calls?limit=${limit}&offset=${offset}`);
  }

  async getCallStats() {
    return this.request<CallStats>('/api/v1/calls/analytics/stats');
  }

  async exportCallsCsv(): Promise<void> {
    const res = await fetch(`${BASE_URL}/api/v1/calls/export/csv`, {
      headers: this.getHeaders(true),
    });
    if (!res.ok) {
      throw new Error(`CSV export failed (HTTP ${res.status})`);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'voxai_call_report.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }

  async triggerOutboundCall(data: {
    to_phone: string;
    customer_name?: string;
    appointment_id?: string;
    custom_greeting?: string;
  }) {
    return this.request<OutboundCallResult>('/api/v1/telephony/outbound-call', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getTelephonyStatus() {
    return this.request<TelephonyStatus>('/api/v1/telephony/status');
  }

  // ── Tenants ───────────────────────────────────────────────────────────────
  async getCurrentTenant() {
    return this.request<Tenant>('/api/v1/tenants/current');
  }

  async getMembers() {
    return this.request<TenantMember[]>('/api/v1/tenants/current/members');
  }
}

export const api = new ApiClient();
