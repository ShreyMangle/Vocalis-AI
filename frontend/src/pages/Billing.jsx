import { useEffect, useState } from 'react';
import { Check, ShieldCheck, Zap, Sparkles } from 'lucide-react';

export default function Billing() {
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState(false);

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
        // Complete mock payment immediately for local MVP demo
        console.log('Simulating Stripe callback checkout...');
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
        // Redirect to real Stripe checkout
        window.location.href = data.url;
      }
    } catch (err) {
      alert(`Stripe error: ${err.message}`);
    } finally {
      setCheckingOut(false);
    }
  };

  const handleDowngrade = async () => {
    if (!confirm('Are you sure you want to cancel your Pro plan and downgrade to Free?')) return;
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

  const isPro = billing?.plan === 'pro';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Subscription Plans</h1>
        <p className="text-slate-400 text-sm">Scale your automated confirmation pipeline with Stripe billing integration.</p>
      </div>

      {/* Plan Status Banner */}
      <div className="glass rounded-xl p-5 border border-blue-500/10 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-600/10 border border-blue-500/20 rounded-xl">
            <ShieldCheck className="h-6 w-6 text-blue-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Current Account Tier</span>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-500/15 border border-blue-500/30 text-blue-400 uppercase">
                {billing?.plan} Tier
              </span>
            </div>
            <p className="text-slate-300 text-sm mt-1">
              {isPro 
                ? 'Your Pro plan is active. Enjoy unlimited outbound scheduling voice calls.'
                : 'You are on the Free trial tier. You have a monthly limit of 10 automated calls.'}
            </p>
          </div>
        </div>
        {isPro && (
          <button
            onClick={handleDowngrade}
            disabled={checkingOut}
            className="px-4 py-2 border border-slate-700 hover:border-red-500/30 text-slate-400 hover:text-red-400 text-sm font-semibold rounded-lg transition cursor-pointer"
          >
            Cancel Subscription
          </button>
        )}
      </div>

      {/* Pricing Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto pt-4">
        {/* Free Plan */}
        <div className="glass rounded-xl p-6 border border-slate-700/50 flex flex-col justify-between relative overflow-hidden">
          <div className="space-y-4">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">Starter Trial</span>
            <h3 className="text-2xl font-bold text-slate-100">Free Tier</h3>
            <div className="flex items-baseline text-slate-200">
              <span className="text-4xl font-extrabold">$0</span>
              <span className="text-slate-400 text-sm ml-1">/ month</span>
            </div>
            <p className="text-slate-400 text-xs mt-2">Perfect for evaluating the voice agent conversation flow and testing sandbox simulations.</p>
            
            <ul className="space-y-2.5 pt-4 text-sm text-slate-300">
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <span>10 live confirmation calls / month</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <span>Unlimited sandbox voice testing</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <span>Bulk CSV upload & manual trigger</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <span>Basic analytics dashboard & logs</span>
              </li>
            </ul>
          </div>

          <div className="pt-6">
            <button
              disabled={!isPro || checkingOut}
              onClick={handleDowngrade}
              className={`w-full py-2.5 border rounded-lg text-sm font-semibold transition cursor-pointer ${
                !isPro 
                  ? 'bg-slate-800/20 border-slate-700 text-slate-400 cursor-not-allowed'
                  : 'border-slate-700 hover:border-slate-500 text-slate-300'
              }`}
            >
              {!isPro ? 'Current Plan' : 'Downgrade to Free'}
            </button>
          </div>
        </div>

        {/* Pro Plan */}
        <div className="glass rounded-xl p-6 border border-blue-500/20 flex flex-col justify-between relative overflow-hidden bg-slate-900/10">
          {/* Popular Tag */}
          <div className="absolute top-0 right-0 bg-blue-600 text-white text-[10px] uppercase font-bold tracking-widest px-4 py-1 rounded-bl-lg flex items-center gap-1">
            <Zap className="h-3 w-3 fill-white" /> Recommended
          </div>

          <div className="space-y-4">
            <span className="text-xs font-bold text-blue-400 uppercase tracking-wider block">Scale Operations</span>
            <h3 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              Pro Package <Sparkles className="h-4.5 w-4.5 text-yellow-400 fill-yellow-400" />
            </h3>
            <div className="flex items-baseline text-slate-200">
              <span className="text-4xl font-extrabold">$49</span>
              <span className="text-slate-400 text-sm ml-1">/ month</span>
            </div>
            <p className="text-slate-400 text-xs mt-2">Built for clinics, salons, and shops processing over 50 bookings weekly.</p>
            
            <ul className="space-y-2.5 pt-4 text-sm text-slate-300">
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-400" />
                <span className="font-semibold text-slate-200">Unlimited automated calls</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-400" />
                <span>Automatic 24-hour scheduler daemon</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-400" />
                <span>Custom agent prompt instructions & tone</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-400" />
                <span>Live Google Calendar / Calendly integrations</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-400" />
                <span>SMS confirmation fallback delivery</span>
              </li>
            </ul>
          </div>

          <div className="pt-6">
            <button
              disabled={isPro || checkingOut}
              onClick={() => handleCheckout('pro')}
              className={`w-full py-2.5 rounded-lg text-sm font-semibold transition cursor-pointer ${
                isPro 
                  ? 'bg-blue-900/10 border border-blue-500/20 text-blue-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/10'
              }`}
            >
              {isPro ? 'Current Plan' : checkingOut ? 'Processing...' : 'Upgrade to Pro'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
