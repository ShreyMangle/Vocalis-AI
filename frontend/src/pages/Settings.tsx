import React, { useEffect, useState } from 'react';
import {
  Settings as SettingsIcon,
  Building2,
  Clock,
  Briefcase,
  Phone,
  Save,
  Plus,
  Trash2,
  CheckCircle,
  Radio,
} from 'lucide-react';
import { api } from '../lib/api';
import type { Business, Service, TelephonyStatus, WorkingHours } from '../types';

const ALL_DAYS: WorkingHours['day_of_week'][] = [
  'MONDAY',
  'TUESDAY',
  'WEDNESDAY',
  'THURSDAY',
  'FRIDAY',
  'SATURDAY',
  'SUNDAY',
];

const DEFAULT_SCHEDULE: WorkingHours[] = ALL_DAYS.map((day, idx) => ({
  id: `default-${idx}`,
  day_of_week: day,
  open_time: day === 'SUNDAY' ? null : '09:00:00',
  close_time: day === 'SUNDAY' ? null : '18:00:00',
  is_closed: day === 'SUNDAY',
}));

const normalizeSchedule = (rows: WorkingHours[]): WorkingHours[] => {
  const byDay = new Map(rows.map((r) => [r.day_of_week, r]));
  return ALL_DAYS.map((day, idx) => {
    const existing = byDay.get(day);
    if (existing) return existing;
    return DEFAULT_SCHEDULE[idx];
  });
};

