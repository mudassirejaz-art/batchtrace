import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Player } from '@remotion/player';
import {
  Users, Activity, ArrowRight, ArrowUpRight, Boxes, Check, CheckCircle2, ChevronDown,
  ChevronRight, CircleAlert, Clock3, CloudUpload, CreditCard, FileCheck2, FileSpreadsheet,
  LayoutDashboard, LogOut, Menu, Package, Plus, RefreshCw, Search, ShieldCheck, Sparkles, BellRing,
  Truck, UserRound, Wallet, X, Zap, Layers3, CalendarDays, Eye, UploadCloud, LockKeyhole,
  type LucideIcon,
} from 'lucide-react';
import { api, ApiError, idem, isoToday, json, messageOf } from './api';
import { AuraScene } from './AuraScene';
import { TeamPanel } from './TeamPanel';
import { EvidencePanel, type EvidenceSelection } from './EvidencePanel';
import { ClaimDetailPanel } from './ClaimDetailPanel';
import { ApprovalInbox } from './ApprovalInbox';
import './step25-live.css';
import { canAct,canVisit,roleCopy,workspaceRole } from './roleAccess';
import { SetupGuide } from './SetupGuide';
import type {
  Claim, CreditReceipt, CreditSummary, CsvPreview, ImportRecord, Lot, Opportunity, Organization,
  Policy, Product, Section, Supplier, User, Verification,
} from './types';

const SESSION = 'batchtrace_session_token';
const allSections: Array<{key:Section;title:string;icon:LucideIcon;group:string}> = [
  {key:'overview',title:'Overview',icon:LayoutDashboard,group:'Workspace'},
  {key:'approvals',title:'Approval inbox',icon:BellRing,group:'Workspace'},
  {key:'opportunities',title:'Recovery signals',icon:Zap,group:'Workspace'},
  {key:'team',title:'Team members',icon:Users,group:'Workspace'},
  {key:'lots',title:'Batches & expiry',icon:Boxes,group:'Inventory'},
  {key:'imports',title:'CSV observations',icon:FileSpreadsheet,group:'Inventory'},
  {key:'suppliers',title:'Suppliers',icon:Truck,group:'Inventory'},
  {key:'products',title:'Products',icon:Package,group:'Inventory'},
  {key:'policies',title:'Return policies',icon:CalendarDays,group:'Inventory'},
  {key:'verifications',title:'Physical checks',icon:ShieldCheck,group:'Recovery'},
  {key:'claims',title:'Supplier claims',icon:FileCheck2,group:'Recovery'},
  {key:'credits',title:'Credit reconciliation',icon:Wallet,group:'Recovery'},
];

type Data = {
  suppliers:Supplier[]; products:Product[]; lots:Lot[]; policies:Policy[];
  imports:ImportRecord[]; opportunities:Opportunity[]; verifications:Verification[]; claims:Claim[];
};
const emptyData:Data = {suppliers:[],products:[],lots:[],policies:[],imports:[],opportunities:[],verifications:[],claims:[]};
type ModalState = {kind:string; id?:string; record?:Record<string, unknown>} | null;
type FormValue = Record<string,string>;
const CATALOG_CODE_PATTERN = /^[A-Z0-9][A-Z0-9._-]*$/;
function normalizeCatalogIdentifier(value:string):string {
  return value.normalize('NFKC').trim().replace(/[\s\u2010-\u2015\u2212]+/g,'-').toUpperCase();
}

function statusTone(s:string):string { return /approved|accepted|window_open|verify_stock|fully_reconciled/i.test(s)?'good':/pending|stale|partial|not_yet_open|draft|dispatched/i.test(s)?'warn':/rejected|closed|expired/i.test(s)?'danger':'muted'; }
function niceStatus(s:string):string { return s.replaceAll('_',' '); }
function formatDate(s?:string|null):string { if(!s) return '—'; const d = new Date(s.includes('T')?s:`${s}T12:00:00`); return Number.isNaN(+d)?s:d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); }
function money(minor:number,currency='PKR'):string {return new Intl.NumberFormat('en-US',{style:'currency',currency,maximumFractionDigits:2}).format(minor/100);}
function GlowLogo({small=false}:{small?:boolean}) {return <div className={'brand-glyph '+(small?'brand-glyph-sm':'')}><Layers3 size={small?19:23} strokeWidth={2.5}/></div>;}
function Tag({children,tone='muted'}:{children:ReactNode;tone?:string}) {return <span className={'tag tag-'+tone}><i/>{children}</span>;}
function Spinner(){return <span className="spinner" aria-label="Loading"/>;}
function Empty({icon:Icon=Boxes, title, caption}:{icon?:LucideIcon; title:string; caption:string}) {return <div className="empty"><div className="empty-icon"><Icon size={24}/></div><strong>{title}</strong><p>{caption}</p></div>;}
function ShortId({id}:{id:string}){return <span className="mono dim" title={id}>{id.slice(0,8)}…</span>}
function todayVal(){return isoToday();}

function IntroVisual({compact=false}:{compact?:boolean}) {
  const [motion,setMotion]=useState(true);
  useEffect(()=>{const m=window.matchMedia('(prefers-reduced-motion: reduce)');const apply=()=>setMotion(!m.matches);apply();m.addEventListener('change',apply);return ()=>m.removeEventListener('change',apply);},[]);
  return <div className={'visual-orbit '+(compact?'compact-orbit':'')} aria-hidden="true">
    <div className="orbit-glow"/>
    {motion?<Player component={AuraScene} durationInFrames={360} compositionWidth={1000} compositionHeight={760} fps={30} autoPlay loop style={{height:'100%',width:'100%'}}/>:<div className="still-aura"><Layers3 size={86}/></div>}
  </div>;
}

