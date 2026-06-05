import React, { useState, useRef, useCallback } from 'react'
import { Routes, Route, useNavigate, Navigate } from 'react-router-dom'
import axios from 'axios'
import { useAuth } from './context/AuthContext'
import LoginPage from './pages/LoginPage'
import SubscriptionPage from './pages/SubscriptionPage'

const API = '/api'
const CONF_COLOR = { high:'text-emerald-400', medium:'text-amber-400', low:'text-rose-400' }
const CONF_BG    = { high:'bg-emerald-400', medium:'bg-amber-400', low:'bg-rose-400' }
const CONF_PCT   = { high:90, medium:60, low:35 }
const FLAG_CLS   = { CRITICAL:'border-rose-500 bg-rose-500/10 text-rose-300', WARNING:'border-amber-500 bg-amber-500/10 text-amber-300', INFO:'border-blue-500 bg-blue-500/10 text-blue-300' }
const INT_CLS    = { CONTRAINDICATED:'border-rose-600 bg-rose-600/10 text-rose-300', MAJOR:'border-orange-500 bg-orange-500/10 text-orange-300', MODERATE:'border-amber-500 bg-amber-500/10 text-amber-300' }

// ── Persistent localStorage hook — changes survive refresh/close ──────
function useLocalState(key, initial) {
  const [val, setVal] = useState(() => {
    try {
      const saved = localStorage.getItem('medcode_' + key)
      return saved ? JSON.parse(saved) : initial
    } catch { return initial }
  })
  const setAndSave = useCallback((update) => {
    setVal(prev => {
      const next = typeof update === 'function' ? update(prev) : update
      try { localStorage.setItem('medcode_' + key, JSON.stringify(next)) } catch {}
      return next
    })
  }, [key])
  return [val, setAndSave]
}

