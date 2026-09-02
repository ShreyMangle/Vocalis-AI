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
  Activity
} from 'lucide-react';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [business, setBusiness] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');

  useEffect(() => {
    if (token) {
      fetchProfile();
    }
  }, [token]);

  const fetchProfile = async () => {
    try {
      const res = await fetch('http://localhost:5000/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (res.ok) {
        setBusiness(data);
      } else {
        // Token expired/invalid
        handleSignOut();
      }
    } catch {
      handleSignOut();
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
        return <Dashboard />;
      case 'appointments':
        return <Appointments />;
      case 'calls':
        return <CallLogs />;
      case 'sandbox':
        return <Sandbox />;
      case 'settings':
        return <Settings />;
      case 'billing':
        return <Billing />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0f17] flex">
      {/* Sidebar navigation */}
      <aside className="w-64 bg-slate-950/80 border-r border-slate-800/80 flex flex-col justify-between p-5 relative">
        <div className="space-y-8">
          {/* Logo Section */}
          <div className="flex items-center gap-2.5 px-2">
            <div className="p-2 bg-blue-600/10 border border-blue-500/20 rounded-lg">
              <Activity className="h-5 w-5 text-blue-500 animate-pulse" />
            </div>
            <div>
              <span className="font-extrabold text-sm tracking-tight text-slate-100 block">VOCALIS</span>
              <span className="text-[9px] font-bold text-blue-400 uppercase tracking-widest block">AI VOICE CLIENT</span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'dashboard'
                  ? 'bg-blue-600/10 text-blue-400 border-l-2 border-blue-500'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <LayoutDashboard className="h-4.5 w-4.5" /> Dashboard
            </button>

            <button
              onClick={() => setActiveTab('appointments')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'appointments'
                  ? 'bg-blue-600/10 text-blue-400 border-l-2 border-blue-500'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <CalendarCheck className="h-4.5 w-4.5" /> Appointments
            </button>

            <button
              onClick={() => setActiveTab('calls')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'calls'
                  ? 'bg-blue-600/10 text-blue-400 border-l-2 border-blue-500'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <PhoneIncoming className="h-4.5 w-4.5" /> Call History
            </button>

            <button
              onClick={() => setActiveTab('sandbox')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'sandbox'
                  ? 'bg-blue-600/10 text-blue-400 border-l-2 border-blue-500'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <Terminal className="h-4.5 w-4.5" /> Live Sandbox
            </button>

            <button
              onClick={() => setActiveTab('settings')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'settings'
                  ? 'bg-blue-600/10 text-blue-400 border-l-2 border-blue-500'
                  : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
              }`}
            >
              <SettingsIcon className="h-4.5 w-4.5" /> Agent Settings
            </button>

            <button
              onClick={() => setActiveTab('billing')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                activeTab === 'billing'
                  ? 'bg-blue-600/10 text-blue-400 border-l-2 border-blue-500'
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
            <div className="flex items-center gap-2.5 px-2 py-1.5 bg-slate-900/40 rounded-xl border border-slate-800/40">
              <div className="p-1.5 bg-blue-600/10 rounded-lg">
                <User className="h-4 w-4 text-blue-400" />
              </div>
              <div className="overflow-hidden">
                <span className="font-semibold text-xs text-slate-200 block truncate">{business.name}</span>
                <span className="text-[10px] text-slate-500 flex items-center gap-1">
                  {business.plan === 'pro' && <Sparkles className="h-3 w-3 text-yellow-400 fill-yellow-400" />}
                  <span className="capitalize">{business.plan} Account</span>
                </span>
              </div>
            </div>
          )}

          <button
            onClick={handleSignOut}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-400 hover:bg-red-950/20 hover:text-red-400 transition cursor-pointer"
          >
            <LogOut className="h-4.5 w-4.5" /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main content display */}
      <main className="flex-1 p-8 overflow-y-auto max-h-screen">
        <div className="max-w-6xl mx-auto">
          <Suspense fallback={
            <div className="flex items-center justify-center min-h-[50vh]">
              <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          }>
            {renderContent()}
          </Suspense>
        </div>
      </main>
    </div>
  );
}