function Auth({onAuth}:{onAuth:(token:string)=>Promise<void>}) {
  const [mode,setMode]=useState<'login'|'register'>('login');
  const [email,setEmail]=useState(''); const [password,setPassword]=useState('');
  const [orgName,setOrgName]=useState(''); const [orgSlug,setOrgSlug]=useState('');
  const [customWorkspace,setCustomWorkspace]=useState(false);
  const [busy,setBusy]=useState(false); const [error,setError]=useState('');
  async function submit(e:FormEvent){e.preventDefault();setBusy(true);setError('');try{
    if(mode==='register') {
      // New accounts receive a private workspace. Joining another org always needs membership approval.
      const autoName=(email.split('@')[0].replace(/[._-]+/g,' ').trim()||'Personal')+' Workspace';
      const autoSlug='ws-'+crypto.randomUUID().replaceAll('-','').slice(0,14);
      await api('/auth/register',null,json({email,password,organization_name:customWorkspace?orgName.trim():autoName,organization_slug:customWorkspace?orgSlug.trim():autoSlug}));
    }
    const result=await api<{access_token:string}>('/auth/login',null,json({email,password}));
    await onAuth(result.access_token);
  }catch(err){setError(messageOf(err));}finally{setBusy(false);}}
  return <div className="auth-layout">
    <div className="auth-marketing">
      <div className="auth-brand"><GlowLogo/><span>batchtrace<span className="brand-dot">.</span></span><Tag tone="good">Made for real teams</Tag></div>
      <div className="auth-visual"><IntroVisual/></div>
      <div className="auth-copy"><div className="eyebrow"><Sparkles size={14}/> SMARTER STOCK, SIMPLER DAYS</div>
        <h1>Less waste.<br/><em>More possibilities.</em></h1>
        <p>Keep good stock moving and valuable time in your hands. Every expiry, return and supplier decision in one calm workspace.</p>
        <div className="auth-perks"><span><CheckCircle2 size={16}/> Your own FastAPI backend</span><span><CheckCircle2 size={16}/> Versioned policy logic</span></div>
      </div>
      <div className="auth-footer">BATCHTRACE / RECOVERY INTELLIGENCE <span>01 — 04</span></div>
    </div>
    <div className="auth-form-pane"><div className="auth-form-box">
      <div className="auth-mini-brand"><GlowLogo small/> batchtrace.</div>
      <div className="auth-header"><div className="section-kicker">WELCOME TO YOUR WORKSPACE</div><h2>{mode==='login'?'Sign in to BatchTrace':'Create your workspace'}</h2><p>{mode==='login'?'Pick up exactly where your recovery workflow left off.':'Your team’s recovery command center starts here.'}</p></div>
      <div className="auth-switch"><button className={mode==='login'?'selected':''} onClick={()=>{setMode('login');setError('')}}>Sign in</button><button className={mode==='register'?'selected':''} onClick={()=>{setMode('register');setError('')}}>Create account</button></div>
      <form onSubmit={submit} className="auth-form">
        {mode==='register'&&<>
          <div className="auth-workspace-note">A private workspace is created automatically for your account. To access someone else's workspace, their owner or admin must add you as a member—matching a workspace name does not grant access.</div>
          <button className="auth-workspace-toggle" type="button" onClick={()=>setCustomWorkspace(x=>!x)}>{customWorkspace?'Use automatic workspace':'Customize workspace name (optional)'}</button>
          {customWorkspace&&<><label>Organization name<input required value={orgName} onChange={e=>{setOrgName(e.target.value);if(!orgSlug)setOrgSlug(e.target.value.toLowerCase().trim().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,''));}} placeholder="Acme Distribution" minLength={2}/></label><label>Workspace slug<input required value={orgSlug} onChange={e=>setOrgSlug(e.target.value.toLowerCase())} pattern="[a-z0-9]+(-[a-z0-9]+)*" minLength={3} placeholder="acme-distribution"/></label></>}
        </>}
        <label>Work email<input type="email" required autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com"/></label>
        <label>Password<input type="password" required minLength={mode==='register'?12:1} autoComplete={mode==='register'?'new-password':'current-password'} value={password} onChange={e=>setPassword(e.target.value)} placeholder={mode==='register'?'At least 12 characters':'Enter your password'}/></label>
        {error&&<div className="inline-error" role="alert"><CircleAlert size={16}/>{error}</div>}
        <button className="primary-btn auth-submit" disabled={busy}>{busy?<Spinner/>:<><span>{mode==='login'?'Open workspace':'Create and sign in'}</span><ArrowRight size={18}/></>}</button>
      </form>
      <div className="auth-form-bottom"><LockKeyhole size={15}/> Secured by your self-hosted API. No third-party login service.</div>
    </div></div>
  </div>;
}

