import { useState, useEffect, lazy, Suspense } from 'react';

const Login = lazy(() => import('./pages/Login'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Appointments = lazy(() => import('./pages/Appointments'));
const CallLogs = lazy(() => import('./pages/CallLogs'));
const Sandbox = lazy(() => import('./pages/Sandbox'));
const Billing = lazy(() => import('./pages/Billing'));
const Settings = lazy(() => import('./pages/Settings'));

import { 
  LayoutDashboard, 
  CalendarCheck, 
  PhoneIncoming, 
  Terminal, 
  CreditCard, 
  Settings as SettingsIcon,
  LogOut, 
  User, 
  Sparkles, 
  Activity,
  PhoneCall,
  Globe,
  Radio,
  Zap,
  X,
  Phone,
  CheckCircle2,
  RefreshCw
} from 'lucide-react';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [business, setBusiness] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [systemStatus, setSystemStatus] = useState(null);
  
  // Quick Call Modal states
  const [showCallModal, setShowCallModal] = useState(false);
  const [callPhone, setCallPhone] = useState('+91 9028525745');
  const [callName, setCallName] = useState('Shrey Mangle');
  const [callService, setCallService] = useState('Dental Checkup & Cleaning');
  const [callStatus, setCallStatus] = useState('idle'); // idle, ringing, in-progress, completed
  const [callTimer, setCallTimer] = useState(0);
  const [callFeedback, setCallFeedback] = useState('');

  useEffect(() => {
    if (token) {
      fetchProfile();
      fetchSystemStatus();
      const interval = setInterval(fetchSystemStatus, 15000);
      return () => clearInterval(interval);
    }
  }, [token]);

  // Call duration timer
  useEffect(() => {
    let interval = null;
    if (callStatus === 'in-progress' || callStatus === 'ringing') {
      interval = setInterval(() => {
        setCallTimer(prev => prev + 1);
      }, 1000);
    } else {
      clearInterval(interval);
    }
    return () => clearInterval(interval);
  }, [callStatus]);

  const fetchProfile = async () => {
    try {
      const res = await fetch('http://localhost:5000/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (res.ok) {
        setBusiness(data);
      } else {
        handleSignOut();
      }
    } catch {
      handleSignOut();
    }
  };

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch('http://localhost:5000/api/system/status');
      if (res.ok) {
        const data = await res.json();
        setSystemStatus(data);
      }
    } catch (err) {
      console.warn('System status poll failed:', err);
    }
  };

  const handleLoginSuccess = (newToken, newBusiness) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
    setBusiness(newBusiness);
    setActiveTab('dashboard');
  };

  const handleSignOut = () => {
    localStorage.removeItem('token');
    setToken(null);
    setBusiness(null);
  };

  const handleTriggerQuickCall = async () => {
    setCallStatus('ringing');
    setCallTimer(0);
    setCallFeedback('Initiating Twilio outbound stream...');

    try {
      const res = await fetch('http://localhost:5000/api/calls/quick-test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          customer_phone: callPhone,
          customer_name: callName,
          service: callService
        })
      });
      const data = await res.json();
      if (res.ok) {
        setCallStatus('in-progress');
        setCallFeedback(`Call placed! Ringing ${callPhone}... Answer to talk to Sarah.`);
      } else {
        setCallStatus('idle');
        setCallFeedback(`Call error: ${data.detail || 'Could not place call'}`);
      }
    } catch (err) {
      setCallStatus('idle');
      setCallFeedback(`Connection error: ${err.message}`);
    }
  };

  const formatTimer = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  if (!token) {
    return (
      <Suspense fallback={
        <div className="min-h-screen bg-[#0b0f17] flex items-center justify-center">
          <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      }>
        <Login onLoginSuccess={handleLoginSuccess} />
      </Suspense>
    );
  }

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard onQuickCall={() => setShowCallModal(true)} />;
      case 'appointments':
        return <Appointments onQuickCall={() => setShowCallModal(true)} />;
      case 'calls':
        return <CallLogs />;
      case 'sandbox':
        return <Sandbox />;
      case 'settings':
        return <Settings />;
      case 'billing':
        return <Billing />;
      default:
        return <Dashboard onQuickCall={() => setShowCallModal(true)} />;
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0f17] flex flex-col md:flex-row">
      {/* Sidebar navigation */}
      <aside className="w-full md:w-64 bg-slate-950/90 border-r border-slate-800/80 flex flex-col justify-between p-5 relative z-20">
        <div className="space-y-7">
          {/* Logo Section */}
          <div className="flex items-center gap-3 px-2">
            <div className="p-2.5 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl shadow-lg shadow-blue-500/20 border border-blue-400/30">
              <Activity className="h-5 w-5 text-white animate-pulse" />
            </div>
            <div>
              <span className="font-black text-base tracking-tight text-white block">VOCALIS AI</span>
              <span className="text-[10px] font-bold text-blue-400 uppercase tracking-widest block">ENTERPRISE VOICE</span>
            </div>
          </div>

          {/* Quick Call Action for Client Demos */}
          <div className="p-3 bg-gradient-to-r from-blue-900/40 via-indigo-900/30 to-slate-900/60 border border-blue-500/30 rounded-xl space-y-2">
            <div className="flex items-center justify-between text-xs text-blue-300 font-semibold">
              <span className="flex items-center gap-1.5">
                <Radio className="h-3.5 w-3.5 text-emerald-400 animate-pulse" /> Live Client Call
              </span>
              <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded border border-blue-400/20">Demo</span>
            </div>
            <button
              onClick={() => setShowCallModal(true)}
              className="w-full py-2 px-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 shadow-md shadow-blue-600/30 cursor-pointer"
            >
              <Zap className="h-3.5 w-3.5 text-yellow-300 fill-yellow-300" /> Launch Voice Demo
            </button>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'dashboard'
                  ? 'bg-blue-600/15 text-blue-400 border-l-2 border-blue-500 shadow-sm'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <LayoutDashboard className="h-4.5 w-4.5" /> Dashboard
            </button>

            <button
              onClick={() => setActiveTab('appointments')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'appointments'
                  ? 'bg-blue-600/15 text-blue-400 border-l-2 border-blue-500 shadow-sm'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <CalendarCheck className="h-4.5 w-4.5" /> Appointments
            </button>

            <button
              onClick={() => setActiveTab('calls')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'calls'
                  ? 'bg-blue-600/15 text-blue-400 border-l-2 border-blue-500 shadow-sm'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <PhoneIncoming className="h-4.5 w-4.5" /> Call History
            </button>

            <button
              onClick={() => setActiveTab('sandbox')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'sandbox'
                  ? 'bg-blue-600/15 text-blue-400 border-l-2 border-blue-500 shadow-sm'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <Terminal className="h-4.5 w-4.5" /> Live Sandbox
            </button>

            <button
              onClick={() => setActiveTab('settings')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'settings'
                  ? 'bg-blue-600/15 text-blue-400 border-l-2 border-blue-500 shadow-sm'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <SettingsIcon className="h-4.5 w-4.5" /> Agent Settings
            </button>

            <button
              onClick={() => setActiveTab('billing')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'billing'
                  ? 'bg-blue-600/15 text-blue-400 border-l-2 border-blue-500 shadow-sm'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <CreditCard className="h-4.5 w-4.5" /> Billing Plans
            </button>
          </nav>
        </div>

        {/* Business details and logout */}
        <div className="space-y-4 pt-4 border-t border-slate-800">
          {business && (
            <div className="flex items-center gap-2.5 px-2 py-1.5 bg-slate-900/60 rounded-xl border border-slate-800/60">
              <div className="p-1.5 bg-blue-600/20 text-blue-400 rounded-lg">
                <User className="h-4 w-4" />
              </div>
              <div className="overflow-hidden">
                <span className="font-semibold text-xs text-slate-200 block truncate">{business.name}</span>
                <span className="text-[10px] text-slate-400 flex items-center gap-1">
                  <Sparkles className="h-3 w-3 text-emerald-400 fill-emerald-400" />
                  <span className="capitalize">{business.industry || 'Healthcare'} Clinic</span>
                </span>
              </div>
            </div>
          )}

          <button
            onClick={handleSignOut}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:bg-red-950/30 hover:text-red-400 transition cursor-pointer"
          >
            <LogOut className="h-4 w-4" /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main content display */}
      <main className="flex-1 overflow-y-auto max-h-screen flex flex-col">
        {/* Global Executive Telemetry Bar */}
        <header className="px-8 py-3.5 bg-slate-950/60 backdrop-blur-md border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-4 sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1 bg-slate-900/80 border border-slate-800 rounded-full text-xs">
              <span className={`h-2 w-2 rounded-full ${systemStatus?.tunnel_online ? 'bg-emerald-400 animate-ping' : 'bg-amber-400'}`} />
              <span className="text-slate-400">Tunnel:</span>
              <span className={`font-mono font-medium ${systemStatus?.tunnel_online ? 'text-emerald-300' : 'text-amber-300'}`}>
                {systemStatus?.tunnel_online ? systemStatus.app_host : 'Localhost (Sandbox Only)'}
              </span>
            </div>

            <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-slate-900/80 border border-slate-800 rounded-full text-xs">
              <PhoneCall className="h-3.5 w-3.5 text-blue-400" />
              <span className="text-slate-400">Twilio PSTN:</span>
              <span className="font-mono text-slate-200">{systemStatus?.twilio_phone || '+1 (857) 578-0665'}</span>
            </div>

            <div className="hidden xl:flex items-center gap-2 px-3 py-1 bg-slate-900/80 border border-slate-800 rounded-full text-xs">
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
              <span className="text-slate-400">Pipeline:</span>
              <span className="text-slate-300 font-medium">Whisper + Qwen3.8 + Edge Neural</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchSystemStatus}
              title="Refresh System Health"
              className="p-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-slate-400 hover:text-slate-200 transition cursor-pointer"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setShowCallModal(true)}
              className="px-3.5 py-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-lg text-xs font-semibold transition flex items-center gap-2 shadow-md shadow-blue-600/20 cursor-pointer"
            >
              <Phone className="h-3.5 w-3.5" /> Quick Call Demo
            </button>
          </div>
        </header>

        {/* Page Content */}
        <div className="p-8 max-w-6xl w-full mx-auto flex-1">
          <Suspense fallback={
            <div className="flex items-center justify-center min-h-[50vh]">
              <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          }>
            {renderContent()}
          </Suspense>
        </div>
      </main>

      {/* Instant Live Call Showcase Modal */}
      {showCallModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-5 relative">
            <button
              onClick={() => {
                setShowCallModal(false);
                setCallStatus('idle');
                setCallFeedback('');
              }}
              className="absolute top-4 right-4 p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800 transition cursor-pointer"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-600/20 text-blue-400 rounded-xl border border-blue-500/30">
                <PhoneCall className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Live Outbound Phone Call</h3>
                <p className="text-xs text-slate-400">Trigger real AI dialogue directly to your mobile phone.</p>
              </div>
            </div>

            {callStatus === 'idle' ? (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-semibold text-slate-300">Destination Phone Number</label>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => {
                          setCallPhone(systemStatus?.default_test_phone || '+91 9028525745');
                          setCallName('Shrey Mangle');
                        }}
                        className="text-[10px] px-2 py-0.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 rounded border border-blue-500/30 transition cursor-pointer"
                      >
                        Verified Target
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setCallPhone('');
                          setCallName('');
                        }}
                        className="text-[10px] px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded border border-slate-700 transition cursor-pointer"
                      >
                        Custom
                      </button>
                    </div>
                  </div>
                  <input
                    type="text"
                    value={callPhone}
                    onChange={(e) => setCallPhone(e.target.value)}
                    placeholder="+1 (555) 234-5678 or +91..."
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-white font-mono focus:border-blue-500 focus:outline-none"
                  />
                  <span className="text-[11px] text-slate-500 mt-1 block">
                    Enter any verified phone or client number with country code.
                  </span>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1.5">Customer / Patient Name</label>
                  <input
                    type="text"
                    value={callName}
                    onChange={(e) => setCallName(e.target.value)}
                    placeholder="Shrey Mangle"
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1.5">Booking / Appointment Service</label>
                  <input
                    type="text"
                    value={callService}
                    onChange={(e) => setCallService(e.target.value)}
                    placeholder="Dental Checkup & Cleaning"
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>

                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl text-xs text-slate-400 space-y-1">
                  <div className="flex items-center justify-between text-slate-300">
                    <span>Assigned Voice Persona:</span>
                    <span className="font-semibold text-blue-400">Sarah (Neural Voice)</span>
                  </div>
                  <div className="flex items-center justify-between text-slate-300">
                    <span>Average Latency:</span>
                    <span className="font-mono text-emerald-400">&lt; 380 ms</span>
                  </div>
                </div>

                <button
                  onClick={handleTriggerQuickCall}
                  className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl text-sm font-bold transition flex items-center justify-center gap-2 shadow-lg shadow-blue-600/30 cursor-pointer"
                >
                  <Zap className="h-4 w-4 text-yellow-300 fill-yellow-300" /> Dispatch Call to Phone Now
                </button>
              </div>
            ) : (
              <div className="py-6 flex flex-col items-center justify-center space-y-5 text-center">
                <div className="relative">
                  <div className="w-20 h-20 rounded-full bg-blue-600/20 border-2 border-blue-500 flex items-center justify-center animate-pulse">
                    <Phone className="h-8 w-8 text-blue-400" />
                  </div>
                  <span className="absolute -top-1 -right-1 h-5 w-5 bg-emerald-500 rounded-full border-2 border-slate-900 flex items-center justify-center">
                    <span className="h-2 w-2 bg-white rounded-full animate-ping" />
                  </span>
                </div>

                <div className="space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">
                    {callStatus === 'ringing' ? 'Ringing Phone...' : 'Call In Progress'}
                  </span>
                  <h4 className="text-xl font-bold text-white">{callPhone}</h4>
                  <p className="text-sm text-slate-400">{callName} • {callService}</p>
                </div>

                <div className="px-4 py-2 bg-slate-950 border border-slate-800 rounded-xl font-mono text-lg font-bold text-emerald-400">
                  {formatTimer(callTimer)}
                </div>

                <p className="text-xs text-slate-400 max-w-xs">{callFeedback}</p>

                <button
                  onClick={() => {
                    setCallStatus('idle');
                    setCallFeedback('');
                  }}
                  className="px-5 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition cursor-pointer"
                >
                  Close & View Call Logs
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
