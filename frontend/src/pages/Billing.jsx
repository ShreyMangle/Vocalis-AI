import { useEffect, useState } from 'react';
import { Check, ShieldCheck, Zap, Sparkles, Building2, CreditCard, Lock } from 'lucide-react';

export default function Billing() {
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState(false);
  const [annualBilling, setAnnualBilling] = useState(false);

  useEffect(() => {
    fetchBillingStatus();
  }, []);

  const fetchBillingStatus = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/billing/status', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setBilling(data);
    } catch (err) {
      console.error('Error fetching billing status:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCheckout = async (plan) => {
    setCheckingOut(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/billing/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ plan })
      });
      const data = await res.json();
      
      if (!res.ok) throw new Error(data.error || 'Failed to initialize checkout');

      if (data.isMock) {
        const succRes = await fetch('http://localhost:5000/api/billing/success-callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({ plan })
        });
        await succRes.json();
        
        if (succRes.ok) {
          alert(`Success! Your business has been upgraded to the ${plan.toUpperCase()} plan.`);
          fetchBillingStatus();
        }
      } else if (data.url) {
        window.location.href = data.url;
      }
    } catch (err) {
      alert(`Stripe error: ${err.message}`);
    } finally {
      setCheckingOut(false);
    }
  };

  const handleDowngrade = async () => {
    if (!confirm('Are you sure you want to cancel your plan and downgrade to Free Sandbox?')) return;
    setCheckingOut(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('http://localhost:5000/api/billing/success-callback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ plan: 'free' })
      });
      if (res.ok) {
        alert('Plan downgraded to Free.');
        fetchBillingStatus();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setCheckingOut(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const currentPlan = billing?.plan || 'free';

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            Subscription & Billing <CreditCard className="h-6 w-6 text-blue-400" />
          </h1>
          <p className="text-slate-400 text-sm mt-0.5">
            Transparent pricing plans with automated Stripe payment checkout and instant quota upgrades.
          </p>
        </div>

        {/* Billing Cycle Toggle */}
        <div className="flex items-center gap-2 bg-slate-900/80 p-1 rounded-xl border border-slate-800 self-start">
          <button
            onClick={() => setAnnualBilling(false)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
              !annualBilling ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Monthly Billing
          </button>
          <button
            onClick={() => setAnnualBilling(true)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer flex items-center gap-1 ${
              annualBilling ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Annual Billing <span className="text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded">Save 20%</span>
          </button>
        </div>
      </div>

      {/* Plan Status Banner */}
      <div className="glass rounded-xl p-5 border border-blue-500/20 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-lg">
        <div className="flex items-center gap-3.5">
          <div className="p-3 bg-blue-600/15 border border-blue-500/30 rounded-xl text-blue-400">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Active Subscription</span>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-500/15 border border-blue-500/30 text-blue-400 uppercase">
                {currentPlan} Account
              </span>
            </div>
            <p className="text-slate-300 text-sm mt-1">
              {currentPlan === 'enterprise' 
                ? 'Enterprise tier active with unlimited outbound calls, priority Groq processing, and custom SIP trunks.'
                : currentPlan === 'pro'
                ? 'Pro plan active. Enjoy automated 24h batches and unlimited AI voice calls.'
                : 'Free sandbox active. Unlimited simulated browser calls with 10 free real outbound minutes.'}
            </p>
          </div>
        </div>
        {currentPlan !== 'free' && (
          <button
            onClick={handleDowngrade}
            disabled={checkingOut}
            className="px-4 py-2 border border-slate-700 hover:border-red-500/40 text-slate-400 hover:text-red-400 text-xs font-semibold rounded-xl transition cursor-pointer"
          >
            Cancel Subscription
          </button>
        )}
      </div>

      {/* Pricing Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
        {/* Free Plan */}
        <div className="glass rounded-xl p-6 border border-slate-700/50 flex flex-col justify-between relative overflow-hidden shadow-xl">
          <div className="space-y-4">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">Developer Tier</span>
            <h3 className="text-xl font-bold text-slate-100">Sandbox Trial</h3>
            <div className="flex items-baseline text-slate-200">
              <span className="text-4xl font-extrabold">$0</span>
              <span className="text-slate-400 text-sm ml-1">/ month</span>
            </div>
            <p className="text-slate-400 text-xs mt-1">Ideal for evaluating voice agent conversations and testing live browser simulations.</p>
            
            <ul className="space-y-2.5 pt-3 text-xs text-slate-300">
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <span>Unlimited browser sandbox calls</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <span>Groq Llama 3.1 & Whisper models</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <span>Bulk CSV appointment upload</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <span>Basic analytics & latency stats</span>
              </li>
            </ul>
          </div>

          <div className="pt-6">
            <button
              disabled={currentPlan === 'free' || checkingOut}
              onClick={handleDowngrade}
              className={`w-full py-2.5 border rounded-xl text-xs font-semibold transition cursor-pointer ${
                currentPlan === 'free' 
                  ? 'bg-slate-800/40 border-slate-700 text-slate-400 cursor-not-allowed'
                  : 'border-slate-700 hover:border-slate-500 text-slate-300'
              }`}
            >
              {currentPlan === 'free' ? 'Current Plan' : 'Downgrade to Free'}
            </button>
          </div>
        </div>

        {/* Pro Plan */}
        <div className="glass rounded-xl p-6 border-2 border-blue-500/50 flex flex-col justify-between relative overflow-hidden bg-slate-900/30 shadow-2xl shadow-blue-900/20">
          <div className="absolute top-0 right-0 bg-blue-600 text-white text-[10px] uppercase font-bold tracking-widest px-3.5 py-1 rounded-bl-xl flex items-center gap-1">
            <Zap className="h-3 w-3 fill-white" /> Popular
          </div>

          <div className="space-y-4">
            <span className="text-xs font-bold text-blue-400 uppercase tracking-wider block">Production Ready</span>
            <h3 className="text-xl font-bold text-slate-100 flex items-center gap-1.5">
              Professional <Sparkles className="h-4 w-4 text-yellow-400 fill-yellow-400" />
            </h3>
            <div className="flex items-baseline text-slate-200">
              <span className="text-4xl font-extrabold">{annualBilling ? '$39' : '$49'}</span>
              <span className="text-slate-400 text-sm ml-1">/ month</span>
            </div>
            <p className="text-slate-400 text-xs mt-1">Designed for dental practices, salons, and auto shops processing 50+ bookings weekly.</p>
            
            <ul className="space-y-2.5 pt-3 text-xs text-slate-300">
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-400" />
                <span className="font-semibold text-slate-100">Unlimited outbound voice calls</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-400" />
                <span>24h automated campaign scheduler</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-400" />
                <span>RFC 5545 Live iCal calendar feed</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-400" />
                <span>Custom agent prompt instructions & voice</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-400" />
                <span>Post-call SMS alert delivery</span>
              </li>
            </ul>
          </div>

          <div className="pt-6">
            <button
              disabled={currentPlan === 'pro' || checkingOut}
              onClick={() => handleCheckout('pro')}
              className={`w-full py-2.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                currentPlan === 'pro' 
                  ? 'bg-blue-900/20 border border-blue-500/30 text-blue-300 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20'
              }`}
            >
              {currentPlan === 'pro' ? 'Current Plan' : checkingOut ? 'Processing...' : 'Upgrade to Professional'}
            </button>
          </div>
        </div>

        {/* Enterprise Plan */}
        <div className="glass rounded-xl p-6 border border-slate-700/50 flex flex-col justify-between relative overflow-hidden shadow-xl">
          <div className="space-y-4">
            <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider block">Multi-Location Scale</span>
            <h3 className="text-xl font-bold text-slate-100 flex items-center gap-1.5">
              Enterprise <Building2 className="h-4 w-4 text-indigo-400" />
            </h3>
            <div className="flex items-baseline text-slate-200">
              <span className="text-4xl font-extrabold">{annualBilling ? '$119' : '$149'}</span>
              <span className="text-slate-400 text-sm ml-1">/ month</span>
            </div>
            <p className="text-slate-400 text-xs mt-1">For multi-clinic chains, franchises, and high-volume medical centers requiring SLA guarantees.</p>
            
            <ul className="space-y-2.5 pt-3 text-xs text-slate-300">
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-indigo-400" />
                <span className="font-semibold text-slate-100">Everything in Pro tier</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-indigo-400" />
                <span>HMAC signed webhook CRM dispatch</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-indigo-400" />
                <span>Multi-branch calendar routing</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-indigo-400" />
                <span>Dedicated SIP trunking & phone numbers</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-indigo-400" />
                <span>99.99% uptime SLA & 24/7 dedicated support</span>
              </li>
            </ul>
          </div>

          <div className="pt-6">
            <button
              disabled={currentPlan === 'enterprise' || checkingOut}
              onClick={() => handleCheckout('enterprise')}
              className={`w-full py-2.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                currentPlan === 'enterprise' 
                  ? 'bg-indigo-900/20 border border-indigo-500/30 text-indigo-300 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20'
              }`}
            >
              {currentPlan === 'enterprise' ? 'Current Plan' : checkingOut ? 'Processing...' : 'Upgrade to Enterprise'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