function FormModal({state,onClose,onSubmit,working,data}:{state:ModalState;onClose:()=>void;onSubmit:(value:FormValue)=>Promise<void>;working:boolean;data:Data}) {
  const [value,setValue]=useState<FormValue>({});
  const [validationError,setValidationError]=useState('');
  if(!state)return null;
  const kinds:Record<string,{title:string;subtitle:string;fields:Array<{key:string;label:string;type?:string;required?:boolean;options?:Array<{id:string;name:string}>;placeholder?:string;min?:number}>}> = {
    supplier:{title:'Add supplier',subtitle:'Create an organization-scoped supplier record.',fields:[{key:'code',label:'Supplier code',placeholder:'SUP-001',required:true},{key:'name',label:'Supplier name',placeholder:'Atlas Wholesale',required:true}]},
    product:{title:'Add product',subtitle:'Register a product before creating batches.',fields:[{key:'sku',label:'Product SKU',placeholder:'ITEM-001',required:true},{key:'name',label:'Product name',placeholder:'Product description',required:true}]},
    lot:{title:'Register batch',subtitle:'A batch is metadata, not a live inventory balance.',fields:[{key:'product_id',label:'Product',type:'select',required:true,options:data.products.map(p=>({id:p.id,name:`${p.sku} · ${p.name}`}))},{key:'supplier_id',label:'Supplier',type:'select',required:true,options:data.suppliers.map(p=>({id:p.id,name:`${p.code} · ${p.name}`}))},{key:'batch_number',label:'Batch number',required:true,placeholder:'LOT-2026-001'},{key:'expiry_date',label:'Expiry date',type:'date',required:true}]},
    policy:{title:'New return policy',subtitle:'Version history is immutable and will be handled by the backend.',fields:[{key:'supplier_id',label:'Supplier',type:'select',required:true,options:data.suppliers.map(p=>({id:p.id,name:p.name}))},{key:'days_before_expiry',label:'Days before expiry',type:'number',required:true,min:0},{key:'days_after_expiry',label:'Days after expiry',type:'number',required:true,min:0},{key:'effective_from',label:'Effective from',type:'date',required:true},{key:'effective_to',label:'Effective until (optional)',type:'date'}]},
    verification:{title:'Verify physical stock',subtitle:'A physical count requires an independent reviewer. This is not a supplier claim.',fields:[{key:'counted_quantity',label:'Physically counted units',type:'number',required:true,min:0},{key:'note',label:'Verification note (min. 10 characters)',required:true,placeholder:'Count checked at warehouse shelf A3'}]},
    'review-verification':{title:'Review physical count',subtitle:'Independent owner/admin approval required.',fields:[{key:'decision',label:'Decision',type:'select',required:true,options:[{id:'approved',name:'Approve'},{id:'rejected',name:'Reject'}]},{key:'reason',label:'Reason (min. 10 characters)',required:true,placeholder:'Quantity confirmed against shelf records'}]},
    claim:{title:'Prepare supplier claim',subtitle:'Allocate part of an approved physical verification.',fields:[{key:'quantity',label:'Units to claim',type:'number',required:true,min:1},{key:'note',label:'Claim note (min. 10 characters)',required:true,placeholder:'Return request prepared for supplier'}]},
    note:{title:state.record?.action==='approve'?'Record approval decision':'Confirm claim action',subtitle:state.record?.action==='approve'?'This is the existing claim. Give your independent approval reason for the audit log; no new claim is created or sent to the supplier.':'A note is required for the audit history.',fields:[{key:'note',label:'Decision reason (min. 10 characters)',required:true,placeholder:'Reviewed existing claim and supporting verification; approved for internal workflow only'}]},
    'supplier-response':{title:'Record supplier response',subtitle:'Staff-entered outcome; not externally verified.',fields:[{key:'accepted_quantity',label:'Accepted quantity',type:'number',required:true,min:0},{key:'rejected_quantity',label:'Rejected quantity',type:'number',required:true,min:0},{key:'note',label:'Outcome note',required:true,placeholder:'Supplier response recorded from return paperwork'}]},
    terms:{title:'Set expected credit terms',subtitle:'Financial amounts are stored in minor currency units.',fields:[{key:'currency',label:'Currency (3-letter code)',required:true,placeholder:'PKR'},{key:'unit_price_minor',label:'Price per accepted unit (minor units)',type:'number',required:true,min:1},{key:'note',label:'Evidence note',required:true,placeholder:'Expected credit from return invoice'}]},
    receipt:{title:'Record credit evidence',subtitle:'Requires separate review. This does not confirm bank payment.',fields:[{key:'amount_minor',label:'Amount (minor units)',type:'number',required:true,min:1},{key:'reference',label:'Receipt reference',required:true,placeholder:'CN-2026-023'},{key:'note',label:'Receipt note',required:true,placeholder:'Credit note received from supplier'}]},
    'review-receipt':{title:'Review credit evidence',subtitle:'Internal reconciliation only.',fields:[{key:'decision',label:'Decision',type:'select',required:true,options:[{id:'approved',name:'Approve'},{id:'rejected',name:'Reject'}]},{key:'reason',label:'Reason',required:true,placeholder:'Evidence matches supporting documents'}]},
  };
  const spec = kinds[state.kind];
  if(!spec)return null;
  const submit=async (e:FormEvent)=>{
    e.preventDefault();
    setValidationError('');
    if(state.kind==='supplier'||state.kind==='product') {
      const key=state.kind==='supplier'?'code':'sku';
      const candidate=normalizeCatalogIdentifier(value[key]??'');
      const max=key==='code'?50:80;
      if(!CATALOG_CODE_PATTERN.test(candidate)||candidate.length>max){
        setValidationError(`${key==='code'?'Supplier code':'Product SKU'} must start with a letter or number and contain only A-Z, 0-9, dots, hyphens or underscores (maximum ${max} characters).`);
        return;
      }
      await onSubmit({...value,[key]:candidate});
      return;
    }
    await onSubmit(value);
  };
  return <div className="modal-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div className="modal" role="dialog" aria-modal="true" aria-label={spec.title}>
    <div className="modal-head"><div><div className="section-kicker">BATCHTRACE / WORKFLOW</div><h3>{spec.title}</h3><p>{spec.subtitle}</p></div><button className="icon-button" onClick={onClose} aria-label="Close"><X size={20}/></button></div>
    <form className="modal-form" onSubmit={submit}>
      {spec.fields.map(f=><label key={f.key}>{f.label}
        {f.type==='select'?<select required={f.required} value={value[f.key]??''} onChange={e=>setValue(v=>({...v,[f.key]:e.target.value}))}><option value="">Select…</option>{f.options?.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select>:<input type={f.type??'text'} min={f.min} maxLength={f.key==='code'?50:f.key==='sku'?80:undefined} required={f.required} placeholder={f.placeholder} value={value[f.key]??(f.type==='date'&&f.key==='effective_from'?todayVal():'')} onChange={e=>{setValidationError('');setValue(v=>({...v,[f.key]:e.target.value}));}} onBlur={e=>{if(f.key==='code'||f.key==='sku')setValue(v=>({...v,[f.key]:normalizeCatalogIdentifier(e.target.value)}));}}/>}</label>)}
      {(state.kind==='supplier'||state.kind==='product')&&<p className="catalog-code-hint">Codes use A-Z, 0-9, dots, dashes or underscores. Spaces are converted to dashes.</p>}
      {validationError&&<p className="catalog-code-error" role="alert">{validationError}</p>}
      <div className="modal-buttons"><button className="secondary-btn" type="button" onClick={onClose}>Cancel</button><button className="primary-btn" disabled={working}>{working?<Spinner/>:<><Check size={17}/> {state.kind==='note'&&state.record?.action==='approve'?'Record approval':'Save changes'}</>}</button></div>
    </form>
  </div></div>;
}

export function BatchTraceApp() {
  const [token,setToken]=useState<string|null>(()=>sessionStorage.getItem(SESSION));
  const knownOrganizations=useRef<string[]>([]);
  const loadGeneration=useRef(0);
  const creditGeneration=useRef(0);
  const [user,setUser]=useState<User|null>(null); const [orgs,setOrgs]=useState<Organization[]>([]);
  const [activeOrg,setActiveOrg]=useState(''); const [section,setSection]=useState<Section>('overview');
  const [data,setData]=useState<Data>(emptyData); const [failures,setFailures]=useState<string[]>([]);
  const [busy,setBusy]=useState(false); const [loading,setLoading]=useState(false); const [booting,setBooting]=useState(!!token);
  const [message,setMessage]=useState(''); const [error,setError]=useState(''); const [modal,setModal]=useState<ModalState>(null);
  const [search,setSearch]=useState(''); const [mobileNav,setMobileNav]=useState(false);
  const [evidence,setEvidence]=useState<EvidenceSelection|null>(null);
  const [claimDetailId,setClaimDetailId]=useState<string|null>(null);
  const [expandedGroup,setExpandedGroup]=useState<string>('Workspace');
  const [file,setFile]=useState<File|null>(null); const [observed,setObserved]=useState(todayVal()); const [preview,setPreview]=useState<CsvPreview|null>(null);
  const [selectedClaim,setSelectedClaim]=useState(''); const [credit,setCredit]=useState<CreditSummary|null>(null);
  const [receipts,setReceipts]=useState<CreditReceipt[]>([]); const [creditLoading,setCreditLoading]=useState(false);
  const org=orgs.find(o=>o.id===activeOrg); const root=org?`/organizations/${org.id}`:'';
  const role=workspaceRole(org?.role);
  // Actionable requests come from OTHER workspace members only; API approval rules remain authoritative.
  const canReview=role==='owner'||role==='admin';
  const pendingClaims=canReview&&user?data.claims.filter(x=>x.status==='draft'&&x.submitted_by_user_id!==user.id):[];
  const pendingChecks=canReview&&user?data.verifications.filter(x=>x.status==='pending'&&x.submitted_by_user_id!==user.id):[];
  const approvalCount=pendingClaims.length+pendingChecks.length;
  const logout=useCallback(()=>{loadGeneration.current+=1;creditGeneration.current+=1;knownOrganizations.current=[];sessionStorage.removeItem(SESSION);setToken(null);setUser(null);setOrgs([]);setActiveOrg('');setData(emptyData);setCredit(null);setSelectedClaim('');},[]);
  const initialize=useCallback(async (t:string)=>{
    try{const [who,organizations]=await Promise.all([api<User>('/auth/me',t),api<Organization[]>('/organizations/me',t)]);
      knownOrganizations.current=organizations.map(x=>x.id);setToken(t);sessionStorage.setItem(SESSION,t);setUser(who);setOrgs(organizations);
      setActiveOrg(previous=>organizations.some(o=>o.id===previous)?previous:(organizations[0]?.id??''));
    }catch(e){logout();throw e;}
  },[logout]);
  useEffect(()=>{if(!token){setBooting(false);return;}initialize(token).catch(()=>{setError('Session expired. Please sign in again.');}).finally(()=>setBooting(false));/* only restore once */ // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  // Team membership is independent of the JWT. Refresh against the DB without re-login.
  const syncWorkspaces=useCallback(async()=>{
    if(!token)return;
    try{
      const latest=await api<Organization[]>('/organizations/me',token);
      if(sessionStorage.getItem(SESSION)!==token)return;
      const newlyAdded=latest.filter(x=>!knownOrganizations.current.includes(x.id));
      knownOrganizations.current=latest.map(x=>x.id);
      setOrgs(latest);
      setActiveOrg(current=>{
        if(latest.some(x=>x.id===current))return current;
        loadGeneration.current+=1;creditGeneration.current+=1;
        setData(emptyData);setCredit(null);setSelectedClaim('');
        return latest[0]?.id??'';
      });
      if(newlyAdded.length)setMessage(`New workspace available: ${newlyAdded.map(x=>x.name).join(', ')}. Select it from the workspace menu.`);
    }catch(e){setError(`Workspace refresh failed: ${messageOf(e)}`);}
  },[token]);
  useEffect(()=>{
    if(!token)return;
    const onFocus=()=>{void syncWorkspaces();};
    const onVisibility=()=>{if(document.visibilityState==='visible')void syncWorkspaces();};
    window.addEventListener('focus',onFocus);
    document.addEventListener('visibilitychange',onVisibility);
    const poll=window.setInterval(()=>{if(document.visibilityState==='visible')void syncWorkspaces();},30000);
    return ()=>{window.removeEventListener('focus',onFocus);document.removeEventListener('visibilitychange',onVisibility);window.clearInterval(poll);};
  },[token,syncWorkspaces]);
  const reload=useCallback(async()=>{
    if(!token||!root)return;
    const generation=++loadGeneration.current;
    setLoading(true);setFailures([]);
    const endpoints = [
      ['suppliers','/suppliers'],['products','/products'],['lots','/lots'],['policies','/return-policies'],
      ['imports','/imports'],['opportunities','/recovery/opportunities'],['verifications','/recovery/verifications'],['claims','/recovery/claims'],
    ] as const;
    const resolved=await Promise.allSettled(endpoints.map(([,p])=>api<unknown[]>(root+p+'?limit=100',token)));
    const next={...emptyData}; const missing:string[]=[];
    for(let i=0;i<endpoints.length;i++){
      const [key]=endpoints[i];const result=resolved[i];
      if(result.status==='fulfilled'){(next as unknown as Record<string,unknown[]>)[key]=result.value;}
      else {missing.push(`${key}: ${messageOf(result.reason)}`);}
    }
    if(generation!==loadGeneration.current)return;
    setData(next);setFailures(missing);setLoading(false);
    if(missing.length===endpoints.length&&resolved.some(x=>x.status==='rejected'&&(x.reason as ApiError)?.status===401))logout();
  },[root,token,logout]);
  useEffect(()=>{void reload();},[reload]);
  const loadCredits=useCallback(async(claimId:string)=>{
    if(!claimId||!token||!root){creditGeneration.current+=1;setCredit(null);setReceipts([]);return;}
    const generation=++creditGeneration.current;
    setCreditLoading(true);setCredit(null);
    const [s,r]=await Promise.allSettled([api<CreditSummary>(`${root}/recovery/claims/${claimId}/credit-summary`,token),api<CreditReceipt[]>(`${root}/recovery/claims/${claimId}/credit-receipts`,token)]);
    if(generation!==creditGeneration.current)return;
    setCredit(s.status==='fulfilled'?s.value:null);setReceipts(r.status==='fulfilled'?r.value:[]);
    if(s.status==='rejected'&&(s.reason as ApiError)?.status!==404)setError(messageOf(s.reason));
    setCreditLoading(false);
  },[token,root]);
  useEffect(()=>{void loadCredits(selectedClaim);},[selectedClaim,loadCredits]);
  // Lightweight cross-session updates: no webhook, WebSocket server or extra services.
  // Refresh status-bearing sections only while the browser tab is visible.
  const liveBusy = useRef(false);
  const refreshLive = useCallback(async () => {
    if (!token || !root || liveBusy.current) return;
    if (document.visibilityState !== 'visible') return;
    liveBusy.current = true;
    const version = loadGeneration.current;
    const sourceToken = token;
    const keys = [
      ['opportunities', '/recovery/opportunities'],
      ['verifications', '/recovery/verifications'],
      ['claims', '/recovery/claims'],
    ] as const;
    try {
      const response = await Promise.allSettled(keys.map(([,path]) =>
        api<unknown[]>(`${root}${path}?limit=100`, sourceToken)
      ));
      if (version !== loadGeneration.current || sessionStorage.getItem(SESSION) !== sourceToken) return;
      setData(previous => {
        let changed = false;
        const updated = {...previous};
        for (let index = 0; index < keys.length; index++) {
          const result = response[index];
          if (result.status !== 'fulfilled') continue;
          const key = keys[index][0];
          if (JSON.stringify(previous[key]) !== JSON.stringify(result.value)) {
            // Only the three live-status lists are updated; catalog and CSV data are preserved.
            (updated as unknown as Record<string,unknown[]>)[key] = result.value;
            changed = true;
          }
        }
        return changed ? updated : previous;
      });
      // Credit reconciliation lives behind its existing role-based access checks.
      // Keep this view up-to-date when another authorized reviewer records a decision.
      if (section === 'credits' && selectedClaim && canVisit(role, 'credits')) {
        const creditVersion = creditGeneration.current;
        const [summary, rows] = await Promise.allSettled([
          api<CreditSummary>(`${root}/recovery/claims/${selectedClaim}/credit-summary`, sourceToken),
          api<CreditReceipt[]>(`${root}/recovery/claims/${selectedClaim}/credit-receipts`, sourceToken),
        ]);
        if (version !== loadGeneration.current || creditVersion !== creditGeneration.current || sessionStorage.getItem(SESSION) !== sourceToken) return;
        if (summary.status === 'fulfilled') setCredit(previous => JSON.stringify(previous) === JSON.stringify(summary.value) ? previous : summary.value);
        if (rows.status === 'fulfilled') setReceipts(previous => JSON.stringify(previous) === JSON.stringify(rows.value) ? previous : rows.value);
      }
    } finally {
      liveBusy.current = false;
    }
  }, [token, root, section, selectedClaim, role]);
  useEffect(() => {
    if (!token || !root) return;
    const check = () => { if (document.visibilityState === 'visible' && navigator.onLine) void refreshLive(); };
    const onVisible = () => { if (document.visibilityState === 'visible') check(); };
    window.addEventListener('focus', check);
    window.addEventListener('online', check);
    document.addEventListener('visibilitychange', onVisible);
    const timer = window.setInterval(check, 8000);
    return () => {
      window.removeEventListener('focus', check);
      window.removeEventListener('online', check);
      document.removeEventListener('visibilitychange', onVisible);
      window.clearInterval(timer);
    };
  }, [token, root, refreshLive]);
  const downloadCsvTemplate = () => {
    const firstLot = data.lots[0];
    const product = data.products.find(p => p.id === firstLot?.product_id);
    const supplier = data.suppliers.find(s => s.id === firstLot?.supplier_id);
    const cell = (s:string) => '"' + s.replaceAll('"','""') + '"';
    const lines = ['product_sku,supplier_code,batch_number,expiry_date,quantity'];
    // Leave quantity blank: the user must enter physically observed units.
    if (firstLot && product && supplier) {
      lines.push([product.sku,supplier.code,firstLot.batch_number,firstLot.expiry_date,''].map(cell).join(','));
    }
    const blob = new Blob([lines.join('\r\n') + '\r\n'],{type:'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'batchtrace-stock-template.csv';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const navigate=(next:Section)=>{if(!canVisit(role,next)){setError('Your organization role does not allow this page.');return;}setSection(next);setExpandedGroup(allSections.find(item=>item.key===next)?.group??'Workspace');setSearch('');setMobileNav(false);setError('');};
  useEffect(()=>{if(!canVisit(role,section)){setSection('overview');setModal(null);}},[role,section]);
  async function doAction(v:FormValue){if(!token||!root||!modal)return;
    if(!canAct(role,modal.kind,String(modal.record?.action??''))){setError('Your role cannot perform this action.');setModal(null);return;}
    setBusy(true);setError('');setMessage('');
    const n=(key:string)=>Number(v[key]);const note=v.note?.trim()??'';const kind=modal.kind;const id=modal.id;
    try{
      if(kind==='supplier') await api(root+'/suppliers',token,json({code:v.code,name:v.name}));
      else if(kind==='product') await api(root+'/products',token,json({sku:v.sku,name:v.name}));
      else if(kind==='lot') await api(root+'/lots',token,json({product_id:v.product_id,supplier_id:v.supplier_id,batch_number:v.batch_number,expiry_date:v.expiry_date}));
      else if(kind==='policy') await api(root+'/return-policies',token,json({supplier_id:v.supplier_id,days_before_expiry:n('days_before_expiry'),days_after_expiry:n('days_after_expiry'),effective_from:v.effective_from??todayVal(),effective_to:v.effective_to||null}));
      else if(kind==='verification') await api(root+'/recovery/verifications',token,{...json({lot_id:modal.record?.lot_id,import_id:modal.record?.import_id,counted_quantity:n('counted_quantity'),note}),headers:{'Idempotency-Key':idem()}});
      else if(kind==='review-verification') await api(`${root}/recovery/verifications/${id}/review`,token,json({decision:v.decision,reason:v.reason}));
      else if(kind==='claim') await api(root+'/recovery/claims',token,{...json({verification_id:id,quantity:n('quantity'),note}),headers:{'Idempotency-Key':idem()}});
      else if(kind==='note') await api(`${root}/recovery/claims/${id}/${String(modal.record?.action)}`,token,json({note}));
      else if(kind==='supplier-response') await api(`${root}/recovery/claims/${id}/supplier-response`,token,json({note,accepted_quantity:n('accepted_quantity'),rejected_quantity:n('rejected_quantity')}));
      else if(kind==='terms') await api(`${root}/recovery/claims/${selectedClaim}/credit-terms`,token,json({currency:v.currency?.toUpperCase(),unit_price_minor:n('unit_price_minor'),note}));
      else if(kind==='receipt') await api(`${root}/recovery/claims/${selectedClaim}/credit-receipts`,token,{...json({reference:v.reference,amount_minor:n('amount_minor'),note}),headers:{'Idempotency-Key':idem()}});
      else if(kind==='review-receipt') await api(`${root}/recovery/claims/${selectedClaim}/credit-receipts/${id}/review`,token,json({decision:v.decision,reason:v.reason}));
      setModal(null);setMessage('Saved to BatchTrace successfully.');await reload();if(['terms','receipt','review-receipt'].includes(kind))await loadCredits(selectedClaim);
    }catch(err){setError(messageOf(err));}finally{setBusy(false);}}
  async function previewCsv(){if(!file||!token||!root)return;setBusy(true);setError('');setPreview(null);try{const fd=new FormData();fd.append('file',file);fd.append('observed_on',observed);setPreview(await api<CsvPreview>(root+'/imports/preview',token,{method:'POST',body:fd}));}catch(e){setError(messageOf(e));}finally{setBusy(false);}}
  async function commitCsv(){if(!file||!token||!root||!preview?.valid||!preview.fingerprint)return;if(!canAct(role,'import-commit')){setError('Viewers cannot commit inventory observations.');return;}setBusy(true);setError('');try{const fd=new FormData();fd.append('file',file);fd.append('observed_on',observed);fd.append('preview_fingerprint',preview.fingerprint);await api(root+'/imports/commit',token,{method:'POST',body:fd});setPreview(null);setFile(null);setMessage('Snapshot committed. It is still unverified observed stock.');await reload();}catch(e){setError(messageOf(e));}finally{setBusy(false);}}
  const verificationFor=(x:Opportunity)=>data.verifications.find(v=>v.lot_id===x.lot_id&&v.import_id===x.import_id);
  const signalReviewStatus=(x:Opportunity)=>{
    const check=verificationFor(x);
    return check?<Tag tone={statusTone(check.status)}>{check.status==='pending'?'Pending review':check.status==='approved'?'Physical count approved':'Physical count rejected'}</Tag>:<Tag tone={statusTone(x.opportunity_status)}>{niceStatus(x.opportunity_status)}</Tag>;
  };
  const signalAction=(x:Opportunity)=>{
    const check=verificationFor(x);
    if(check)return <button className="secondary-btn small" onClick={()=>navigate('verifications')}>View physical check</button>;
    return x.opportunity_status==='verify_stock'&&canAct(role,'verification')?secButton('verification','Verify units',undefined,{lot_id:x.lot_id,import_id:x.import_id}):<span className="dim">Read only</span>;
  };
  const findProduct=(id:string)=>data.products.find(x=>x.id===id)?.sku??id.slice(0,8);
  const findSupplier=(id:string)=>data.suppliers.find(x=>x.id===id)?.name??id.slice(0,8);
  const visible=<T,>(items:T[]):T[]=>items.filter(x=>JSON.stringify(x).toLowerCase().includes(search.toLowerCase()));
  const counts = useMemo(()=>({actionable:data.opportunities.filter(x=>x.opportunity_status==='verify_stock').length,
    pending:data.verifications.filter(x=>x.status==='pending').length,
    active:data.claims.filter(x=>['draft','approved','dispatched'].includes(x.status)).length,
    soon:data.lots.filter(x=>{const days=Math.ceil((new Date(x.expiry_date+'T12:00:00').getTime()-Date.now())/86400000);return days>=0&&days<=30;}).length,
  }),[data]);
  const statuses=useMemo(()=>Object.entries(data.opportunities.reduce<Record<string,number>>((acc,x)=>{acc[x.opportunity_status]=(acc[x.opportunity_status]??0)+1;return acc;},{})).sort((a,b)=>b[1]-a[1]),[data.opportunities]);
  function secButton(kind:string,title:string,id?:string,record?:Record<string,unknown>){return canAct(role,kind,String(record?.action??''))?<button className="secondary-btn small" onClick={()=>setModal({kind,id,record})}>{title}</button>:<span className="dim">Restricted</span>}
  function viewTable(headers:string[],rows:ReactNode[][],icon:LucideIcon,emptyTitle:string){return <div className="panel table-panel">{rows.length===0?<Empty icon={icon} title={emptyTitle} caption={search?'No matching results in the current loaded page.':'There are no records yet. Create or import data to get started.'}/>:<div className="table-scroll"><table><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={i}>{row.map((value,j)=><td key={j}>{value}</td>)}</tr>)}</tbody></table></div>}</div>}
  function header(title:string,eyebrow:string,subtitle:string,action?:ReactNode){return <div className="page-heading"><div><div className="section-kicker">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>}
  const btnAdd=(label:string,kind:string)=> canAct(role,kind)?<button className="primary-btn" onClick={()=>setModal({kind})}><Plus size={17}/>{label}</button>:<span className="role-readonly">Read-only access</span>;

  if(booting)return <div className="boot-screen"><GlowLogo/><Spinner/><span>Preparing your workspace</span></div>;
  if(!token||!user)return <Auth onAuth={initialize}/>;
  if(orgs.length===0)return <div className="boot-screen"><GlowLogo/><h2>No organization access</h2><p>Please ask your administrator to add you to an organization.</p><button className="secondary-btn" onClick={logout}>Sign out</button></div>;
  return <div className="app-shell">
    <div className="ambient ambient-one"/><div className="ambient ambient-two"/>
    <aside className={'sidebar '+(mobileNav?'show-sidebar':'')}>
      <div className="sidebar-brand"><GlowLogo small/><span>batchtrace<span className="brand-dot">.</span></span><button className="mobile-close icon-button" onClick={()=>setMobileNav(false)}><X size={18}/></button></div>
      <div className="workspace-switch"><span className="workspace-avatar">{org?.name?.charAt(0).toUpperCase()}</span><div><small>ACTIVE WORKSPACE</small><select aria-label="Choose organization" value={activeOrg} onChange={e=>{loadGeneration.current+=1;creditGeneration.current+=1;setCredit(null);setData(emptyData);setActiveOrg(e.target.value);setSelectedClaim('');setSection('overview');setModal(null);setEvidence(null);setClaimDetailId(null);setMessage('');}}>{orgs.map(o=><option key={o.id} value={o.id}>{o.name} · {o.role}</option>)}</select></div><ChevronDown size={15}/></div>
      <button type="button" className="workspace-reload" onClick={()=>void syncWorkspaces()}><RefreshCw size={13}/> Refresh workspaces</button><nav className="sidebar-navigation" aria-label="Main navigation">
        {['Workspace','Inventory','Recovery'].map(group=><div key={group} className="nav-group">
          <button type="button" className="nav-group-toggle" aria-expanded={expandedGroup===group} aria-controls={`batchtrace-nav-${group.toLowerCase()}`} onClick={()=>setExpandedGroup(previous=>previous===group?'':group)}>
            <span className="nav-group-label">{group}</span>
            <span className="nav-group-count">{allSections.filter(x=>x.group===group).length}</span>
            <ChevronDown size={15} className="nav-group-chevron"/>
          </button>
          <div className="nav-group-items" id={`batchtrace-nav-${group.toLowerCase()}`} hidden={expandedGroup!==group}>
            {expandedGroup===group&&allSections.filter(x=>x.group===group&&canVisit(role,x.key)).map(({key,title,icon:Icon})=><button type="button" key={key} onClick={()=>navigate(key)} aria-current={section===key?'page':undefined} className={'nav-item '+(section===key?'active':'')}><Icon size={18}/><span>{title}</span>{key==='approvals'&&approvalCount>0&&<span className="approval-inbox-nav-count">{approvalCount}</span>}{section===key?<span className="active-spot"/>:null}</button>)}
          </div>
        </div>)}
      </nav>
      <div className="sidebar-bottom"><div className="status-card"><span className="status-beacon"/><div><strong>Local API connected</strong><small>FastAPI · PostgreSQL</small></div></div><button className="user-chip" onClick={logout}><div className="user-avatar"><UserRound size={17}/></div><span><strong>{user.email.split('@')[0]}</strong><small>{org?.role??'Member'} · Sign out</small></span><LogOut size={17}/></button></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="top-left"><button className="mobile-menu icon-button" onClick={()=>setMobileNav(true)} aria-label="Open navigation"><Menu size={22}/></button><span className="bread-muted">Workspace</span><ChevronRight size={15} className="bread-chevron"/><span className="bread-current">{allSections.find(x=>x.key===section)?.title}</span><span className="tag tag-muted">{role}</span></div><div className="top-right">{canReview&&<button type="button" className="approval-inbox-bell" aria-label={`Open approval inbox, ${approvalCount} pending`} title={`${approvalCount} approval requests need your review`} onClick={()=>navigate('approvals')}><BellRing size={16}/>{approvalCount>0&&<span>{approvalCount}</span>}</button>}<span className="live-sync-hint" title="Status data refreshes every 8 seconds while the tab is visible"><span aria-hidden="true" className="live-sync-dot"/> Auto sync</span><span className="secure-label"><ShieldCheck size={16}/> Organization-scoped</span><button className="icon-button refresh-button" title="Refresh real API data" onClick={()=>{void syncWorkspaces();void reload();}} disabled={loading}><RefreshCw size={18} className={loading?'spinning':''}/></button><div className="mini-avatar">{user.email.charAt(0).toUpperCase()}</div></div></header>
      <div className="page-content" key={section}>
        {error&&<div className="toast danger-toast" role="alert"><CircleAlert size={17}/><span>{error}</span><button onClick={()=>setError('')}><X size={16}/></button></div>}
        {message&&<div className="toast success-toast" role="status"><CheckCircle2 size={17}/><span>{message}</span><button onClick={()=>setMessage('')}><X size={16}/></button></div>}
        {failures.length>0&&<div className="toast danger-toast"><CircleAlert size={17}/>Some API sections failed to load. <button className="text-link" onClick={()=>setError(failures.join(' | '))}>View details</button></div>}
        {section==='overview'&&<>
          <div className="workspace-role-note"><ShieldCheck size={16}/> You are a {role} in {org?.name}. Permissions apply to this workspace only; switch workspaces to see your other roles.</div>
          {canReview&&approvalCount>0&&<button className="approval-inbox-banner" type="button" onClick={()=>navigate('approvals')}><BellRing size={18}/>{approvalCount} request{approvalCount!==1?'s':''} waiting for your independent review. Open Approval inbox to read what your team submitted.<ArrowRight size={16}/></button>}
          {header(roleCopy[role].title,roleCopy[role].eyebrow,roleCopy[role].description,<button className="secondary-btn" onClick={()=>navigate('imports')}><CloudUpload size={17}/> Import stock CSV</button>)}
          <div className="hero-banner"><div className="hero-pattern"/><div className="hero-content"><div className="hero-eyebrow"><Sparkles size={14}/> MAKE EVERY BATCH MATTER</div><h2>{role==='owner'?'Lead with clarity.':role==='admin'?'Keep reviews moving.':role==='staff'?'One task at a time.':'Stay informed.'}<br/><span>{role==='owner'?'Recover more.':role==='admin'?'Keep stock safe.':role==='staff'?'Keep stock moving.':'See the progress.'}</span></h2><p>{roleCopy[role].description}</p><button className="hero-cta" onClick={()=>navigate(role==='admin'?'verifications':role==='staff'?'imports':'opportunities')}>{role==='admin'?'Review checks':role==='staff'?'Upload observations':'Explore opportunities'} <ArrowUpRight size={18}/></button></div><div className="hero-visual"><IntroVisual compact/></div></div>
          {!loading && failures.length === 0 && <SetupGuide
            suppliers={data.suppliers.length}
            products={data.products.length}
            lots={data.lots.length}
            policies={data.policies.length}
            imports={data.imports.length}
            onNavigate={navigate}
            onDownloadTemplate={downloadCsvTemplate}
          />}
          <div className="kpi-grid">
            {[
              {l:'Batches expiring ≤30d',v:counts.soon,icon:Clock3,tag:'Lot metadata',color:'purple'},
              {l:'Open return windows',v:counts.actionable,icon:Zap,tag:'Policy eligible',color:'teal'},
              {l:'Physical checks pending',v:counts.pending,icon:ShieldCheck,tag:'Waiting for review',color:'amber'},
              {l:'Active supplier claims',v:counts.active,icon:FileCheck2,tag:'Staff workflow',color:'blue'},
            ].map((x,i)=><div className={'kpi-card kpi-'+x.color} key={x.l} style={{animationDelay:`${i*70}ms`}}><div className="kpi-top"><span>{x.l}</span><div className="kpi-icon"><x.icon size={19}/></div></div><div className="kpi-value">{loading?<Spinner/>:x.v}<span className="kpi-arrow"><ArrowUpRight size={16}/></span></div><div className="kpi-foot"><span className="kpi-dash"/>{x.tag}</div></div>)}
          </div>
          <div className="dashboard-grid"><div className="panel chart-panel"><div className="panel-title"><div><h3>Recovery pulse</h3><p>Actual advisory statuses · loaded observations</p></div><Tag tone="muted">Live API</Tag></div>
            {statuses.length===0?<Empty icon={Activity} title="No opportunity data yet" caption="Import your first CSV stock snapshot to populate recovery signals."/>:<div className="pulse-list">{statuses.slice(0,7).map(([name,num],i)=><div className="pulse-row" key={name}><span>{niceStatus(name)}</span><div className="pulse-track"><span style={{width:`${Math.max(3,num/Math.max(1,data.opportunities.length)*100)}%`,animationDelay:`${i*110}ms`}}/></div><strong>{num}</strong></div>)}</div>}
            <div className="panel-footnote">Counts are from up to 100 loaded records per section, not global totals.</div>
          </div><div className="panel activity-panel"><div className="panel-title"><div><h3>Next actions</h3><p>Quick access to your workflow</p></div><ArrowUpRight size={19}/></div><div className="quick-actions">{[
              {title:'Inspect recovery signals',desc:'Review return windows',icon:Zap,s:'opportunities' as Section},
              {title:'Upload stock observation',desc:'Preview before commit',icon:UploadCloud,s:'imports' as Section},
              {title:'Review physical checks',desc:'Independent sign-off',icon:FileCheck2,s:'verifications' as Section},
              {title:'Reconcile credits',desc:'Staff-recorded evidence',icon:CreditCard,s:'credits' as Section},
            ].filter(q=>canVisit(role,q.s)).filter(q=>role!=='viewer'||q.s==='opportunities').filter(q=>role!=='staff'||q.s!=='credits').map(q=><button key={q.title} onClick={()=>navigate(q.s)} className="quick-action"><div><q.icon size={18}/></div><span><strong>{q.title}</strong><small>{q.desc}</small></span><ArrowRight size={17}/></button>)}</div></div></div>
        </>}
        {canReview&&section==='approvals'&&<>{header('Approval inbox','WORKSPACE / REVIEWS','Read what your team submitted before recording a decision.')}<ApprovalInbox key={`${root}-${user.id}`} root={root} token={token} viewerId={user.id} claims={data.claims} verifications={data.verifications} lots={data.lots} products={data.products} suppliers={data.suppliers} onClaim={id=>setClaimDetailId(id)} onVerification={id=>setEvidence({kind:'verification',id})}/></>}
        {canVisit(role,'team')&&section==='team'&&<>{header('Team members','WORKSPACE / ACCESS CONTROL','Give existing registered users access and assign independent reviewers.')}<TeamPanel key={root} root={root} token={token} myRole={org?.role??'viewer'} myId={user.id}/></>}
        {section==='suppliers'&&<>{header('Suppliers','INVENTORY / CONTACTS','Organization-scoped supplier directory.',btnAdd('Add supplier','supplier'))}{<SearchBox value={search} onChange={setSearch}/>}{viewTable(['SUPPLIER CODE','NAME','CREATED'],visible(data.suppliers).map(x=>[<span key="cell-0" className="mono">{x.code}</span>,<strong key="cell-1">{x.name}</strong>,formatDate(x.created_at)]),Truck,'No suppliers yet')}</>}
        {section==='products'&&<>{header('Products','INVENTORY / CATALOG','Maintain a clean SKU catalog for batch observations.',btnAdd('Add product','product'))}<SearchBox value={search} onChange={setSearch}/>{viewTable(['SKU','PRODUCT NAME','CREATED'],visible(data.products).map(x=>[<span key="cell-0" className="mono">{x.sku}</span>,<strong key="cell-1">{x.name}</strong>,formatDate(x.created_at)]),Package,'No products yet')}</>}
        {section==='lots'&&<>{header('Batches & expiry','INVENTORY / LOT TRACKING','Register expiry metadata. These are not confirmed stock balances.',btnAdd('Register batch','lot'))}<SearchBox value={search} onChange={setSearch}/>{viewTable(['BATCH','PRODUCT','SUPPLIER','EXPIRY','STATUS'],visible(data.lots).map(x=>[<span key="cell-0" className="mono">{x.batch_number}</span>,findProduct(x.product_id),findSupplier(x.supplier_id),formatDate(x.expiry_date),<Tag key="cell-4" tone={new Date(x.expiry_date+'T23:59:59')<new Date()?'danger':'muted'}>{new Date(x.expiry_date+'T23:59:59')<new Date()?'Expired':'Tracked'}</Tag>]),Boxes,'No registered batches')}</>}
        {section==='policies'&&<>{header('Return policies','INVENTORY / RULE ENGINE','Versioned supplier return windows. Policy records are not editable in place.',btnAdd('Add policy','policy'))}<SearchBox value={search} onChange={setSearch}/>{viewTable(['SUPPLIER','VERSION','BEFORE','AFTER','EFFECTIVE','ENDS'],visible(data.policies).map(x=>[findSupplier(x.supplier_id),<Tag key="cell-1" tone="muted">v{x.version}</Tag>,`${x.days_before_expiry} days`,`${x.days_after_expiry} days`,formatDate(x.effective_from),formatDate(x.effective_to)]),CalendarDays,'No return policies')}</>}
        {section==='imports'&&<>{header('CSV observations','INVENTORY / SNAPSHOTS','Preview and validate before committing stock observations to PostgreSQL.')}
          <div className="panel upload-panel"><div className="upload-head"><div className="upload-symbol"><UploadCloud size={24}/></div><div><h3>Import a stock snapshot</h3><p>CSV only · observed data, not authoritative inventory</p></div></div>
            <div className="upload-grid"><label className="file-zone"><FileSpreadsheet size={26}/><strong>{file?.name??'Choose CSV stock file'}</strong><span>{file?'Click to replace file':'Click to browse · 2 MB maximum'}</span><input type="file" accept=".csv,text/csv" onChange={e=>{setFile(e.target.files?.[0]??null);setPreview(null);}}/></label><div className="upload-side"><label>Observation date<input type="date" value={observed} max={todayVal()} onChange={e=>{setObserved(e.target.value);setPreview(null);}}/></label><button className="primary-btn" disabled={!file||busy} onClick={()=>void previewCsv()}>{busy?<Spinner/>:<><Eye size={17}/> Preview & validate</>}</button></div></div>
            <div className="csv-format">Expected columns: <code>product_sku,supplier_code,batch_number,expiry_date,quantity</code></div>
            {preview&&<div className="preview-result"><div className="preview-head"><Tag tone={preview.valid?'good':'danger'}>{preview.valid?'Valid preview':'Needs correction'}</Tag><span>{preview.valid_rows}/{preview.total_rows} rows accepted</span></div>{preview.errors.length>0&&<ul>{preview.errors.slice(0,10).map((x,i)=><li key={i}>Line {x.line}: {x.message}</li>)}</ul>}{preview.valid&&canAct(role,'import-commit')&&<button disabled={busy} className="primary-btn" onClick={()=>void commitCsv()}><Check size={17}/> Commit verified preview</button>}</div>}
          </div><div className="subsection-header"><h3>Import history</h3><Tag tone="muted">Snapshots only</Tag></div>{viewTable(['FILE','OBSERVED ON','ROWS','IMPORTED'],visible(data.imports).map(x=>[<button key="cell-0" className="evidence-file-button" onClick={()=>setEvidence({kind:'import',id:x.id})} title="View recorded snapshot rows">{x.filename}</button>,formatDate(x.observed_on),x.row_count,formatDate(x.created_at)]),FileSpreadsheet,'No CSV imports yet')}</>}
        {canVisit(role,'opportunities')&&section==='opportunities'&&<>{header('Recovery signals','RECOVERY / ADVISORY','Explainable return windows from the latest eligible stock observations.')}<div className="subtle-callout"><CircleAlert size={18}/><span>Observed quantities are unverified. A recovery signal is not a confirmed supplier claim.</span></div><SearchBox value={search} onChange={setSearch}/>{viewTable(['LOT / PRODUCT','SUPPLIER','OBSERVED','RETURN DEADLINE','DECISION','ACTION'],visible(data.opportunities).map(x=>[<div key="cell-0"><strong>{x.product_sku}</strong><small>{x.batch_number}</small></div>,x.supplier_code,<div key="cell-2"><strong>{x.observed_quantity} units</strong><small>{formatDate(x.observed_on)}</small></div>,formatDate(x.return_closes_on),signalReviewStatus(x),signalAction(x)]),Zap,'No recovery signals')}</>}
        {section==='verifications'&&<>{header('Physical checks','RECOVERY / VERIFICATION','Independent verification before creating supplier claims.')}<SearchBox value={search} onChange={setSearch}/>{viewTable(['VERIFICATION','LOT','COUNT','SUBMITTED','STATUS','ACTION'],visible(data.verifications).map(x=>[<ShortId key="cell-0" id={x.id}/>,findProduct(data.lots.find(l=>l.id===x.lot_id)?.product_id??x.lot_id),x.counted_quantity,formatDate(x.created_at),<Tag key="cell-4" tone={statusTone(x.status)}>{niceStatus(x.status)}</Tag>,<div key="cell-5" className="inline-actions"><button className="secondary-btn small" onClick={()=>setEvidence({kind:'verification',id:x.id})}>{x.status==='pending'?'Review evidence':'View evidence'}</button>{x.status==='approved'&&secButton('claim','Create claim',x.id)}</div>]),ShieldCheck,'No physical checks')}</>}
        {section==='claims'&&<>{header('Supplier claims','RECOVERY / CLAIMS','Track claims through internal approval, dispatch and staff-recorded outcomes.')}<SearchBox value={search} onChange={setSearch}/>{viewTable(['CLAIM','QUANTITY','ACCEPTED','STATUS','CREATED','NEXT STEP'],visible(data.claims).map(x=>[<button key="cell-0" type="button" className="claim-table-id" title="Read claim details" onClick={()=>setClaimDetailId(x.id)}><ShortId id={x.id}/></button>,x.quantity,x.accepted_quantity,<Tag key="cell-3" tone={statusTone(x.status)}>{niceStatus(x.status)}</Tag>,formatDate(x.created_at),<div key="cell-5" className="inline-actions">{x.status==='draft'&&(x.submitted_by_user_id===user.id?<span className="dim">Awaiting another approver</span>:['owner','admin'].includes(role)?<button type="button" className="secondary-btn small" onClick={()=>setClaimDetailId(x.id)}>Review claim</button>:<span className="dim">Admin review required</span>)}{x.status==='approved'&&secButton('note','Dispatch',x.id,{action:'dispatch'})}{x.status==='dispatched'&&secButton('supplier-response','Record response',x.id)}{canVisit(role,'credits')&&['accepted','rejected','partially_accepted'].includes(x.status)&&<button className="secondary-btn small" onClick={()=>{setSelectedClaim(x.id);navigate('credits')}}>View credits</button>}</div>]),FileCheck2,'No claims yet')}</>}
        {canVisit(role,'credits')&&section==='credits'&&<>{header('Credit reconciliation','RECOVERY / FINANCIAL EVIDENCE','Record and review supplier credits internally. Not bank-confirmed payments.')}<div className="panel credit-panel"><div className="panel-title"><div><h3>Claim reconciliation</h3><p>Select a completed supplier-response claim.</p></div><CreditCard size={20}/></div><label className="wide-select">Supplier claim<select value={selectedClaim} onChange={e=>setSelectedClaim(e.target.value)}><option value="">Select claim…</option>{data.claims.map(x=><option key={x.id} value={x.id}>{x.id.slice(0,8)} · {niceStatus(x.status)} · {x.quantity} units</option>)}</select></label>{creditLoading?<div className="center-loading"><Spinner/></div>:selectedClaim?(credit?<><div className="credit-summary-grid"><div><small>Expected credit</small><strong>{money(credit.expected_minor,credit.currency)}</strong></div><div><small>Approved recorded credit</small><strong>{money(credit.approved_recorded_minor,credit.currency)}</strong></div><div><small>Outstanding unapproved</small><strong>{money(credit.outstanding_unapproved_minor,credit.currency)}</strong></div></div><div className="credit-bottom"><Tag tone={statusTone(credit.reconciliation_status)}>{niceStatus(credit.reconciliation_status)}</Tag>{btnAdd('Add credit receipt','receipt')}</div></>:<div className="no-terms"><CircleAlert size={19}/><span>Credit terms have not been recorded for this claim yet.</span>{btnAdd('Record terms','terms')}</div>):<Empty icon={Wallet} title="Select a claim" caption="Choose a claim above to see its credit reconciliation evidence."/>}</div>
          {selectedClaim&&credit&&<><div className="subsection-header"><h3>Credit receipts</h3><Tag tone="muted">Staff-recorded, not bank-verified</Tag></div>{viewTable(['REFERENCE','AMOUNT','STATUS','SUBMITTED','ACTION'],receipts.map(r=>[<span key="cell-0" className="mono">{r.reference}</span>,money(r.amount_minor,credit.currency),<Tag key="cell-2" tone={statusTone(r.status)}>{r.status}</Tag>,formatDate(r.created_at),r.status==='pending'?secButton('review-receipt','Review',r.id):<span className="dim">—</span>]),Wallet,'No credit receipts')}</>}
        </>}
      </div>
      <footer className="app-footer"><span>BatchTrace Recovery OS</span><span>Self-hosted API · Local PostgreSQL · No external integrations</span></footer>
    </main>
    {mobileNav&&<div className="mobile-overlay" onClick={()=>setMobileNav(false)}/>}
    <ClaimDetailPanel key={`${root}:${claimDetailId ?? ''}`} claimId={claimDetailId} root={root} token={token} viewerId={user.id} role={role} lots={data.lots} products={data.products} suppliers={data.suppliers} onClose={()=>setClaimDetailId(null)} onShowVerification={id=>{setClaimDetailId(null);setEvidence({kind:'verification',id});}} onApprove={id=>setModal({kind:'note',id,record:{action:'approve'}})}/>
    <EvidencePanel key={`${root}:${evidence?.kind ?? ''}:${evidence?.id ?? ''}`} selection={evidence} root={root} token={token} lots={data.lots} products={data.products} suppliers={data.suppliers} policies={data.policies} viewerId={user.id} role={role} onClose={()=>setEvidence(null)} onReview={id=>setModal({kind:'review-verification',id})}/>
    <FormModal key={`${root}:${modal?.kind??'closed'}:${modal?.id??''}:${String(modal?.record?.action??'')}`} state={modal} onClose={()=>setModal(null)} onSubmit={doAction} working={busy} data={data}/>
  </div>;
}
function SearchBox({value,onChange}:{value:string;onChange:(s:string)=>void}) {return <div className="list-tools"><div className="search-box"><Search size={18}/><input aria-label="Filter loaded records" placeholder="Search loaded records…" value={value} onChange={e=>onChange(e.target.value)}/></div><span className="loaded-notice"><Activity size={14}/> Showing up to 100 records</span></div>}