export const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'profile' | 'hours' | 'services' | 'telephony'>('profile');
  const [business, setBusiness] = useState<Business | null>(null);
  const [workingHours, setWorkingHours] = useState<WorkingHours[]>(DEFAULT_SCHEDULE);
  const [services, setServices] = useState<Service[]>([]);
  const [telephony, setTelephony] = useState<TelephonyStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // New service modal state
  const [showServiceModal, setShowServiceModal] = useState(false);
  const [newServiceName, setNewServiceName] = useState('');
  const [newServiceDuration, setNewServiceDuration] = useState(30);
  const [newServicePrice, setNewServicePrice] = useState(500);
  const [newServiceCategory, setNewServiceCategory] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [biz, hrs, srv, tel] = await Promise.all([
        api.getBusiness().catch(() => null),
        api.getWorkingHours().catch(() => []),
        api.listServices().catch(() => ({ items: [], total: 0 })),
        api.getTelephonyStatus().catch(() => null),
      ]);
      setBusiness(biz);
      setWorkingHours(normalizeSchedule(Array.isArray(hrs) ? hrs : []));
      setServices(srv.items);
      setTelephony(tel);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!business) return;

    setSaving(true);
    setSaveSuccess(false);
    try {
      const updated = await api.updateBusiness(business);
      setBusiness(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveHours = async () => {
    setSaving(true);
    setSaveSuccess(false);
    try {
      const payload = workingHours.map((wh) => ({
        day_of_week: wh.day_of_week,
        open_time: wh.is_closed ? null : (wh.open_time || '09:00:00').slice(0, 5) + ':00',
        close_time: wh.is_closed ? null : (wh.close_time || '18:00:00').slice(0, 5) + ':00',
        is_closed: wh.is_closed,
      }));
      const res = await api.updateWorkingHours(payload);
      setWorkingHours(normalizeSchedule(Array.isArray(res) ? res : payload as WorkingHours[]));
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Hours save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleAddService = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newServiceName) return;

    try {
      await api.createService({
        name: newServiceName,
        duration_minutes: newServiceDuration,
        price: newServicePrice * 100, // into paise
        category: newServiceCategory || undefined,
      });
      setShowServiceModal(false);
      setNewServiceName('');
      await fetchData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to add service');
    }
  };

  const handleDeleteService = async (id: string) => {
    if (!confirm('Are you sure you want to delete this service?')) return;
    try {
      await api.deleteService(id);
      await fetchData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-white flex items-center gap-2">
          Business & Telephony Settings <SettingsIcon className="w-5 h-5 text-blue-400" />
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Configure operating hours, service catalogs, and telephony provider parameters.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 space-x-1">
        {[
          { id: 'profile', name: 'Business Profile', icon: Building2 },
          { id: 'hours', name: 'Operating Hours', icon: Clock },
          { id: 'services', name: 'Services Catalog', icon: Briefcase },
          { id: 'telephony', name: 'Telephony & Carrier', icon: Phone },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition cursor-pointer ${
              activeTab === tab.id
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <tab.icon className="w-3.5 h-3.5" />
            <span>{tab.name}</span>
          </button>
        ))}
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && business && (
        <form onSubmit={handleSaveProfile} className="glass rounded-xl p-6 border border-slate-800 shadow space-y-4 max-w-2xl">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white">Profile Details</h2>
            {saveSuccess && (
              <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                <CheckCircle className="w-3.5 h-3.5" /> Saved successfully
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Business Name</label>
              <input
                type="text"
                value={business.name}
                onChange={(e) => setBusiness({ ...business, name: e.target.value })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Industry Vertical</label>
              <input
                type="text"
                value={business.industry}
                onChange={(e) => setBusiness({ ...business, industry: e.target.value })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Phone Number</label>
              <input
                type="text"
                value={business.phone_number || ''}
                onChange={(e) => setBusiness({ ...business, phone_number: e.target.value })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Timezone</label>
              <input
                type="text"
                value={business.timezone}
                onChange={(e) => setBusiness({ ...business, timezone: e.target.value })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Business Summary</label>
            <textarea
              rows={3}
              value={business.description || ''}
              onChange={(e) => setBusiness({ ...business, description: e.target.value })}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
            />
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer shadow-lg shadow-blue-600/25"
            >
              <Save className="w-3.5 h-3.5" /> Save Profile
            </button>
          </div>
        </form>
      )}

      {/* Operating Hours Tab */}
      {activeTab === 'hours' && (
        <div className="glass rounded-xl p-6 border border-slate-800 shadow space-y-4 max-w-2xl">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white">Weekly Calendar Availability</h2>
            <button
              onClick={handleSaveHours}
              disabled={saving}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer shadow-lg shadow-blue-600/25"
            >
              <Save className="w-3.5 h-3.5" /> Save Hours
            </button>
          </div>

          <div className="space-y-2">
            {workingHours.map((wh, idx) => (
              <div key={wh.id || idx} className="flex items-center justify-between p-3 bg-slate-900/60 border border-slate-800 rounded-xl text-xs">
                <span className="w-28 font-bold text-slate-200 capitalize">{wh.day_of_week.toLowerCase()}</span>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1.5 text-slate-400">
                    <input
                      type="checkbox"
                      checked={wh.is_closed}
                      onChange={(e) => {
                        const updated = [...workingHours];
                        updated[idx].is_closed = e.target.checked;
                        setWorkingHours(updated);
                      }}
                      className="accent-blue-500"
                    />
                    <span>Closed</span>
                  </label>

                  {!wh.is_closed && (
                    <div className="flex items-center gap-2">
                      <input
                        type="time"
                        value={(wh.open_time || '09:00').slice(0, 5)}
                        onChange={(e) => {
                          const updated = [...workingHours];
                          updated[idx] = { ...updated[idx], open_time: e.target.value };
                          setWorkingHours(updated);
                        }}
                        className="px-2 py-1 bg-slate-950 border border-slate-700 rounded text-xs text-white"
                      />
                      <span className="text-slate-500">to</span>
                      <input
                        type="time"
                        value={(wh.close_time || '18:00').slice(0, 5)}
                        onChange={(e) => {
                          const updated = [...workingHours];
                          updated[idx] = { ...updated[idx], close_time: e.target.value };
                          setWorkingHours(updated);
                        }}
                        className="px-2 py-1 bg-slate-950 border border-slate-700 rounded text-xs text-white"
                      />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Services Tab */}
      {activeTab === 'services' && (
        <div className="glass rounded-xl border border-slate-800 shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
            <h2 className="text-sm font-bold text-white">Treatment & Service Catalog</h2>
            <button
              onClick={() => setShowServiceModal(true)}
              className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" /> Add Service
            </button>
          </div>

          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/60 text-slate-400 border-b border-slate-800 uppercase font-semibold text-[10px] tracking-wider">
              <tr>
                <th className="px-6 py-3">Service Name</th>
                <th className="px-6 py-3">Duration</th>
                <th className="px-6 py-3">Price</th>
                <th className="px-6 py-3">Category</th>
                <th className="px-6 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {services.map((s) => (
                <tr key={s.id} className="hover:bg-slate-900/40 transition">
                  <td className="px-6 py-4 font-semibold text-white">{s.name}</td>
                  <td className="px-6 py-4 font-mono text-slate-300">{s.duration_minutes} min</td>
                  <td className="px-6 py-4 font-mono text-emerald-400 font-bold">
                    ₹{(s.price / 100).toFixed(0)}
                  </td>
                  <td className="px-6 py-4 text-slate-400">{s.category || 'General'}</td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => handleDeleteService(s.id)}
                      className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Telephony Tab */}
      {activeTab === 'telephony' && (
        <div className="glass rounded-xl p-6 border border-slate-800 shadow space-y-4 max-w-2xl">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Radio className="w-4 h-4 text-emerald-400" />
                Telephony Carrier Integration
              </h2>
              <p className="text-xs text-slate-400">VoBiz (India TRAI Primary) + Twilio Global Fallback</p>
            </div>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                telephony?.is_configured
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
              }`}
            >
              {telephony?.is_configured ? 'CARRIER READY' : 'SIMULATION MODE'}
            </span>
          </div>

          <div className="space-y-3 pt-2">
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2">
              <span className="text-xs font-bold text-white block">Active Carrier Stream</span>
              <p className="text-xs text-slate-300">
                Primary Telephony Provider:{' '}
                <span className="font-mono text-blue-400 font-bold uppercase">
                  {telephony?.provider || 'vobiz'}
                </span>
              </p>
              <p className="text-xs text-slate-300">
                Active Carrier Number:{' '}
                <span className="font-mono text-slate-200">
                  {telephony?.active_number || 'Not configured (simulation fallback)'}
                </span>
              </p>
              <p className="text-[11px] text-slate-400">
                Account Credentials:{' '}
                <span className={telephony?.account_configured ? 'text-emerald-400' : 'text-amber-400'}>
                  {telephony?.account_configured ? 'Configured' : 'Missing'}
                </span>{' '}
                • Phone Line:{' '}
                <span className={telephony?.phone_number_configured ? 'text-emerald-400' : 'text-amber-400'}>
                  {telephony?.phone_number_configured ? 'Configured' : 'Missing'}
                </span>
              </p>
              <p className="text-[11px] text-slate-400">
                Bidirectional Media Stream Endpoint:{' '}
                <span className="font-mono text-slate-200">/api/v1/telephony/stream</span>
              </p>
            </div>

            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2">
              <span className="text-xs font-bold text-white block">Global Failover</span>
              <p className="text-xs text-slate-300">
                Secondary Telephony Provider: <span className="font-mono text-indigo-400 font-bold">Twilio</span>
              </p>
              <p className="text-[11px] text-slate-400">
                Automatically routes international callers outside India to Twilio voice media streams.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Add Service Modal */}
      {showServiceModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass rounded-2xl p-6 border border-slate-800 max-w-md w-full shadow-2xl space-y-4">
            <h2 className="text-base font-bold text-white">Add Offered Service</h2>
            <form onSubmit={handleAddService} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Service Display Name</label>
                <input
                  type="text"
                  required
                  value={newServiceName}
                  onChange={(e) => setNewServiceName(e.target.value)}
                  placeholder="e.g. General Dental Checkup"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Duration (Minutes)</label>
                <input
                  type="number"
                  min={5}
                  max={480}
                  value={newServiceDuration}
                  onChange={(e) => setNewServiceDuration(parseInt(e.target.value) || 30)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Price (₹ INR)</label>
                <input
                  type="number"
                  min={0}
                  value={newServicePrice}
                  onChange={(e) => setNewServicePrice(parseInt(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Category (Optional)</label>
                <input
                  type="text"
                  value={newServiceCategory}
                  onChange={(e) => setNewServiceCategory(e.target.value)}
                  placeholder="e.g. Consultation, Treatment"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-white"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowServiceModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold"
                >
                  Save Service
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
