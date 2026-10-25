import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowRight, ClipboardCheck, Clock3, FileCheck2, FileSpreadsheet, ShieldCheck, X } from 'lucide-react';
import { api, messageOf } from './api';
import type { Claim, Lot, Product, Supplier, Verification } from './types';
import './step26-claim-details.css';

type ClaimEvent = {
  id:string;
  claim_id:string;
  actor_user_id:string;
  event_type:'created'|'approved'|'dispatched'|'supplier_response_recorded';
  note:string;
  created_at:string;
};
type FullClaim = Claim & {
  organization_id:string;
  events:ClaimEvent[];
  is_external_supplier_confirmation:false;
  changes_inventory_balance:false;
};
type FullVerification = Verification & {organization_id:string;policy_id:string;snapshot_row_id:string};
type Props = {
  claimId:string|null;
  root:string;
  token:string|null;
  viewerId:string;
  role:string;
  lots:Lot[];
  products:Product[];
  suppliers:Supplier[];
  onClose:()=>void;
  onShowVerification:(verificationId:string)=>void;
  onApprove:(claimId:string)=>void;
};
const pretty=(s:string)=>s.replaceAll('_',' ').replace(/\b\w/g,x=>x.toUpperCase());
const stamp=(s?:string)=>{
  if(!s)return '—';
  const date=new Date(s.includes('T')?s:`${s}T12:00:00`);
  return Number.isNaN(date.valueOf())?s:date.toLocaleString('en-US',{month:'short',day:'numeric',year:'numeric',hour:s.includes('T')?'numeric':undefined,minute:s.includes('T')?'2-digit':undefined});
};
const short=(id?:string)=>id?`${id.slice(0,8)}…`:'—';

