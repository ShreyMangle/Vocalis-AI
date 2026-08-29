import { useEffect, useState } from 'react';
import { 
  Plus, 
  Upload, 
  Trash2, 
  Phone, 
  Calendar, 
  AlertCircle, 
  Copy, 
  Check, 
  Sparkles, 
  Search, 
  Download, 
  Send,
  RefreshCw,
  Clock
} from 'lucide-react';

export default function Appointments() {
  const [appointments, setAppointments] = useState([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  
  const [showCsvUpload, setShowCsvUpload] = useState(false);
  const [csvText, setCsvText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [callingId, setCallingId] = useState(null);
  const [businessId, setBusinessId] = useState('');
  
  const [copiedFeed, setCopiedFeed] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [dispatchingCampaign, setDispatchingCampaign] = useState(false);
  const [campaignResult, setCampaignResult] = useState(null);

  useEffect(() => {
    fetchAppointments();
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (res.ok && data.id) {
        setBusinessId(data.id);
      }
    } catch (err) {
      console.error('Error fetching profile:', err);
    }
  };

  const fetchAppointments = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/appointments', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setAppointments(data || []);
    } catch (err) {
      console.error('Error fetching appointments:', err);
    }
  };

  const handleAddAppointment = async (e) => {
    e.preventDefault();
    setError('');

    const scheduled_at = new Date(`${date}T${time}`).toISOString();
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/appointments', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ customer_name: name, customer_phone: phone, scheduled_at })
      });

      if (!res.ok) throw new Error('Failed to create appointment');

      setName('');
      setPhone('');
      setDate('');
      setTime('');
      setShowAddForm(false);
      fetchAppointments();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCsvUpload = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/appointments/upload', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ csvText })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to upload CSV');

      setCsvText('');
      setShowCsvUpload(false);
      fetchAppointments();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this appointment?')) return;
    try {
      const token = localStorage.getItem('token');
      await fetch(`http://localhost:5000/api/appointments/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchAppointments();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleTriggerCall = async (appt) => {
    setCallingId(appt.id);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`http://localhost:5000/api/appointments/${appt.id}/trigger`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || 'Failed to start voice call');
      
      alert('Outbound call triggered! Navigate to the Live Sandbox simulator or answer your registered phone.');
      fetchAppointments();
    } catch (err) {
      alert(`Call error: ${err.message}`);
    } finally {
      setCallingId(null);
    }
  };

  const handleDispatchCampaign = async () => {
    if (!confirm('Run outbound automated voice reminder batch for all pending appointments?')) return;
    setDispatchingCampaign(true);
    setCampaignResult(null);

    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/campaigns/dispatch-reminders', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to dispatch campaign');

      setCampaignResult(data);
      fetchAppointments();
    } catch (err) {
      alert(`Campaign error: ${err.message}`);
    } finally {
      setDispatchingCampaign(false);
    }
  };

  const calendarFeedUrl = businessId ? `http://localhost:5000/api/calendar/${businessId}/feed.ics` : '';

  const copyCalendarFeed = () => {
    if (!calendarFeedUrl) return;
    navigator.clipboard.writeText(calendarFeedUrl);
    setCopiedFeed(true);
    setTimeout(() => setCopiedFeed(false), 3000);
  };

  const filteredAppointments = appointments.filter((appt) => {
    const matchesStatus = statusFilter === 'all' || appt.status === statusFilter;
    const matchesSearch = 
      appt.customer_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      appt.customer_phone?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
            Appointments Manager
          </h1>
          <p className="text-slate-400 text-sm">
            Manage upcoming bookings, synchronize live calendar feeds, and launch outbound reminder campaigns.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={handleDispatchCampaign}
            disabled={dispatchingCampaign}
            className="px-3.5 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 rounded-lg text-sm text-white font-semibold transition flex items-center gap-2 shadow-lg shadow-blue-900/20 cursor-pointer disabled:opacity-50"
          >
            <Send className={`h-4 w-4 ${dispatchingCampaign ? 'animate-spin' : ''}`} />
            {dispatchingCampaign ? 'Dispatching Calls...' : 'Run 24h Reminder Batch'}
          </button>
          <button
            onClick={() => {
              setShowCsvUpload(true);
              setShowAddForm(false);
            }}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/60 rounded-lg text-sm text-slate-300 font-medium transition flex items-center gap-2 cursor-pointer"
          >
            <Upload className="h-4 w-4" /> CSV Import
          </button>
          <button
            onClick={() => {
              setShowAddForm(true);
              setShowCsvUpload(false);
            }}
            className="px-3.5 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm text-white font-medium transition flex items-center gap-2 cursor-pointer"
          >
            <Plus className="h-4 w-4" /> Add Slot
          </button>
        </div>
      </div>

      {/* Campaign Result Toast */}
      {campaignResult && (
        <div className="p-4 bg-emerald-950/40 border border-emerald-500/30 rounded-xl flex items-center justify-between text-emerald-300 text-sm animate-fade-in">
          <div className="flex items-center gap-2.5">
            <Sparkles className="h-5 w-5 text-emerald-400" />
            <span>
              <strong>Campaign Executed:</strong> {campaignResult.message} ({campaignResult.count} calls initiated).
            </span>
          </div>
          <button
            onClick={() => setCampaignResult(null)}
            className="text-xs text-emerald-400/80 hover:text-emerald-200 cursor-pointer font-semibold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Live Calendar Subscription Banner */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-slate-900/90 via-slate-900/60 to-blue-950/40 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-400">
            <Calendar className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-200">Live iCal Calendar Sync</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase">
                RFC 5545 Live
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Subscribe to real-time confirmed & rescheduled bookings in Google Calendar, Apple Calendar, or Outlook.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 w-full md:w-auto">
          <button
            onClick={copyCalendarFeed}
            className="flex-1 md:flex-initial px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition flex items-center justify-center gap-1.5 cursor-pointer"
          >
            {copiedFeed ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            {copiedFeed ? 'Copied iCal Link!' : 'Copy Feed URL'}
          </button>
          {calendarFeedUrl && (
            <a
              href={calendarFeedUrl}
              download={`vocalis_appointments_${businessId}.ics`}
              className="px-3.5 py-1.5 bg-blue-600/10 hover:bg-blue-600/20 border border-blue-500/30 text-blue-400 rounded-lg text-xs font-semibold transition flex items-center justify-center gap-1.5"
            >
              <Download className="h-3.5 w-3.5" /> Download .ics
            </a>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-900/20 border border-red-500/30 text-red-300 rounded-lg text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {/* Manual Add Form */}
      {showAddForm && (
        <form onSubmit={handleAddAppointment} className="glass rounded-xl p-6 border border-slate-700/50 space-y-4 max-w-xl">
          <h3 className="text-md font-semibold text-slate-200">New Appointment</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Customer Name</label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Doe"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg focus:outline-none focus:border-blue-500 text-slate-200 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Phone Number</label>
              <input
                type="tel"
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+1234567890"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg focus:outline-none focus:border-blue-500 text-slate-200 text-sm"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Date</label>
              <input
                type="date"
                required
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg focus:outline-none focus:border-blue-500 text-slate-200 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase mb-1">Time</label>
              <input
                type="time"
                required
                value={time}
                onChange={(e) => setTime(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg focus:outline-none focus:border-blue-500 text-slate-200 text-sm"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button
              type="button"
              onClick={() => setShowAddForm(false)}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-slate-300 transition cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm text-white transition cursor-pointer"
            >
              Save Appointment
            </button>
          </div>
        </form>
      )}

      {/* CSV paste/import panel */}
      {showCsvUpload && (
        <form onSubmit={handleCsvUpload} className="glass rounded-xl p-6 border border-slate-700/50 space-y-4 max-w-xl">
          <h3 className="text-md font-semibold text-slate-200">Import CSV List</h3>
          <p className="text-xs text-slate-400">Paste comma-separated rows. Expected format: `CustomerName, PhoneNumber, ScheduledTime(ISO/YYYY-MM-DD HH:MM)`.</p>
          <textarea
            required
            rows={5}
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            placeholder="Jane Doe, +1234567890, 2026-07-16 10:00&#10;John Smith, +1987654321, 2026-07-16 14:30"
            className="w-full p-3 bg-slate-900 border border-slate-700 rounded-lg focus:outline-none focus:border-blue-500 text-slate-200 text-sm font-mono"
          />
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => setShowCsvUpload(false)}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-slate-300 transition cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm text-white transition flex items-center gap-1 cursor-pointer"
            >
              {loading ? 'Importing...' : 'Upload List'}
            </button>
          </div>
        </form>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-3 pt-2">
        {/* Status Pills */}
        <div className="flex items-center gap-1.5 bg-slate-900/60 p-1 rounded-xl border border-slate-800 w-full md:w-auto overflow-x-auto">
          {['all', 'pending', 'confirmed', 'rescheduled', 'cancelled'].map((tab) => (
            <button
              key={tab}
              onClick={() => setStatusFilter(tab)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition cursor-pointer whitespace-nowrap ${
                statusFilter === tab
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative w-full md:w-72">
          <Search className="h-4 w-4 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search by name or phone..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-slate-900/80 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Table list */}
      <div className="glass rounded-xl border border-slate-700/50 overflow-hidden shadow-xl">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-slate-900/60 border-b border-slate-700/50 text-slate-400 text-xs font-semibold uppercase tracking-wider">
              <th className="px-6 py-4">Customer</th>
              <th className="px-6 py-4">Phone Number</th>
              <th className="px-6 py-4">Scheduled Date & Time</th>
              <th className="px-6 py-4">Status</th>
              <th className="px-6 py-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80 text-sm text-slate-300">
            {filteredAppointments.length > 0 ? (
              filteredAppointments.map((appt) => (
                <tr key={appt.id} className="hover:bg-slate-800/30 transition-all">
                  <td className="px-6 py-4 font-medium text-slate-200">{appt.customer_name}</td>
                  <td className="px-6 py-4 font-mono text-slate-400 text-xs">{appt.customer_phone}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 text-slate-300">
                      <Clock className="h-3.5 w-3.5 text-blue-400" />
                      {new Date(appt.scheduled_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                        appt.status === 'confirmed'
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                          : appt.status === 'rescheduled'
                          ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                          : appt.status === 'cancelled'
                          ? 'bg-red-500/10 border-red-500/30 text-red-400'
                          : 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                      }`}
                    >
                      {appt.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button
                      onClick={() => handleTriggerCall(appt)}
                      disabled={callingId !== null}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600/10 border border-blue-500/20 hover:bg-blue-600/20 text-blue-400 rounded-lg text-xs font-semibold transition cursor-pointer"
                    >
                      <Phone className="h-3.5 w-3.5" />
                      {callingId === appt.id ? 'Calling...' : 'Trigger Call'}
                    </button>
                    <button
                      onClick={() => handleDelete(appt.id)}
                      className="p-1.5 border border-slate-700/50 hover:border-red-500/30 text-slate-500 hover:text-red-400 rounded-lg transition cursor-pointer"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="text-center py-12 text-slate-500">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Calendar className="h-8 w-8 text-slate-600" />
                    <span className="text-sm font-medium">No appointments match your filters</span>
                    <span className="text-xs text-slate-600">Try changing status filter or adding a new booking</span>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
