import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from '../context/AuthContext'

export default function SubscriptionPage() {
  const { user, refreshUser } = useAuth()
  const nav = useNavigate()
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')

  const handleSubscribe = async () => {
    setLoading(true)
    setStatus('')
    try {
      // Step 1: Create order
      const { data: order } = await axios.post('/api/payment/create-order')

      // Demo mode (no Razorpay keys configured)
      if (order.demo_mode) {
        // Verify the demo order directly
        await axios.post('/api/payment/verify', {
          razorpay_order_id: order.order_id,
          razorpay_payment_id: 'demo',
          razorpay_signature: 'demo'
        })
        await refreshUser()
        setStatus('success')
        setTimeout(() => nav('/'), 2000)
        return
      }

      // Step 2: Open Razorpay checkout
      const options = {
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: 'MedCode AI',
        description: 'Pro Subscription — 1 Month',
        image: 'https://i.imgur.com/3g7nmJC.png',
        order_id: order.order_id,
        handler: async (response) => {
          try {
            await axios.post('/api/payment/verify', {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            })
            await refreshUser()
            setStatus('success')
            setTimeout(() => nav('/'), 2000)
          } catch (e) {
            setStatus('error')
          }
        },
        prefill: { email: user?.email, name: user?.name },
        theme: { color: '#0D9488' },
        modal: { ondismiss: () => setLoading(false) }
      }

      const rzp = new window.Razorpay(options)
      rzp.on('payment.failed', () => { setStatus('error'); setLoading(false) })
      rzp.open()
    } catch (e) {
      setStatus('error')
      console.error(e)
    }
    setLoading(false)
  }

  if (status === 'success') {
    return (
      <div className="min-h-screen bg-[#0a0f1e] flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4">🎉</div>
          <h2 className="text-2xl font-bold text-white mb-2">Subscription Activated!</h2>
          <p className="text-teal-400">Redirecting to the app...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0a0f1e] flex items-center justify-center px-4">
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 right-20 w-72 h-72 rounded-full bg-teal-500/5 blur-3xl" />
        <div className="absolute bottom-20 left-20 w-72 h-72 rounded-full bg-indigo-500/5 blur-3xl" />
      </div>

      <div className="w-full max-w-lg relative">
        <div className="text-center mb-8">
          <button onClick={() => nav('/')} className="text-slate-500 hover:text-slate-300 text-sm mb-4 block mx-auto">
            ← Back to app
          </button>
          <h1 className="text-3xl font-bold text-white">MedCode AI Pro</h1>
          <p className="text-slate-400 mt-2">Unlock detailed reports, email delivery & more</p>
        </div>

        {/* Pricing card */}
        <div className="bg-slate-800/60 border-2 border-teal-500/60 rounded-2xl p-8 backdrop-blur mb-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="text-xs text-teal-400 font-bold uppercase tracking-wider mb-1">Monthly Plan</div>
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-bold text-white">₹1</span>
                <span className="text-slate-400 text-sm">/month</span>
              </div>
              <div className="text-xs text-slate-500 mt-1">(Introductory pricing)</div>
            </div>
            <div className="w-16 h-16 rounded-2xl bg-teal-500/20 border border-teal-500/40 flex items-center justify-center text-2xl">
              🏥
            </div>
          </div>

          <div className="space-y-3 mb-8">
            {[
              { icon: '📄', text: 'Download detailed PDF reports with full justifications' },
              { icon: '📧', text: 'Email results directly to your inbox' },
              { icon: '💬', text: 'Share via WhatsApp with one click' },
              { icon: '🔬', text: 'Full lab value extraction & analysis' },
              { icon: '⚠️', text: 'Drug interaction alerts & allergy risk assessment' },
              { icon: '✅', text: 'Anti-hallucination verified ICD-10-CM codes' },
            ].map(({ icon, text }) => (
              <div key={text} className="flex items-start gap-3">
                <span className="text-base mt-0.5">{icon}</span>
                <span className="text-sm text-slate-300">{text}</span>
              </div>
            ))}
          </div>

          {status === 'error' && (
            <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl px-4 py-3 text-sm text-rose-400 mb-4">
              Payment failed. Please try again.
            </div>
          )}

          <button
            onClick={handleSubscribe}
            disabled={loading || user?.is_subscribed}
            className={`w-full py-4 rounded-xl font-bold text-base transition-all ${
              user?.is_subscribed
                ? 'bg-emerald-600 text-white cursor-default'
                : 'bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white hover:scale-[1.02] active:scale-100'
            }`}
          >
            {user?.is_subscribed
              ? '✓ Already Subscribed'
              : loading
              ? 'Processing...'
              : 'Subscribe for ₹1'}
          </button>

          <p className="text-center text-xs text-slate-500 mt-3">
            Secure payment via Razorpay · Cancel anytime
          </p>
        </div>

        <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-4">
          <div className="text-xs text-slate-500 text-center">
            🔒 Payments processed securely by Razorpay · Test mode uses test cards
          </div>
        </div>
      </div>
    </div>
  )
}