// ── Sidebar ───────────────────────────────────────────────────────────
function Sidebar({ view, setView, user }) {
  const nav = useNavigate()
  const groups = [
    { title:'Top Level', items:[{id:'Home',icon:'🏠',label:'Home'},{id:'Inbox',icon:'📥',label:'Inbox'}] },
    { title:'Applications', items:[
      {id:'Doctor',icon:'👨‍⚕️',label:'Doctor'},
      {id:'Patient',icon:'🩺',label:'Code Document'},
      {id:'Departments',icon:'🏢',label:'Departments'},
      {id:'Schedule',icon:'📅',label:'Schedule'},
      {id:'Report',icon:'📊',label:'Reports'},
    ]},
    { title:'Account', items:[{id:'Payment',icon:'💳',label:'Billing'}] },
  ]
  return (
    <aside className="w-60 bg-[#0d1326] border-r border-slate-800 flex flex-col h-screen sticky top-0 overflow-y-auto shrink-0 z-40">
      <div className="p-5 border-b border-slate-800/50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-teal-500/20 border border-teal-500/40 flex items-center justify-center text-lg">🏥</div>
          <div>
            <div className="font-bold text-white text-sm">MedCode AI</div>
            <div className="text-xs text-teal-400">ICD-10 Assistant</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-5">
        {groups.map(g => (
          <div key={g.title}>
            <div className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2 px-2">{g.title}</div>
            <div className="space-y-0.5">
              {g.items.map(item => (
                <button key={item.id} onClick={() => setView(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${view===item.id?'bg-teal-500/15 text-teal-300 font-semibold border border-teal-500/25':'text-slate-400 hover:text-slate-200 hover:bg-slate-800/70 border border-transparent'}`}>
                  <span>{item.icon}</span><span>{item.label}</span>
                  {item.id==='Patient'&&<span className="ml-auto w-2 h-2 rounded-full bg-emerald-400 pulse-dot"/>}
                </button>
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="p-3 border-t border-slate-800/50 space-y-2">
        {user ? (
          <>
            {!user.is_subscribed && (
              <button onClick={()=>nav('/subscribe')} className="w-full py-2 bg-gradient-to-r from-teal-600 to-teal-500 text-white rounded-xl text-xs font-bold hover:from-teal-500 hover:to-teal-400 transition-all shadow-lg shadow-teal-500/20">
                ⭐ Upgrade to Pro — ₹1
              </button>
            )}
            <div className="flex items-center gap-3 bg-slate-800/40 p-2.5 rounded-xl border border-slate-700/50">
              <div className="w-8 h-8 rounded-full bg-teal-500/20 flex items-center justify-center text-teal-300 font-bold text-xs border border-teal-500/30">
                {user.name?.charAt(0)?.toUpperCase()||'U'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-slate-200 font-semibold truncate">{user.name}</div>
                <div className={`text-xs truncate ${user.is_subscribed?'text-teal-400':'text-slate-500'}`}>{user.is_subscribed?'✓ Pro Active':'Free Plan'}</div>
              </div>
            </div>
          </>
        ) : (
          <button onClick={()=>nav('/login')} className="w-full py-2.5 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-xs font-bold transition-colors">Sign In / Register</button>
        )}
      </div>
    </aside>
  )
}

// ── CodeCard ──────────────────────────────────────────────────────────
function CodeCard({ code, isPrincipal=false }) {
  const [open, setOpen] = useState(isPrincipal)
  const conf = code.confidence||'medium'
  return (
    <div className={`slide-in rounded-xl border cursor-pointer transition-all ${isPrincipal?'border-teal-500/60 bg-gradient-to-br from-teal-900/30 to-slate-800/50':'border-slate-700 bg-slate-800/50 hover:border-slate-500'}`} onClick={()=>setOpen(!open)}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {isPrincipal&&<span className="shrink-0 text-xs font-bold px-2 py-0.5 rounded-full bg-teal-500/20 text-teal-300 border border-teal-500/40">PRINCIPAL</span>}
            <span className="font-mono font-bold text-teal-300 text-base shrink-0">{code.code}</span>
            <span className="text-sm text-slate-200 truncate">{code.description}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {!code.verified&&<span className="text-xs px-1.5 py-0.5 bg-rose-500/20 text-rose-400 rounded border border-rose-500/30">REVIEW</span>}
            <span className={`text-xs font-bold ${CONF_COLOR[conf]}`}>{conf.toUpperCase()}</span>
            <svg className={`w-4 h-4 text-slate-400 transition-transform ${open?'rotate-180':''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/></svg>
          </div>
        </div>
        <div className="mt-3 h-1 bg-slate-700 rounded-full overflow-hidden">
          <div className={`h-full rounded-full confidence-bar ${CONF_BG[conf]}`} style={{width:`${CONF_PCT[conf]}%`}}/>
        </div>
        <div className="mt-2 flex gap-2 flex-wrap">
          {code.chapter&&<span className="text-xs px-2 py-0.5 bg-slate-700/60 text-slate-400 rounded">{code.chapter}</span>}
          {code.category&&<span className="text-xs px-2 py-0.5 bg-slate-700/60 text-slate-400 rounded">{code.category}</span>}
          {code.relationship&&<span className="text-xs px-2 py-0.5 bg-slate-700/40 text-slate-500 rounded capitalize">{code.relationship}</span>}
        </div>
      </div>
      {open&&(
        <div className="px-4 pb-4 border-t border-slate-700/50 pt-3 space-y-3">
          {code.justification&&<div><div className="text-xs font-bold text-teal-400 mb-1">Clinical Justification</div><p className="text-sm text-slate-300 leading-relaxed">{code.justification}</p></div>}
          {code.coding_notes&&<div><div className="text-xs font-bold text-blue-400 mb-1">ICD-10-CM Coding Notes</div><p className="text-sm text-slate-400 leading-relaxed">{code.coding_notes}</p></div>}
          {code.warning&&<div className="text-xs text-rose-400 bg-rose-500/10 rounded px-2 py-1.5 border border-rose-500/20">⚠️ {code.warning}</div>}
        </div>
      )}
    </div>
  )
}

// ── SearchPanel ───────────────────────────────────────────────────────
function SearchPanel() {
  const [q,setQ]=useState(''); const [results,setResults]=useState([]); const [busy,setBusy]=useState(false)
  const run=async()=>{if(!q.trim())return;setBusy(true);try{const r=await axios.get(`${API}/search-codes?q=${encodeURIComponent(q)}&limit=15`);setResults(r.data.results||[])}catch{}setBusy(false)}
  return (
    <div className="glass rounded-xl p-4 space-y-3">
      <h3 className="text-sm font-semibold text-slate-300">🔍 ICD-10 Code Lookup</h3>
      <div className="flex gap-2">
        <input className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-teal-500 transition-colors" placeholder="diabetes, E11, pneumonia..." value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&run()}/>
        <button onClick={run} className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-sm font-medium transition-colors">{busy?'...':'Search'}</button>
      </div>
      {results.length>0&&<div className="space-y-1 max-h-56 overflow-y-auto">{results.map(r=><div key={r.code} className="flex gap-2 p-2 rounded-lg hover:bg-slate-700/50 transition-colors"><span className="font-mono text-teal-300 text-xs shrink-0 pt-0.5">{r.code}</span><span className="text-xs text-slate-300 leading-snug">{r.description}</span></div>)}</div>}
    </div>
  )
}

// ── VitalsPanel ───────────────────────────────────────────────────────
function VitalsPanel({ vitals, labs }) {
  const ll={hb:'Hemoglobin',wbc:'WBC',platelets:'Platelets',creatinine:'Creatinine',hba1c:'HbA1c',egfr:'eGFR',sodium:'Sodium',potassium:'Potassium',alt:'ALT',ast:'AST',bilirubin:'Bilirubin',albumin:'Albumin',tsh:'TSH',cholesterol:'Cholesterol',ldl:'LDL',hdl:'HDL',triglycerides:'Triglycerides',inr:'INR',crp:'CRP',psa:'PSA',troponin:'Troponin'}
  const fmtV=(k,v)=>{if(k==='bp')return`${v.systolic}/${v.diastolic} mmHg`;const u={hr:'bpm',temp:'°C',spo2:'%',weight:'kg',height:'cm',bmi:'kg/m²',glucose:'mg/dL'};return`${v}${u[k]?' '+u[k]:''}`}
  const hasV=vitals&&Object.keys(vitals).length>0; const hasL=labs&&Object.keys(labs).length>0
  if(!hasV&&!hasL)return null
  return (
    <div className="glass rounded-xl p-4 space-y-3">
      <h3 className="text-sm font-semibold text-slate-300">📊 Extracted Clinical Values</h3>
      {hasV&&<><div className="text-xs text-teal-400 font-semibold uppercase tracking-wider">Vital Signs</div><div className="grid grid-cols-2 gap-2">{Object.entries(vitals).map(([k,v])=><div key={k} className="bg-slate-800/60 rounded-lg px-3 py-2 border border-slate-700/50"><div className="text-xs text-slate-500 uppercase tracking-wide">{k==='bp'?'Blood Pressure':k==='spo2'?'SpO₂':k.toUpperCase()}</div><div className="text-sm font-mono font-semibold text-slate-200 mt-0.5">{fmtV(k,v)}</div></div>)}</div></>}
      {hasL&&<><div className="text-xs text-teal-400 font-semibold uppercase tracking-wider">Lab Values</div><div className="grid grid-cols-2 gap-2">{Object.entries(labs).map(([k,v])=><div key={k} className="bg-slate-800/60 rounded-lg px-3 py-2 border border-slate-700/50"><div className="text-xs text-slate-500">{ll[k]||k.toUpperCase()}</div><div className="text-sm font-mono font-semibold text-slate-200 mt-0.5">{v}</div></div>)}</div></>}
    </div>
  )
}

// ── AllergyRisk ───────────────────────────────────────────────────────
function AllergyRisk({ data }) {
  if(!data)return null
  const{cross_reactivity_risks=[],has_documented_allergy,note}=data
  if(!has_documented_allergy&&cross_reactivity_risks.length===0)return null
  return(
    <div className="rounded-xl p-4 border border-amber-500/40 bg-amber-500/5 space-y-2">
      <h3 className="text-sm font-bold text-amber-400">⚠️ Allergy Risk Notice</h3>
      {cross_reactivity_risks.map((r,i)=><div key={i} className="text-xs text-amber-300">• Prescribed <b>{r.drug_found}</b> — verify <b>{r.class}</b> allergy history before dispensing</div>)}
      {note&&<p className="text-xs text-slate-400 italic">{note}</p>}
    </div>
  )
}

// ── ShareBar ──────────────────────────────────────────────────────────
function ShareBar({ result, isSubscribed }) {
  const nav=useNavigate()
  const [eLoad,setELoad]=useState(false); const [eSent,setESent]=useState(false); const [email,setEmail]=useState(''); const [showE,setShowE]=useState(false); const [pLoad,setPLoad]=useState(false)
  const guard=(fn)=>{if(!isSubscribed){nav('/subscribe');return};fn()}
  const pdf=async()=>{setPLoad(true);try{const r=await axios.post(`${API}/report/download`,{analysis:result},{responseType:'blob'});const u=URL.createObjectURL(new Blob([r.data],{type:'application/pdf'}));const a=document.createElement('a');a.href=u;a.download='MedCode_Report.pdf';a.click();URL.revokeObjectURL(u)}catch(e){if(e.response?.data?.code==='SUBSCRIPTION_REQUIRED')nav('/subscribe');else alert('PDF failed: '+(e.response?.data?.error||e.message))}setPLoad(false)}
  const wa=()=>{const c=result?.coding||{},p=c.principal_diagnosis,s=c.secondary_diagnoses||[];let t=`🏥 *MedCode AI — Clinical Coding Report*\n\n*Document:* ${(result.document_type||'').replace(/_/g,' ')}\n`;if(result.patient_info?.age)t+=`*Patient:* ${result.patient_info.age}y ${result.patient_info.gender||''}\n`;if(p){t+=`\n*Principal:*\n📌 ${p.code} — ${p.description}\n_${p.confidence?.toUpperCase()}_\n`;if(p.justification)t+=`_${p.justification}_\n`}if(s.length>0){t+=`\n*Secondary:*\n`;s.forEach(c=>{t+=`• ${c.code} — ${c.description} (${c.confidence})\n`})}const fl=result.abnormal_flags||[];if(fl.length>0){t+=`\n*⚠️ Alerts:*\n`;fl.forEach(f=>{t+=`${f.type==='CRITICAL'?'🚨':'⚠️'} ${f.label}: ${f.value}\n`})}t+=`\n_MedCode AI — Verify with certified medical coder_`;window.open(`https://wa.me/?text=${encodeURIComponent(t)}`,'_blank')}
  const sendEmail=async()=>{if(!email.trim())return;setELoad(true);try{const r=await axios.post(`${API}/report/email`,{email,analysis:result});if(r.data.success){setESent(true);setShowE(false)}else alert('Email failed: '+r.data.error)}catch(e){if(e.response?.data?.code==='SUBSCRIPTION_REQUIRED')nav('/subscribe');else alert(e.response?.data?.error||'Failed')}setELoad(false)}
  const tsv=()=>{const codes=[result?.coding?.principal_diagnosis,...(result?.coding?.secondary_diagnoses||[])].filter(Boolean);const blob=new Blob(['Code\tDescription\tConfidence\tJustification\n'+codes.map(c=>`${c.code}\t${c.description}\t${c.confidence}\t${c.justification||''}`).join('\n')],{type:'text/tab-separated-values'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='icd10_codes.tsv';a.click()}
  return (
    <div className="glass rounded-xl p-5 space-y-4 border border-slate-700/50">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-300">📤 Share & Export</h3>
        {isSubscribed?<span className="text-xs px-2.5 py-1 bg-teal-500/20 text-teal-400 border border-teal-500/30 rounded-full font-semibold">✓ Pro</span>:<button onClick={()=>nav('/subscribe')} className="text-xs px-2.5 py-1 bg-teal-600/20 text-teal-400 border border-teal-500/40 rounded-full hover:bg-teal-600/40 transition-colors font-semibold">🔒 Upgrade for Pro features</button>}
      </div>
      <button onClick={tsv} className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium transition-colors"><span>📊</span><span>Export TSV</span><span className="ml-auto text-xs text-emerald-400 font-semibold">FREE</span></button>
      <div className="space-y-2">
        <div className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Pro Features</div>
        <button onClick={()=>guard(pdf)} disabled={pLoad} className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${isSubscribed?'bg-slate-700 hover:bg-slate-600 text-slate-200':'bg-slate-800/50 text-slate-500 border border-dashed border-slate-600 hover:border-teal-500/50'}`}><span>📄</span><span>{pLoad?'Generating...':'Download PDF Report'}</span>{!isSubscribed&&<span className="ml-auto text-xs text-teal-500 font-semibold">🔒 PRO</span>}</button>
        <button onClick={()=>guard(wa)} className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${isSubscribed?'bg-green-700/30 hover:bg-green-700/50 text-green-300':'bg-slate-800/50 text-slate-500 border border-dashed border-slate-600 hover:border-teal-500/50'}`}><span>💬</span><span>Share via WhatsApp</span>{!isSubscribed&&<span className="ml-auto text-xs text-teal-500 font-semibold">🔒 PRO</span>}</button>
        <button onClick={()=>guard(()=>setShowE(!showE))} className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${isSubscribed?'bg-blue-700/30 hover:bg-blue-700/50 text-blue-300':'bg-slate-800/50 text-slate-500 border border-dashed border-slate-600 hover:border-teal-500/50'}`}><span>📧</span><span>{eSent?'✓ Email Sent!':'Email Full Report'}</span>{!isSubscribed&&<span className="ml-auto text-xs text-teal-500 font-semibold">🔒 PRO</span>}</button>
        {showE&&isSubscribed&&<div className="flex gap-2 slide-in"><input className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors" placeholder="Enter email address..." value={email} onChange={e=>setEmail(e.target.value)} onKeyDown={e=>e.key==='Enter'&&sendEmail()}/><button onClick={sendEmail} disabled={eLoad} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors">{eLoad?'Sending...':'Send'}</button></div>}
      </div>
      {!isSubscribed&&<button onClick={()=>nav('/subscribe')} className="w-full py-3 bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-500 hover:to-teal-400 text-white rounded-xl text-sm font-bold transition-all shadow-lg shadow-teal-500/20">⭐ Unlock All Pro Features — ₹1/month</button>}
    </div>
  )
}

// ── PatientView ───────────────────────────────────────────────────────
function PatientView({ isSubscribed }) {
  const [dragging,setDragging]=useState(false); const [loading,setLoading]=useState(false); const [result,setResult]=useState(null); const [error,setError]=useState(''); const [textInput,setTextInput]=useState(''); const [mode,setMode]=useState('file')
  const fileRef=useRef(null); const resultRef=useRef(null)
  const analyze=useCallback(async(data)=>{setLoading(true);setError('');setResult(null);try{const isForm=data instanceof FormData;const r=await axios.post(`${API}/analyze`,data,{headers:isForm?{}:{'Content-Type':'application/json'},timeout:120000});setResult(r.data);setTimeout(()=>resultRef.current?.scrollIntoView({behavior:'smooth'}),100)}catch(e){setError(e.response?.data?.error||e.message||'Analysis failed')}setLoading(false)},[])
  const handleFile=useCallback((f)=>{if(!f)return;const fd=new FormData();fd.append('file',f);analyze(fd)},[analyze])
  const principal=result?.coding?.principal_diagnosis; const secondary=result?.coding?.secondary_diagnoses||[]; const excluded=result?.coding?.excluded_considerations||[]; const flags=result?.abnormal_flags||[]; const interactions=result?.drug_interactions||[]
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="space-y-4">
        <div className="glass rounded-2xl p-5 space-y-4">
          <div><h2 className="text-base font-bold text-white">Analyze Medical Document</h2><p className="text-xs text-slate-400 mt-0.5">PDF · Image (JPG/PNG) · DOCX · Plain text</p></div>
          <div className="flex bg-slate-900 rounded-xl p-1 gap-1">{['file','text'].map(m=><button key={m} onClick={()=>setMode(m)} className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all ${mode===m?'bg-teal-600 text-white shadow-lg':'text-slate-400 hover:text-white'}`}>{m==='file'?'📎 Upload File':'✏️ Paste Text'}</button>)}</div>
          {mode==='file'?(
            <div className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${dragging?'border-teal-400 bg-teal-400/10':'border-slate-600 hover:border-teal-500/60 hover:bg-slate-800/40'}`} onDragOver={e=>{e.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);handleFile(e.dataTransfer.files[0])}} onClick={()=>fileRef.current?.click()}>
              <input ref={fileRef} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,.docx,.txt" onChange={e=>handleFile(e.target.files[0])}/>
              <div className="text-4xl mb-3">📄</div>
              <p className="text-sm text-slate-200 font-semibold">Drop or click to upload</p>
              <p className="text-xs text-slate-500 mt-2">Prescription · Lab Report · Discharge Summary · Clinical Note</p>
            </div>
          ):(
            <div className="space-y-2">
              <textarea className="w-full h-40 bg-slate-900 border border-slate-600 rounded-xl px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-teal-500 resize-none transition-colors" placeholder="Paste any clinical text here..." value={textInput} onChange={e=>setTextInput(e.target.value)}/>
              <button onClick={()=>{if(textInput.trim())analyze({text:textInput})}} disabled={loading||!textInput.trim()} className="w-full py-3 bg-teal-600 hover:bg-teal-500 disabled:opacity-40 text-white rounded-xl text-sm font-bold transition-colors">Analyze Text</button>
            </div>
          )}
          {loading&&<div className="flex items-center gap-3 py-2"><div className="w-5 h-5 border-2 border-teal-400 border-t-transparent rounded-full animate-spin shrink-0"/><div><div className="text-sm text-teal-300 font-semibold">Analyzing...</div><div className="text-xs text-slate-500">OCR → NLP → BM25 → LLM</div></div></div>}
          {error&&<div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-3 text-sm text-rose-400">{error}</div>}
        </div>
        <SearchPanel/>
        <p className="text-xs text-slate-600 px-1 leading-relaxed">⚕️ Coding assistance only. Verify all codes with a certified medical coder (CCS/CPC).</p>
      </div>
      <div className="lg:col-span-2 space-y-4" ref={resultRef}>
        {!result&&!loading&&(
          <div className="flex flex-col items-center justify-center h-80 text-center">
            <div className="text-6xl mb-4 opacity-20">🩺</div>
            <p className="text-slate-400 text-base font-medium mb-1">Upload any medical document</p>
            <p className="text-slate-500 text-sm max-w-sm">Get accurate ICD-10-CM codes with clinical justifications instantly</p>
            <div className="mt-6 grid grid-cols-2 gap-3 w-full max-w-md">{[['💊','Prescriptions'],['🏨','Discharge Summaries'],['🔬','Lab Reports'],['📋','Clinical Notes']].map(([i,l])=><div key={l} className="glass rounded-xl py-3 px-4 text-sm text-slate-400 flex items-center gap-2">{i} {l}</div>)}</div>
          </div>
        )}
        {result&&(
          <div className="space-y-4 slide-in">
            <div className="glass rounded-xl p-4 flex flex-wrap gap-4 text-xs border border-slate-700/50">
              <div><span className="text-slate-500 uppercase tracking-wider text-xs">Document</span><div className="text-slate-200 font-semibold mt-0.5 capitalize">{(result.document_type||'').replace(/_/g,' ')}</div></div>
              {result.patient_info?.age&&<div><span className="text-slate-500 uppercase tracking-wider text-xs">Patient</span><div className="text-slate-200 font-semibold mt-0.5 capitalize">{result.patient_info.age}y {result.patient_info.gender||''}{result.patient_info.pregnant?' · Pregnant':''}</div></div>}
              <div><span className="text-slate-500 uppercase tracking-wider text-xs">Codes</span><div className="text-teal-400 font-bold text-lg mt-0.5">{result.coding?.total_codes||0}</div></div>
              <div><span className="text-slate-500 uppercase tracking-wider text-xs">Verified</span><div className={`font-semibold mt-0.5 ${result.coding?.all_verified?'text-emerald-400':'text-amber-400'}`}>{result.coding?.all_verified?'✓ All verified':'⚠ Review req.'}</div></div>
              {result.extraction?.ocr_confidence<1&&<div><span className="text-slate-500 uppercase tracking-wider text-xs">OCR Conf.</span><div className="text-amber-400 font-semibold mt-0.5">{Math.round(result.extraction.ocr_confidence*100)}%</div></div>}
            </div>
            {flags.filter(f=>f.type==='CRITICAL').length>0&&<div className="border border-rose-600/60 bg-rose-600/10 rounded-xl p-4 space-y-2"><div className="text-sm font-bold text-rose-400">🚨 Critical Clinical Alerts</div>{flags.filter(f=>f.type==='CRITICAL').map((f,i)=><div key={i} className="flex items-center gap-3 text-sm"><span className="text-rose-300 font-semibold">{f.label}</span><span className="text-rose-400 font-mono text-xs bg-rose-500/10 px-2 py-0.5 rounded">{f.value}</span></div>)}</div>}
            {interactions.length>0&&<div className="glass rounded-xl p-4 space-y-3"><h3 className="text-sm font-bold text-orange-300">⚠️ Drug Interaction Alerts</h3>{interactions.map((ia,i)=><div key={i} className={`rounded-xl p-3 border ${INT_CLS[ia.severity]}`}><div className="flex items-center gap-2 mb-1.5"><span className="text-xs font-bold px-2 py-0.5 rounded-full bg-current/20 border border-current/30">{ia.severity}</span><span className="text-xs font-mono font-semibold">{ia.drugs?.join(' + ')}</span></div><p className="text-xs leading-relaxed">{ia.message}</p><p className="text-xs mt-1.5 font-bold opacity-80">{ia.action}</p></div>)}</div>}
            <AllergyRisk data={result.allergy_risk}/>
            {flags.filter(f=>f.type!=='CRITICAL').length>0&&<div className="glass rounded-xl p-4 space-y-2"><h3 className="text-sm font-semibold text-slate-300">⚡ Clinical Flags</h3><div className="flex flex-wrap gap-2">{flags.filter(f=>f.type!=='CRITICAL').map((f,i)=><span key={i} className={`text-xs px-2.5 py-1.5 rounded-lg border font-medium ${FLAG_CLS[f.type]}`}>{f.label} · {f.value}</span>)}</div></div>}
            {principal&&<div className="space-y-2"><h3 className="text-sm font-bold text-teal-300 px-1">Principal Diagnosis</h3><CodeCard code={principal} isPrincipal/></div>}
            {secondary.length>0&&<div className="space-y-2"><h3 className="text-sm font-semibold text-slate-300 px-1">Secondary Diagnoses <span className="text-xs text-slate-500 font-normal ml-1">{secondary.length} codes</span></h3>{secondary.map((c,i)=><CodeCard key={c.code+i} code={c}/>)}</div>}
            <VitalsPanel vitals={result.vitals} labs={result.labs}/>
            {result.medications?.length>0&&<div className="glass rounded-xl p-4"><h3 className="text-xs font-bold text-teal-400 uppercase tracking-wider mb-3">💊 Medications</h3><div className="flex flex-wrap gap-2">{result.medications.map(m=><span key={m} className="text-xs px-3 py-1.5 bg-slate-800 text-slate-300 rounded-full border border-slate-600 capitalize font-medium">{m}</span>)}</div></div>}
            {result.coding?.coding_summary&&<div className="glass rounded-xl p-4 space-y-3"><h3 className="text-sm font-bold text-slate-200">📝 Coding Summary</h3><p className="text-sm text-slate-400 leading-relaxed">{result.coding.coding_summary}</p>{result.coding.documentation_gaps?.length>0&&<><div className="text-xs text-amber-400 font-bold uppercase tracking-wider mb-2">Documentation Gaps</div><ul className="space-y-1.5">{result.coding.documentation_gaps.map((g,i)=><li key={i} className="text-xs text-slate-400 flex gap-2"><span className="text-amber-500 shrink-0">·</span>{g}</li>)}</ul></>}{result.coding.query_for_physician&&<><div className="text-xs text-blue-400 font-bold uppercase tracking-wider mb-2">🩺 Query for Physician</div><p className="text-xs text-slate-400 leading-relaxed bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">{result.coding.query_for_physician}</p></>}</div>}
            {excluded.length>0&&<div className="glass rounded-xl p-4"><h3 className="text-sm font-semibold text-slate-400 mb-3">Considered but Excluded</h3>{excluded.map((e,i)=><div key={i} className="flex gap-3 text-xs mb-2"><span className="font-mono text-slate-500 shrink-0">{e.code}</span><span className="text-slate-500">{e.reason_excluded}</span></div>)}</div>}
            <ShareBar result={result} isSubscribed={isSubscribed}/>
          </div>
        )}
      </div>
    </div>
  )
}

// ── HomeView ──────────────────────────────────────────────────────────
function HomeView() {
  const [stats,setStats]=useLocalState('home_stats',[{label:'Total Scans',value:1248,change:'+12%',color:'text-teal-400'},{label:'High Confidence',value:94,isPercent:true,change:'+2.1%',color:'text-emerald-400'},{label:'Critical Alerts',value:24,change:'-5',color:'text-rose-400'},{label:'Pending Review',value:18,change:'+3',color:'text-amber-400'}])
  const [activity,setActivity]=useLocalState('home_activity',[{id:1,time:'10 mins ago',action:'Automated scan completed for Patient #8832',type:'info'},{id:2,time:'1 hr ago',action:'Critical interaction detected in Prescription #992',type:'alert'},{id:3,time:'2 hrs ago',action:'Dr. Smith updated diagnostic codes for Patient #771',type:'success'},{id:4,time:'3 hrs ago',action:'System backup completed successfully',type:'info'}])
  const refresh=()=>{setStats(s=>s.map(x=>({...x,value:x.isPercent?Math.min(100,x.value+Math.floor(Math.random()*3)):x.value+Math.floor(Math.random()*10)})));setActivity(a=>[{id:Date.now(),time:'Just now',action:'Dashboard refreshed',type:'info'},...a.slice(0,3)])}
  return (
    <div className="space-y-6 slide-in">
      <div className="flex items-center justify-between"><h2 className="text-2xl font-bold text-white">Dashboard Overview</h2><button onClick={refresh} className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors flex items-center gap-2">🔄 Refresh</button></div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">{stats.map(s=><div key={s.label} className="glass p-5 rounded-xl border border-slate-700/50"><div className="text-slate-400 text-sm">{s.label}</div><div className="flex items-end justify-between mt-2"><div className={`text-3xl font-bold ${s.color}`}>{s.value}{s.isPercent?'%':''}</div><div className="text-xs text-slate-500 mb-1">{s.change}</div></div></div>)}</div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass rounded-xl p-5 md:col-span-2"><h3 className="text-slate-200 font-semibold mb-4">Recent Activity</h3><div className="space-y-3">{activity.map(a=><div key={a.id} className="flex items-center gap-3 text-sm"><div className={`w-2 h-2 rounded-full shrink-0 ${a.type==='alert'?'bg-rose-400':a.type==='success'?'bg-emerald-400':'bg-blue-400'}`}/><span className="text-slate-300 flex-1">{a.action}</span><span className="text-slate-500 text-xs shrink-0">{a.time}</span></div>)}</div></div>
        <div className="glass rounded-xl p-5"><h3 className="text-slate-200 font-semibold mb-4">System Status</h3><div className="space-y-4">{[['NLP Engine',100,'teal'],['OCR Service',95,'teal'],['LLM (Groq)',90,'emerald'],['BM25 Index',100,'blue']].map(([n,p,c])=><div key={n}><div className="flex justify-between text-xs mb-1.5"><span className="text-slate-400">{n}</span><span className={`text-${c}-400 font-medium`}>Online</span></div><div className="h-1.5 bg-slate-800 rounded-full overflow-hidden"><div className={`h-full bg-${c}-500 rounded-full`} style={{width:`${p}%`}}/></div></div>)}</div></div>
      </div>
    </div>
  )
}

// ── InboxView ─────────────────────────────────────────────────────────
function InboxView() {
  const [tab,setTab]=useState('all'); const [composing,setComposing]=useState(false); const [to,setTo]=useState(''); const [subj,setSubj]=useState(''); const [body,setBody]=useState('')
  const [msgs,setMsgs]=useLocalState('inbox_msgs',[{id:1,sender:'Dr. Adams',subj:'Review Patient #10292',time:'10:30 AM',read:false,type:'normal'},{id:2,sender:'System',subj:'ICD-10 Update Available',time:'Yesterday',read:true,type:'alert'},{id:3,sender:'Billing Dept',subj:'Missing codes for #9921',time:'Yesterday',read:true,type:'normal'},{id:4,sender:'Pharmacy',subj:'Contraindication Alert #882',time:'Mon',read:false,type:'alert'}])
  const filtered=msgs.filter(m=>tab==='unread'?!m.read:tab==='alerts'?m.type==='alert':true); const unreadCount=msgs.filter(m=>!m.read).length
  const send=()=>{setMsgs(prev=>[{id:Date.now(),sender:`To: ${to||'Unknown'}`,subj:subj||'(No Subject)',time:'Just now',read:true,type:'normal'},...prev]);setComposing(false);setTo('');setSubj('');setBody('')}
  return (
    <div className="space-y-6 slide-in">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3"><h2 className="text-2xl font-bold text-white">Inbox</h2>{unreadCount>0&&<span className="text-xs px-2 py-0.5 bg-teal-500/20 text-teal-400 border border-teal-500/30 rounded-full font-bold">{unreadCount} unread</span>}</div>
        <button onClick={()=>setComposing(!composing)} className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-semibold transition-colors">{composing?'✕ Cancel':'✉️ Compose'}</button>
      </div>
      {composing&&<div className="glass p-5 rounded-xl space-y-3 slide-in border border-teal-500/20">
        <h3 className="text-sm font-semibold text-slate-300">New Message</h3>
        <input value={to} onChange={e=>setTo(e.target.value)} placeholder="To: (e.g. Dr. Smith)" className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-teal-500 text-slate-200 transition-colors"/>
        <input value={subj} onChange={e=>setSubj(e.target.value)} placeholder="Subject" className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-teal-500 text-slate-200 transition-colors"/>
        <textarea value={body} onChange={e=>setBody(e.target.value)} placeholder="Message..." className="w-full h-28 bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-teal-500 text-slate-200 resize-none transition-colors"/>
        <div className="flex justify-end gap-2"><button onClick={()=>setComposing(false)} className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-xl text-sm font-medium transition-colors">Cancel</button><button onClick={send} className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-semibold transition-colors">Send</button></div>
      </div>}
      <div className="flex gap-1 border-b border-slate-800">{['all','unread','alerts'].map(t=><button key={t} onClick={()=>setTab(t)} className={`px-4 py-2.5 text-sm capitalize font-medium transition-colors border-b-2 ${tab===t?'border-teal-400 text-teal-300':'border-transparent text-slate-400 hover:text-slate-200'}`}>{t}{t==='unread'&&unreadCount>0?` (${unreadCount})`:''}</button>)}</div>
      <div className="glass rounded-xl divide-y divide-slate-800/50 overflow-hidden">
        {filtered.length===0&&<div className="p-10 text-center text-slate-500">No messages here.</div>}
        {filtered.map(m=><div key={m.id} onClick={()=>setMsgs(prev=>prev.map(x=>x.id===m.id?{...x,read:true}:x))} className={`p-4 flex items-center gap-4 cursor-pointer hover:bg-slate-800/40 transition-colors group ${!m.read?'bg-slate-800/20':''}`}>
          <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${!m.read?(m.type==='alert'?'bg-rose-400':'bg-teal-400'):'bg-slate-700'}`}/>
          <div className="flex-1 min-w-0">
            <div className="flex justify-between items-center mb-0.5"><span className={`text-sm truncate ${!m.read?'font-bold text-slate-200':'text-slate-400'}`}>{m.sender}</span><span className="text-xs text-slate-500 shrink-0 ml-2">{m.time}</span></div>
            <div className={`text-sm truncate ${!m.read?(m.type==='alert'?'text-rose-300 font-semibold':'text-teal-300 font-semibold'):'text-slate-300'}`}>{m.subj}</div>
          </div>
          <button onClick={e=>{e.stopPropagation();setMsgs(prev=>prev.filter(x=>x.id!==m.id))}} className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-500 hover:text-rose-400 transition-all shrink-0 rounded-lg hover:bg-rose-500/10">🗑️</button>
        </div>)}
      </div>
    </div>
  )
}

// ── DoctorView ────────────────────────────────────────────────────────
function DoctorView() {
  const [cases,setCases]=useLocalState('doctor_cases',[{id:1083,status:'Needs Review',time:'Today, 08:30 AM'},{id:9382,status:'Pending Lab',time:'Yesterday'},{id:1923,status:'Reviewed',time:'Yesterday'}])
  const [drafts,setDrafts]=useLocalState('doctor_drafts',[{id:1,title:'Discharge Summary Draft',time:'Last edited 2 hours ago',content:''},{id:2,title:'Surgical Note - Appendectomy',time:'Last edited yesterday',content:''}])
  const [editing,setEditing]=useState(null); const [editContent,setEditContent]=useState('')
  const openEdit=(d)=>{setEditing(d);setEditContent(d.content||`PATIENT HISTORY:\n\nCLINICAL FINDINGS:\n\nASSESSMENT:\n\nPLAN:\n`)}
  const saveEdit=()=>{setDrafts(prev=>prev.map(d=>d.id===editing.id?{...d,content:editContent,time:'Just now'}:d));setEditing(null)}
  const updateTitle=(id,val)=>setDrafts(prev=>prev.map(d=>d.id===id?{...d,title:val}:d))
  return (
    <div className="space-y-6 slide-in">
      <h2 className="text-2xl font-bold text-white">Physician Workflow</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass p-5 rounded-xl">
          <div className="flex justify-between items-center mb-4"><h3 className="text-teal-400 font-semibold">📋 Assigned Cases</h3><button onClick={()=>setCases(prev=>[{id:Math.floor(1000+Math.random()*9000),status:'Needs Review',time:'Just now'},...prev])} className="text-xs bg-teal-600/20 hover:bg-teal-600/40 text-teal-400 border border-teal-500/30 px-3 py-1.5 rounded-lg font-semibold transition-colors">+ New Case</button></div>
          <div className="space-y-3">{cases.map((c,i)=><div key={c.id} className="bg-slate-800/50 p-3 rounded-xl border border-slate-700/50 flex flex-col group hover:border-slate-600 transition-colors">
            <div className="flex justify-between items-start"><span className="text-sm font-semibold text-slate-200">Patient #{c.id}</span><span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${c.status==='Needs Review'?'text-rose-400 bg-rose-400/10 border-rose-400/30':c.status==='Pending Lab'?'text-amber-400 bg-amber-400/10 border-amber-400/30':'text-emerald-400 bg-emerald-400/10 border-emerald-400/30'}`}>{c.status}</span></div>
            <div className="flex justify-between items-end mt-2"><div className="text-xs text-slate-400">{c.time}</div><div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity"><button onClick={()=>setCases(prev=>prev.map(x=>x.id===c.id?{...x,status:'Reviewed'}:x))} className="text-xs text-emerald-400 hover:text-emerald-300 font-semibold">✓ Done</button><button onClick={()=>setCases(prev=>prev.filter(x=>x.id!==c.id))} className="text-xs text-rose-400 hover:text-rose-300 font-semibold">Remove</button></div></div>
          </div>)}</div>
        </div>
        <div className="glass p-5 rounded-xl">
          <div className="flex justify-between items-center mb-4"><h3 className="text-blue-400 font-semibold">✍️ Clinical Drafts</h3><button onClick={()=>setDrafts(prev=>[{id:Date.now(),title:'New Clinical Note',time:'Just now',content:''},...prev])} className="text-xs bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 border border-blue-500/30 px-3 py-1.5 rounded-lg font-semibold transition-colors">+ New Draft</button></div>
          <div className="space-y-3">{drafts.map(d=><div key={d.id} className="bg-slate-800/50 p-3 rounded-xl border border-slate-700/50 group hover:border-slate-600 transition-colors">
            <input type="text" value={d.title} onChange={e=>updateTitle(d.id,e.target.value)} className="w-full text-sm font-semibold text-slate-200 bg-transparent border-b-2 border-transparent hover:border-slate-600 focus:border-teal-500 focus:outline-none transition-colors pb-0.5 leading-tight"/>
            <div className="flex justify-between items-center mt-2"><div className="text-xs text-slate-500">{d.time}</div><div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity"><button onClick={()=>openEdit(d)} className="text-xs bg-teal-600/20 text-teal-400 hover:bg-teal-600/40 px-2 py-1 rounded-lg font-semibold transition-colors">Edit</button><button onClick={()=>setDrafts(prev=>prev.filter(x=>x.id!==d.id))} className="text-xs bg-rose-600/20 text-rose-400 hover:bg-rose-600/40 px-2 py-1 rounded-lg font-semibold transition-colors">Delete</button></div></div>
          </div>)}</div>
        </div>
      </div>
      {editing&&<div className="fixed inset-0 bg-[#0a0f1e]/80 backdrop-blur-sm z-50 flex items-center justify-center p-6 slide-in">
        <div className="bg-[#0d1326] border border-slate-700 w-full max-w-3xl rounded-2xl p-6 shadow-2xl flex flex-col h-[70vh]">
          <div className="flex justify-between items-center mb-4"><h2 className="text-lg font-bold text-white">✍️ {editing.title}</h2><button onClick={()=>setEditing(null)} className="text-slate-400 hover:text-rose-400 w-8 h-8 rounded-lg hover:bg-rose-500/10 flex items-center justify-center transition-all">✕</button></div>
          <textarea value={editContent} onChange={e=>setEditContent(e.target.value)} className="flex-1 w-full bg-slate-900 border border-slate-700 rounded-xl p-4 text-slate-200 text-sm focus:outline-none focus:border-teal-500 resize-none font-mono transition-colors"/>
          <div className="flex justify-end gap-3 mt-4"><button onClick={()=>setEditing(null)} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-sm font-medium transition-colors">Discard</button><button onClick={saveEdit} className="px-6 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-bold transition-colors">Save Draft</button></div>
        </div>
      </div>}
    </div>
  )
}

// ── DepartmentsView ───────────────────────────────────────────────────
function DepartmentsView() {
  const [depts,setDepts]=useLocalState('departments',[{id:1,name:'Cardiology',patients:24,status:'Normal'},{id:2,name:'Neurology',patients:18,status:'Busy'},{id:3,name:'Oncology',patients:32,status:'Normal'},{id:4,name:'Radiology',patients:45,status:'High Volume'},{id:5,name:'Emergency',patients:12,status:'Critical'},{id:6,name:'Pediatrics',patients:8,status:'Normal'}])
  const statuses=['Normal','Busy','High Volume','Critical']
  const cycle=(id)=>setDepts(prev=>prev.map(d=>d.id===id?{...d,status:statuses[(statuses.indexOf(d.status)+1)%statuses.length]}:d))
  const updateName=(id,val)=>setDepts(prev=>prev.map(d=>d.id===id?{...d,name:val}:d))
  const updatePts=(id,delta)=>setDepts(prev=>prev.map(d=>d.id===id?{...d,patients:Math.max(0,d.patients+delta)}:d))
  return (
    <div className="space-y-6 slide-in">
      <div className="flex items-center justify-between"><h2 className="text-2xl font-bold text-white">Departments</h2><button onClick={()=>setDepts(prev=>[...prev,{id:Date.now(),name:'New Department',patients:0,status:'Normal'}])} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-sm font-semibold border border-slate-700 transition-colors">+ Add Department</button></div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{depts.map(d=><div key={d.id} className="glass p-5 rounded-xl border border-slate-700/50 hover:border-slate-600 transition-colors group">
        <div className="flex justify-between items-start mb-4">
          <input type="text" value={d.name} onChange={e=>updateName(d.id,e.target.value)} className="text-base font-bold text-slate-200 bg-transparent border-b-2 border-transparent hover:border-slate-600 focus:border-teal-500 focus:outline-none transition-colors w-full mr-2 pb-0.5" placeholder="Department name"/>
          <button onClick={()=>setDepts(prev=>prev.filter(x=>x.id!==d.id))} className="text-slate-500 hover:text-rose-400 opacity-0 group-hover:opacity-100 transition-all text-xs px-2 py-1 hover:bg-rose-500/10 rounded-lg shrink-0">Remove</button>
        </div>
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2"><span className="text-sm text-slate-400 font-medium">{d.patients} Patients</span><div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity"><button onClick={()=>updatePts(d.id,1)} className="w-6 h-6 bg-teal-600/20 text-teal-400 rounded-lg flex items-center justify-center hover:bg-teal-600/40 transition-colors text-xs font-bold">+</button><button onClick={()=>updatePts(d.id,-1)} className="w-6 h-6 bg-slate-700 text-slate-400 rounded-lg flex items-center justify-center hover:bg-slate-600 transition-colors text-xs font-bold">-</button></div></div>
          <button onClick={()=>cycle(d.id)} className={`text-xs px-3 py-1.5 rounded-full cursor-pointer transition-colors font-semibold border ${d.status==='Critical'?'bg-rose-500/15 text-rose-400 border-rose-500/30 hover:bg-rose-500/25':d.status==='High Volume'?'bg-orange-500/15 text-orange-400 border-orange-500/30 hover:bg-orange-500/25':d.status==='Busy'?'bg-amber-500/15 text-amber-400 border-amber-500/30 hover:bg-amber-500/25':'bg-emerald-500/15 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/25'}`}>{d.status}</button>
        </div>
      </div>)}</div>
    </div>
  )
}

// ── ScheduleView ──────────────────────────────────────────────────────
function ScheduleView() {
  const [viewMode,setViewMode]=useState('Day')
  const [events,setEvents]=useLocalState('schedule_events',[{id:1,time:'09:00 AM',title:'Dr. Smith — Patient Assessment',loc:'Room 302',color:'teal'},{id:2,time:'10:30 AM',title:'Department Meeting',loc:'Conference Room B',color:'blue'},{id:3,time:'01:00 PM',title:'Surgery Prep',loc:'OR 2',color:'rose'},{id:4,time:'03:00 PM',title:'Rounds',loc:'Ward 4',color:'emerald'}])
  const updateTitle=(id,val)=>setEvents(prev=>prev.map(e=>e.id===id?{...e,title:val}:e))
  const updateLoc=(id,val)=>setEvents(prev=>prev.map(e=>e.id===id?{...e,loc:val}:e))
  const colors=['teal','blue','rose','emerald','amber','indigo']
  const add=()=>setEvents(prev=>[...prev,{id:Date.now(),time:'04:00 PM',title:'New Appointment',loc:'TBD',color:colors[Math.floor(Math.random()*colors.length)]}].sort((a,b)=>a.time.localeCompare(b.time)))
  const colorMap={teal:'border-teal-500/40 bg-teal-500/10',blue:'border-blue-500/40 bg-blue-500/10',rose:'border-rose-500/40 bg-rose-500/10',emerald:'border-emerald-500/40 bg-emerald-500/10',amber:'border-amber-500/40 bg-amber-500/10',indigo:'border-indigo-500/40 bg-indigo-500/10'}
  const textMap={teal:'text-teal-300',blue:'text-blue-300',rose:'text-rose-300',emerald:'text-emerald-300',amber:'text-amber-300',indigo:'text-indigo-300'}
  return (
    <div className="space-y-6 slide-in">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Schedule</h2>
        <div className="flex gap-3">
          <div className="flex bg-slate-800 rounded-xl p-1">{['Day','Week','Month'].map(m=><button key={m} onClick={()=>setViewMode(m)} className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition-colors ${viewMode===m?'bg-teal-600 text-white':'text-slate-400 hover:text-slate-200'}`}>{m}</button>)}</div>
          <button onClick={add} className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-semibold transition-colors">+ Add Event</button>
        </div>
      </div>
      <div className="glass rounded-xl p-6 space-y-4 min-h-80">
        {events.length===0&&<div className="text-center text-slate-500 py-10">No events scheduled. Click + Add Event to start.</div>}
        {events.map(ev=><div key={ev.id} className="flex gap-4 group">
          <div className="w-20 text-right text-xs text-slate-500 font-semibold pt-3 shrink-0">{ev.time}</div>
          <div className={`flex-1 rounded-xl p-3 border ${colorMap[ev.color]||colorMap.teal}`}>
            <div className="flex justify-between items-start gap-3">
              <div className="flex-1 min-w-0 space-y-1.5">
                <input type="text" value={ev.title} onChange={e=>updateTitle(ev.id,e.target.value)} className={`w-full text-sm font-bold bg-transparent border-b border-transparent hover:border-slate-500 focus:border-teal-400 focus:outline-none transition-colors pb-0.5 ${textMap[ev.color]||textMap.teal}`}/>
                <input type="text" value={ev.loc} onChange={e=>updateLoc(ev.id,e.target.value)} className="w-full text-xs text-slate-400 bg-transparent border-b border-transparent hover:border-slate-600 focus:border-slate-500 focus:outline-none transition-colors pb-0.5" placeholder="Location"/>
              </div>
              <button onClick={()=>setEvents(prev=>prev.filter(e=>e.id!==ev.id))} className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-400 transition-all w-6 h-6 flex items-center justify-center rounded hover:bg-rose-500/10 shrink-0">✕</button>
            </div>
          </div>
        </div>)}
      </div>
    </div>
  )
}

// ── ReportView ────────────────────────────────────────────────────────
function ReportView() {
  const [reports,setReports]=useLocalState('reports',[])
  const [title,setTitle]=useState(''); const [viewing,setViewing]=useState(null)
  const gen=()=>{const t=title.trim()||'Analytics Report';const d=new Date().toLocaleDateString();const content=`MEDCODE AI — ANALYTICS REPORT\n${'='.repeat(40)}\nTitle: ${t}\nGenerated: ${d}\n\nSUMMARY METRICS\n---------------\nTotal Scans Processed: 1,248\nAI Confidence Average: 94.2%\nCode Mapping Accuracy: 98.7%\nCritical Flags Raised: 24\nDrug Interactions Detected: 8\n\nNOTES\n-----\nSystem performance is optimal.\nAll codes verified against ICD-10-CM database.\n`;setReports(prev=>[{id:Date.now(),title:t,date:d,content},...prev]);setTitle('')}
  const exp=(r)=>{const blob=new Blob([r.content],{type:'text/plain'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=r.title.replace(/\s+/g,'_')+'.txt';a.click()}
  return (
    <div className="space-y-6 slide-in">
      <div className="flex items-center justify-between"><h2 className="text-2xl font-bold text-white">Reports & Analytics</h2><div className="flex gap-2"><input value={title} onChange={e=>setTitle(e.target.value)} onKeyDown={e=>e.key==='Enter'&&gen()} placeholder="Report title..." className="bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-teal-500 text-slate-200 w-52 transition-colors"/><button onClick={gen} className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-bold transition-colors">Generate</button></div></div>
      <div className="grid grid-cols-2 gap-6">{[['📈','Coding Accuracy Trend','Historical accuracy improvements over time'],['📊','Top ICD-10 Codes','Most frequently extracted diagnosis codes']].map(([i,t,d])=><div key={t} className="glass p-5 rounded-xl h-52 flex flex-col justify-center items-center text-center"><div className="text-4xl mb-3">{i}</div><div className="text-slate-200 font-semibold">{t}</div><div className="text-slate-500 text-xs mt-2 max-w-xs">{d}</div></div>)}</div>
      {reports.length>0&&<div className="glass rounded-xl p-5"><h3 className="text-slate-200 font-semibold mb-4">Generated Reports ({reports.length})</h3><div className="grid grid-cols-1 md:grid-cols-3 gap-4">{reports.map(r=><div key={r.id} className="bg-slate-800/50 p-4 rounded-xl border border-slate-700/50 hover:border-slate-600 transition-colors"><div className="text-sm font-bold text-teal-300">{r.title}</div><div className="text-xs text-slate-500 mt-1">{r.date}</div><div className="flex gap-2 mt-4"><button onClick={()=>setViewing(r)} className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 px-3 py-1.5 rounded-lg flex-1 transition-colors font-medium">View</button><button onClick={()=>exp(r)} className="text-xs bg-teal-700/40 hover:bg-teal-700/60 text-teal-300 px-3 py-1.5 rounded-lg flex-1 transition-colors font-medium">Export</button><button onClick={()=>setReports(prev=>prev.filter(x=>x.id!==r.id))} className="text-xs bg-rose-700/30 hover:bg-rose-700/50 text-rose-400 px-3 py-1.5 rounded-lg transition-colors font-medium">Del</button></div></div>)}</div></div>}
      {viewing&&<div className="fixed inset-0 bg-[#0a0f1e]/80 backdrop-blur-sm z-50 flex items-center justify-center p-6 slide-in"><div className="bg-[#0d1326] border border-slate-700 w-full max-w-2xl rounded-2xl p-6 shadow-2xl"><div className="flex justify-between items-center mb-4"><h2 className="text-lg font-bold text-white">{viewing.title}</h2><button onClick={()=>setViewing(null)} className="text-slate-400 hover:text-rose-400 w-8 h-8 rounded-lg hover:bg-rose-500/10 flex items-center justify-center transition-all">✕</button></div><textarea readOnly value={viewing.content} className="bg-slate-900 border border-slate-700 rounded-xl p-4 text-slate-300 text-sm font-mono h-60 w-full resize-none focus:outline-none"/><div className="flex justify-end mt-4"><button onClick={()=>{exp(viewing);setViewing(null)}} className="px-5 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-bold transition-colors">Export & Close</button></div></div></div>}
    </div>
  )
}

// ── PaymentView ───────────────────────────────────────────────────────
function PaymentView({ user }) {
  const nav=useNavigate()
  const SERVICE_TYPES=['Consultation','Lab Test','Radiology','Surgery','Pharmacy','ICU','OPD Visit','Emergency','Physiotherapy','Dental']
  const [invoices,setInvoices]=useLocalState('medical_invoices',[{id:'INV-001',patient:'Rajesh Kumar',service:'Cardiology Consultation',date:'17 Apr 2024',amount:500,status:'Paid',doctor:'Dr. Sharma'},{id:'INV-002',patient:'Priya Mehta',service:'CBC + LFT Lab Tests',date:'16 Apr 2024',amount:850,status:'Pending',doctor:'Dr. Patel'},{id:'INV-003',patient:'Suresh Verma',service:'Chest X-Ray',date:'15 Apr 2024',amount:300,status:'Paid',doctor:'Dr. Gupta'},{id:'INV-004',patient:'Anita Singh',service:'Emergency Visit',date:'14 Apr 2024',amount:2200,status:'Overdue',doctor:'Dr. Rao'}])
  const [showForm,setShowForm]=useState(false); const [form,setForm]=useState({patient:'',service:'Consultation',amount:'',doctor:''}); const [viewInv,setViewInv]=useState(null)
  const cycleStatus=(id)=>{const s=['Pending','Paid','Overdue'];setInvoices(prev=>prev.map(x=>x.id===id?{...x,status:s[(s.indexOf(x.status)+1)%s.length]}:x))}
  const createInv=()=>{if(!form.patient||!form.amount)return;const num=String(invoices.length+1).padStart(3,'0');setInvoices(prev=>[{id:'INV-'+num,patient:form.patient,service:form.service,date:new Date().toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}),amount:parseFloat(form.amount)||0,status:'Pending',doctor:form.doctor||'Dr. Unknown'},...prev]);setForm({patient:'',service:'Consultation',amount:'',doctor:''});setShowForm(false)}
  const total=invoices.reduce((s,i)=>s+i.amount,0); const paid=invoices.filter(i=>i.status==='Paid').reduce((s,i)=>s+i.amount,0); const pending=invoices.filter(i=>i.status!=='Paid').reduce((s,i)=>s+i.amount,0)
  return (
    <div className="space-y-6 slide-in">
      <div className="flex items-center justify-between"><h2 className="text-2xl font-bold text-white">Medical Billing</h2><button onClick={()=>setShowForm(!showForm)} className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-bold transition-colors">+ Create Invoice</button></div>
      <div className={`rounded-xl p-4 border ${user?.is_subscribed?'border-teal-500/40 bg-teal-500/5':'border-slate-700 bg-slate-800/30'}`}>
        <div className="flex items-center justify-between">
          <div><div className="text-sm font-bold text-slate-200">MedCode AI Subscription</div><div className={`text-xs mt-1 ${user?.is_subscribed?'text-teal-400':'text-slate-500'}`}>{user?.is_subscribed?'✓ Pro Plan Active — PDF, Email & WhatsApp unlocked':'Free Plan — Upgrade to unlock Pro features'}</div></div>
          {!user?.is_subscribed&&<button onClick={()=>nav('/subscribe')} className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-bold transition-colors whitespace-nowrap">Subscribe ₹1/mo</button>}
          {user?.is_subscribed&&<span className="text-xs px-3 py-1.5 bg-teal-500/20 text-teal-400 border border-teal-500/30 rounded-full font-bold">✓ Pro Active</span>}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">{[['Total Invoiced',`₹${total.toLocaleString()}`,'text-white'],['Collected',`₹${paid.toLocaleString()}`,'text-emerald-400'],['Outstanding',`₹${pending.toLocaleString()}`,'text-amber-400']].map(([l,v,c])=><div key={l} className="glass p-4 rounded-xl border border-slate-700/50 text-center"><div className="text-xs text-slate-400 font-semibold uppercase tracking-wider">{l}</div><div className={`text-2xl font-bold mt-1 ${c}`}>{v}</div></div>)}</div>
      {showForm&&<div className="glass p-5 rounded-xl space-y-3 border border-teal-500/20 slide-in">
        <h3 className="text-sm font-bold text-slate-200">New Medical Invoice</h3>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="text-xs text-slate-400 font-semibold block mb-1">Patient Name *</label><input value={form.patient} onChange={e=>setForm(f=>({...f,patient:e.target.value}))} placeholder="e.g. Rajesh Kumar" className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-teal-500 transition-colors"/></div>
          <div><label className="text-xs text-slate-400 font-semibold block mb-1">Doctor</label><input value={form.doctor} onChange={e=>setForm(f=>({...f,doctor:e.target.value}))} placeholder="e.g. Dr. Sharma" className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-teal-500 transition-colors"/></div>
          <div><label className="text-xs text-slate-400 font-semibold block mb-1">Service Type</label><select value={form.service} onChange={e=>setForm(f=>({...f,service:e.target.value}))} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-teal-500 transition-colors">{SERVICE_TYPES.map(s=><option key={s}>{s}</option>)}</select></div>
          <div><label className="text-xs text-slate-400 font-semibold block mb-1">Amount (₹) *</label><input type="number" value={form.amount} onChange={e=>setForm(f=>({...f,amount:e.target.value}))} placeholder="e.g. 500" className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-teal-500 transition-colors"/></div>
        </div>
        <div className="flex justify-end gap-2"><button onClick={()=>setShowForm(false)} className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-xl text-sm font-medium transition-colors">Cancel</button><button onClick={createInv} className="px-5 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-bold transition-colors">Create Invoice</button></div>
      </div>}
      <div className="glass rounded-xl overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-800/80 text-xs uppercase text-slate-500 border-b border-slate-700"><tr>{['Invoice','Patient','Service','Doctor','Date','Amount','Status',''].map(h=><th key={h} className="px-4 py-3 font-bold tracking-wider">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-800/50">{invoices.map(inv=><tr key={inv.id} className="hover:bg-slate-800/30 transition-colors group">
            <td className="px-4 py-3 font-mono text-xs text-teal-400 font-bold">{inv.id}</td>
            <td className="px-4 py-3 font-semibold text-slate-200">{inv.patient}</td>
            <td className="px-4 py-3 text-slate-300 text-xs">{inv.service}</td>
            <td className="px-4 py-3 text-slate-400 text-xs">{inv.doctor}</td>
            <td className="px-4 py-3 text-slate-400 text-xs">{inv.date}</td>
            <td className="px-4 py-3 font-mono font-bold text-slate-200">₹{inv.amount.toLocaleString()}</td>
            <td className="px-4 py-3"><button onClick={()=>cycleStatus(inv.id)} className={`text-xs px-2.5 py-1 rounded-full cursor-pointer font-bold border transition-colors ${inv.status==='Paid'?'bg-emerald-500/15 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/25':inv.status==='Pending'?'bg-amber-500/15 text-amber-400 border-amber-500/30 hover:bg-amber-500/25':'bg-rose-500/15 text-rose-400 border-rose-500/30 hover:bg-rose-500/25'}`}>{inv.status}</button></td>
            <td className="px-4 py-3"><div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity"><button onClick={()=>setViewInv(inv)} className="text-xs text-teal-400 hover:text-teal-300 font-semibold">View</button><button onClick={()=>setInvoices(prev=>prev.filter(x=>x.id!==inv.id))} className="text-xs text-rose-400 hover:text-rose-300 font-semibold">Del</button></div></td>
          </tr>)}</tbody>
        </table>
      </div>
      {viewInv&&<div className="fixed inset-0 bg-[#0a0f1e]/80 backdrop-blur-sm z-50 flex items-center justify-center p-6 slide-in"><div className="bg-[#0d1326] border border-slate-700 w-full max-w-md rounded-2xl p-8 shadow-2xl" id="inv-print">
        <style>{`@media print{body *{visibility:hidden}#inv-print,#inv-print *{visibility:visible}#inv-print{position:absolute;left:0;top:0;width:100%;background:white;color:black}.no-print{display:none!important}}`}</style>
        <button onClick={()=>setViewInv(null)} className="no-print absolute top-4 right-4 text-slate-400 hover:text-rose-400 w-8 h-8 rounded-lg flex items-center justify-center hover:bg-rose-500/10 transition-all">✕</button>
        <div className="text-center mb-6"><div className="text-2xl font-bold text-white">🏥 MEDCODE AI</div><div className="text-xs text-slate-400 mt-1">Medical Service Invoice</div></div>
        <div className="space-y-3 text-sm">{[['Invoice ID',viewInv.id,'font-mono text-teal-400'],['Patient',viewInv.patient,'text-white font-semibold'],['Doctor',viewInv.doctor,'text-slate-300'],['Service',viewInv.service,'text-slate-300'],['Date',viewInv.date,'text-slate-300'],['Status',viewInv.status,viewInv.status==='Paid'?'text-emerald-400':viewInv.status==='Overdue'?'text-rose-400':'text-amber-400']].map(([l,v,c])=><div key={l} className="flex justify-between border-b border-slate-800 pb-2"><span className="text-slate-400">{l}</span><span className={c}>{v}</span></div>)}<div className="flex justify-between items-center pt-3"><span className="text-lg font-bold text-slate-200">Total Amount</span><span className="text-2xl font-bold text-white font-mono">₹{viewInv.amount.toLocaleString()}</span></div></div>
        <div className="mt-6 flex gap-3 no-print"><button onClick={()=>window.print()} className="flex-1 py-2.5 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-bold transition-colors">Print Invoice</button><button onClick={()=>setViewInv(null)} className="flex-1 py-2.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-xl text-sm font-medium transition-colors">Close</button></div>
      </div></div>}
    </div>
  )
}

// ── Main shell ────────────────────────────────────────────────────────
function MainApp() {
  const { user, logout }=useAuth(); const [view,setView]=useState('Patient'); const nav=useNavigate()
  const titles={Home:'Dashboard',Inbox:'Inbox',Doctor:'Physician Workflow',Patient:'Code Document',Departments:'Departments',Schedule:'Schedule',Report:'Reports & Analytics',Payment:'Medical Billing'}
  const render=()=>{ switch(view){ case 'Home':return<HomeView/>; case 'Inbox':return<InboxView/>; case 'Doctor':return<DoctorView/>; case 'Patient':return<PatientView isSubscribed={user?.is_subscribed}/>; case 'Departments':return<DepartmentsView/>; case 'Schedule':return<ScheduleView/>; case 'Report':return<ReportView/>; case 'Payment':return<PaymentView user={user}/>; default:return<PatientView isSubscribed={user?.is_subscribed}/> } }
  return (
    <div className="flex min-h-screen bg-[#0a0f1e]">
      <Sidebar view={view} setView={setView} user={user}/>
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="border-b border-slate-800 bg-[#0a0f1e]/95 backdrop-blur sticky top-0 z-30 shrink-0">
          <div className="px-6 py-3 flex items-center justify-between">
            <div><h1 className="text-sm font-bold text-white">{titles[view]||view}</h1><div className="text-xs text-slate-500">MedCode AI · ICD-10-CM Coding Assistant</div></div>
            <div className="flex items-center gap-3">
              <div className="hidden sm:flex items-center gap-2 text-xs text-slate-500"><div className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot"/>RAG + LLM · Anti-hallucination</div>
              {user?(
                <div className="flex items-center gap-2">
                  {user.is_subscribed?<span className="text-xs px-2.5 py-1 bg-teal-500/20 text-teal-400 border border-teal-500/30 rounded-full font-bold">⭐ Pro</span>:<button onClick={()=>nav('/subscribe')} className="text-xs px-2.5 py-1 bg-teal-600/20 hover:bg-teal-600/40 text-teal-400 border border-teal-500/40 rounded-full transition-colors font-semibold">Upgrade ₹1</button>}
                  <span className="text-xs text-slate-400 hidden sm:block font-medium">{user.name}</span>
                  <button onClick={logout} className="text-xs text-slate-500 hover:text-slate-300 transition-colors">Sign out</button>
                </div>
              ):<button onClick={()=>nav('/login')} className="text-xs px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-white rounded-lg font-semibold transition-colors">Sign In</button>}
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">{render()}</main>
      </div>
    </div>
  )
}

export default function App() {
  const { loading }=useAuth()
  if(loading)return<div className="min-h-screen bg-[#0a0f1e] flex items-center justify-center"><div className="w-8 h-8 border-2 border-teal-400 border-t-transparent rounded-full animate-spin"/></div>
  return(
    <Routes>
      <Route path="/" element={<MainApp/>}/>
      <Route path="/login" element={<LoginPage/>}/>
      <Route path="/subscribe" element={<SubscriptionPage/>}/>
      <Route path="*" element={<Navigate to="/"/>}/>
    </Routes>
  )
}
