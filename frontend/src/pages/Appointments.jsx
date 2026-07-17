import { useEffect, useState } from 'react';
import { Plus, Upload, Trash2, Phone, Calendar, AlertCircle } from 'lucide-react';

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

  useEffect(() => {
    fetchAppointments();
  }, []);

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
      
      alert('Outbound call triggered! If using Sandbox mode, navigate to the Sandbox Simulator to start speaking.');
      fetchAppointments();
    } catch (err) {
      alert(`Call error: ${err.message}`);
    } finally {
      setCallingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Appointments Manager</h1>
          <p className="text-slate-400 text-sm">Upload upcoming appointments list and trigger AI confirmations.</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => {
              setShowCsvUpload(true);
              setShowAddForm(false);
            }}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-300 font-medium transition flex items-center gap-2 cursor-pointer"
          >
            <Upload className="h-4 w-4" /> CSV Upload
          </button>
          <button
            onClick={() => {
              setShowAddForm(true);
              setShowCsvUpload(false);
            }}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm text-white font-medium transition flex items-center gap-2 cursor-pointer"
          >
            <Plus className="h-4 w-4" /> Add Appointment
          </button>
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
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-slate-300 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm text-white transition"
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
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-slate-300 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm text-white transition flex items-center gap-1"
            >
              {loading ? 'Importing...' : 'Upload List'}
            </button>
          </div>
        </form>
      )}

      {/* Table list */}
      <div className="glass rounded-xl border border-slate-700/50 overflow-hidden">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-slate-900/50 border-b border-slate-700/50 text-slate-400 text-xs font-semibold uppercase tracking-wider">
              <th className="px-6 py-4">Customer</th>
              <th className="px-6 py-4">Phone Number</th>
              <th className="px-6 py-4">Scheduled Date & Time</th>
              <th className="px-6 py-4">Status</th>
              <th className="px-6 py-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80 text-sm text-slate-300">
            {appointments.length > 0 ? (
              appointments.map((appt) => (
                <tr key={appt.id} className="hover:bg-slate-800/20 transition-all">
                  <td className="px-6 py-4 font-medium text-slate-200">{appt.customer_name}</td>
                  <td className="px-6 py-4 font-mono text-slate-400">{appt.customer_phone}</td>
                  <td className="px-6 py-4 flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-slate-500" />
                    {new Date(appt.scheduled_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                        appt.status === 'confirmed'
                          ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                          : appt.status === 'rescheduled'
                          ? 'bg-blue-500/10 border-blue-500/20 text-blue-400'
                          : appt.status === 'cancelled'
                          ? 'bg-red-500/10 border-red-500/20 text-red-400'
                          : 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400'
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
                <td colSpan={5} className="text-center py-10 text-slate-500">
                  No appointments registered. Create one manually or upload a CSV file list above!
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
