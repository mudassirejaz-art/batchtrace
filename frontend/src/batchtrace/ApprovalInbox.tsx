import {useEffect, useState} from 'react';
import {ArrowRight, BellRing, ClipboardCheck, FileCheck2, ShieldCheck, Users} from 'lucide-react';
import {api} from './api';
import type {Claim, Lot, Product, Supplier, Verification} from './types';
import './step27-approval-inbox.css';

type Member={user_id:string;email:string};
type Props={
  root:string;
  token:string;
  viewerId:string;
  claims:Claim[];
  verifications:Verification[];
  lots:Lot[];
  products:Product[];
  suppliers:Supplier[];
  onClaim:(id:string)=>void;
  onVerification:(id:string)=>void;
};

const short=(value:string)=>value.slice(0,8)+'…';
function formatDate(value:string){
  const parsed=new Date(value);
  return Number.isNaN(parsed.getTime())?value:parsed.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
}
export function ApprovalInbox({root,token,viewerId,claims,verifications,lots,products,suppliers,onClaim,onVerification}:Props){
  const [people,setPeople]=useState<Record<string,string>>({});
  useEffect(()=>{
    let active=true;
    // Only owner/admin render this component; the server authorizes the team directory.
    void api<Member[]>(`${root}/team`,token).then(rows=>{
      if(active)setPeople(Object.fromEntries(rows.map(row=>[row.user_id,row.email])));
    }).catch(()=>{/* Keep the queue useful even when member names cannot be loaded. */});
    return()=>{active=false;};
  },[root,token]);

  const checks=verifications.filter(item=>item.status==='pending'&&item.submitted_by_user_id!==viewerId);
  const drafts=claims.filter(item=>item.status==='draft'&&item.submitted_by_user_id!==viewerId);
  const total=checks.length+drafts.length;
  const actor=(id:string)=>people[id]??`Team member ${short(id)}`;
  const context=(verificationId:string)=>{
    const verification=verifications.find(item=>item.id===verificationId);
    const lot=lots.find(item=>item.id===verification?.lot_id);
    const product=products.find(item=>item.id===lot?.product_id);
    const supplier=suppliers.find(item=>item.id===lot?.supplier_id);
    return {product:product?.sku??'Product details',batch:lot?.batch_number??'Batch details',supplier:supplier?.name??'Supplier details'};
  };

  return <section className="approval-inbox-panel" aria-label="Approval inbox">
    <div className="approval-inbox-heading">
      <div className="approval-inbox-heading-icon"><BellRing size={21}/></div>
      <div><h2>Waiting for your review</h2><p>Requests from other members of this workspace. New requests appear through auto-sync.</p></div>
      <span className="approval-inbox-count" aria-label={`${total} requests awaiting your review`}>{total} pending</span>
    </div>
    {total===0?<div className="approval-inbox-empty"><ClipboardCheck size={24}/><strong>You're all caught up</strong><span>No requests from other members need your decision right now.</span></div>:<div className="approval-inbox-items">
      {drafts.map(claim=>{
        const record=context(claim.verification_id);
        return <article className="approval-inbox-item" key={`claim-${claim.id}`}>
          <div className="approval-inbox-kind"><FileCheck2 size={17}/> Supplier claim <span>Draft · Needs internal approval</span></div>
          <div className="approval-inbox-item-body"><div>
            <strong>{claim.quantity} units · {record.batch}</strong>
            <p>{record.product} · {record.supplier}</p>
            <div className="approval-inbox-person"><Users size={14}/> Submitted by <b>{actor(claim.submitted_by_user_id)}</b> · {formatDate(claim.created_at)}</div>
            <blockquote>{claim.note}</blockquote>
          </div><button type="button" className="approval-inbox-review" onClick={()=>onClaim(claim.id)}>Read claim & evidence <ArrowRight size={16}/></button></div>
        </article>;
      })}
      {checks.map(check=>{
        const lot=lots.find(item=>item.id===check.lot_id);
        const product=products.find(item=>item.id===lot?.product_id);
        return <article className="approval-inbox-item" key={`check-${check.id}`}>
          <div className="approval-inbox-kind"><ShieldCheck size={17}/> Physical verification <span>Pending independent review</span></div>
          <div className="approval-inbox-item-body"><div>
            <strong>{check.counted_quantity} units · {lot?.batch_number??short(check.lot_id)}</strong>
            <p>{product?.sku??'Product details'} · CSV observed {check.observed_quantity} units</p>
            <div className="approval-inbox-person"><Users size={14}/> Submitted by <b>{actor(check.submitted_by_user_id)}</b> · {formatDate(check.created_at)}</div>
            <blockquote>{check.note}</blockquote>
          </div><button type="button" className="approval-inbox-review" onClick={()=>onVerification(check.id)}>Read source evidence <ArrowRight size={16}/></button></div>
        </article>;
      })}
    </div>}
    <p className="approval-inbox-footnote">Reviewing does not create a second claim, dispatch goods, or confirm payment. Your decision note is preserved in the existing audit history. You cannot approve your own submission.</p>
  </section>;
}