export function ClaimDetailPanel({claimId,root,token,viewerId,role,lots,products,suppliers,onClose,onShowVerification,onApprove}:Props){
  const [claim,setClaim]=useState<FullClaim|null>(null);
  const [verification,setVerification]=useState<FullVerification|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [reviewed,setReviewed]=useState(false);

  useEffect(()=>{
    if(!claimId||!token||!root)return;
    let active=true;
    const load=async()=>{
      try{
        const detail=await api<FullClaim>(`${root}/recovery/claims/${claimId}`,token);
        const check=await api<FullVerification>(`${root}/recovery/verifications/${detail.verification_id}`,token);
        const orgId=root.split('/').pop();
        if(detail.organization_id!==orgId||check.organization_id!==orgId||check.id!==detail.verification_id){
          throw new Error('Claim and verification do not belong to the selected workspace');
        }
        if(active){setClaim(detail);setVerification(check);}
      }catch(err){if(active)setError(messageOf(err));}
      finally{if(active)setLoading(false);}
    };
    void load();
    return ()=>{active=false;};
  },[claimId,root,token]);

  const lot=useMemo(()=>lots.find(x=>x.id===verification?.lot_id),[lots,verification?.lot_id]);
  const product=useMemo(()=>products.find(x=>x.id===lot?.product_id),[products,lot?.product_id]);
  const supplier=useMemo(()=>suppliers.find(x=>x.id===lot?.supplier_id),[suppliers,lot?.supplier_id]);
  const canApprove=!!claim&&!!verification&&claim.status==='draft'&&verification.status==='approved'
    &&claim.submitted_by_user_id!==viewerId&&(role==='owner'||role==='admin');
  const audit=useMemo(()=>claim?.events.slice().sort((a,b)=>new Date(a.created_at).valueOf()-new Date(b.created_at).valueOf())??[],[claim?.events]);
  if(!claimId)return null;
  return <div className="claim-detail-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}>
    <section className="claim-detail-sheet" role="dialog" aria-modal="true" aria-label="Supplier claim details">
      <header className="claim-detail-header">
        <div><span className="claim-detail-eyebrow"><FileCheck2 size={15}/> BATCHTRACE / RETURN CLAIM</span>
          <h2>Review supplier claim</h2>
          <p>Read the requested return, its original physical-check record and internal approval history.</p>
        </div>
        <button type="button" className="claim-detail-close" aria-label="Close claim details" onClick={onClose}><X size={21}/></button>
      </header>
      <div className="claim-detail-body">
        {loading&&<p role="status">Loading claim details from your workspace…</p>}
        {error&&<div role="alert" className="claim-detail-warning"><AlertTriangle size={18}/> Could not load claim details: {error}</div>}
        {claim&&verification&&!error&&<>
          <div className="claim-detail-banner"><ShieldCheck size={18}/><span><strong>Internal claim only.</strong> Creating or approving this claim does not dispatch goods, confirm supplier acceptance or record money received.</span></div>
          <div className="claim-detail-heading"><div><small>Claim reference</small><strong title={claim.id}>{claim.id}</strong></div><span className={`claim-detail-status claim-detail-${claim.status}`}>{pretty(claim.status)}</span></div>
          <div className="claim-detail-stats">
            <div><small>Requested units</small><strong>{claim.quantity}</strong></div>
            <div><small>Physical check</small><strong>{verification.counted_quantity}</strong></div>
            <div><small>Supplier accepted</small><strong>{claim.accepted_quantity}</strong></div>
            <div><small>Supplier rejected</small><strong>{claim.rejected_quantity}</strong></div>
          </div>
          <div className="claim-detail-title"><ClipboardCheck size={18}/> Claim and batch context</div>
          <div className="claim-detail-grid">
            <div><small>Product</small><strong>{product?`${product.sku} · ${product.name}`:lot?`Product ID ${short(lot.product_id)} (not loaded)`:'Product not loaded'}</strong></div>
            <div><small>Supplier</small><strong>{supplier?`${supplier.code} · ${supplier.name}`:lot?`Supplier ID ${short(lot.supplier_id)} (not loaded)`:'Supplier not loaded'}</strong></div>
            <div><small>Batch number</small><strong>{lot?.batch_number??`Batch ID ${short(verification.lot_id)}`}</strong></div>
            <div><small>Expiry date</small><strong>{lot?.expiry_date?stamp(lot.expiry_date):'Batch not loaded'}</strong></div>
            <div><small>Claim created</small><strong>{stamp(claim.created_at)}</strong></div>
            <div><small>Submitted by</small><strong title={claim.submitted_by_user_id}>{claim.submitted_by_user_id===viewerId?'You':short(claim.submitted_by_user_id)}</strong></div>
          </div>
          <div className="claim-detail-note"><small>Creator's claim reason / request</small><p>{claim.note}</p></div>
          <div className="claim-detail-title"><FileSpreadsheet size={18}/> Source verification</div>
          <div className="claim-detail-source">
            <div><strong>Physical count: {verification.counted_quantity} units</strong><small>CSV observed: {verification.observed_quantity} units · Verification: {pretty(verification.status)}</small><small>Verification note: {verification.note}</small></div>
            <button className="secondary-btn small" type="button" onClick={()=>onShowVerification(verification.id)}>Open source evidence <ArrowRight size={15}/></button>
          </div>
          <div className="claim-detail-title"><Clock3 size={18}/> Audit history</div>
          {audit.length===0?<p className="claim-detail-muted">No claim event records returned.</p>:<ol className="claim-detail-events">{audit.map(evt=><li key={evt.id}><div className="claim-detail-event-top"><strong>{pretty(evt.event_type)}</strong><span>{stamp(evt.created_at)}</span></div><small title={evt.actor_user_id}>Action by {evt.actor_user_id===viewerId?'you':short(evt.actor_user_id)}</small><p>{evt.note}</p></li>)}</ol>}
          {claim.status==='draft'&&claim.submitted_by_user_id===viewerId&&<div className="claim-detail-warning"><AlertTriangle size={17}/> Your claim requires approval by a different owner/admin. Self-approval is not permitted.</div>}
          {canApprove&&<label className="claim-detail-confirm"><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/><span>I reviewed this claim, the quantity and the recorded verification. I understand these records alone do not prove the goods have been sent to the supplier.</span></label>}
        </>}
      </div>
      <footer className="claim-detail-footer">
        <button type="button" className="secondary-btn" onClick={onClose}>Close</button>
        {canApprove&&<button type="button" className="primary-btn" disabled={!reviewed} onClick={()=>{onApprove(claim.id);onClose();}}>Continue to approval <ArrowRight size={16}/></button>}
      </footer>
    </section>
  </div>;
}
