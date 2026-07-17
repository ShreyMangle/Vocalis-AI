import { useState } from 'react';
import { Sparkles, ArrowRight, Activity } from 'lucide-react';

export default function Login({ onLoginSuccess }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [industry, setIndustry] = useState('Dental Clinic');
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const url = isRegister ? '/api/auth/register' : '/api/auth/login';
    const payload = isRegister 
      ? { name, email, password, industry, phone_number: phone }
      : { email, password };

    try {
      // Connect to server (using relative path which will proxy or load directly)
      const res = await fetch(`http://localhost:5000${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Something went wrong');
      }

      onLoginSuccess(data.token, data.business);
    } catch (err) {
      setError(err.message || 'Connection to server failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0b0f17] relative overflow-hidden px-4">
      {/* Decorative gradients */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-blue-900/20 rounded-full blur-[120px]" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-purple-900/20 rounded-full blur-[120px]" />

      <div className="w-full max-w-md glass rounded-2xl p-8 shadow-2xl relative z-10">
        <div className="flex flex-col items-center mb-8">
          <div className="p-3 bg-blue-600/10 border border-blue-500/30 rounded-xl mb-4">
            <Activity className="h-8 w-8 text-blue-500 animate-pulse" />
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            AI Voice Agent <Sparkles className="h-5 w-5 text-yellow-400 fill-yellow-400" />
          </h2>
          <p className="text-slate-400 text-sm mt-2 text-center">
            {isRegister ? 'Set up your business dashboard' : 'Sign in to manage confirmation calls'}
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-900/20 border border-red-500/30 text-red-300 rounded-lg text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegister && (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Business Name
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Bright Smiles Dental"
                  className="w-full px-4 py-2.5 bg-slate-900/50 border border-slate-700/50 rounded-lg focus:outline-none focus:border-blue-500 text-slate-200 text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                    Industry
                  </label>
                  <select
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="w-full px-3 py-2.5 bg-slate-900/50 border border-slate-700/50 rounded-lg focus:outline-none focus:border-blue-500 text-slate-200 text-sm"
                  >
                    <option value="Dental Clinic">Dental Clinic</option>
                    <option value="Hair Salon">Hair Salon</option>
                    <option value="Auto Repair">Auto Repair</option>
                    <option value="Medical Practice">Medical Practice</option>
                    <option value="Consulting">Consulting</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                    Outbound Phone
                  </label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+1234567890"
                    className="w-full px-4 py-2.5 bg-slate-900/50 border border-slate-700/50 rounded-lg focus:outline-none focus:border-blue-500 text-slate-200 text-sm"
                  />
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full px-4 py-2.5 bg-slate-900/50 border border-slate-700/50 rounded-lg focus:outline-none focus:border-blue-500 text-slate-200 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-4 py-2.5 bg-slate-900/50 border border-slate-700/50 rounded-lg focus:outline-none focus:border-blue-500 text-slate-200 text-sm"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg shadow-lg hover:shadow-blue-500/20 transition-all flex items-center justify-center gap-2 text-sm mt-6 cursor-pointer"
          >
            {loading ? 'Processing...' : isRegister ? 'Create Account' : 'Sign In'}
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>

        <div className="mt-6 text-center text-sm">
          <button
            onClick={() => setIsRegister(!isRegister)}
            className="text-blue-400 hover:text-blue-300 font-medium transition cursor-pointer"
          >
            {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Create one"}
          </button>
        </div>
      </div>
    </div>
  );
}
