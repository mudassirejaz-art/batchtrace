import {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, CheckCircle2, Download, FileSpreadsheet, SearchCheck, ShieldCheck, X} from 'lucide-react';
import {api, messageOf} from './api';
import type {Lot, Policy, Product, Supplier, Verification} from './types';
import './step24-evidence.css';

type ImportDetail = {
  id:string; filename:string; observed_on:string; created_at:string;
  row_count:number; content_sha256:string; organization_id:string;
  rows:Array<{lot_id:string;observed_quantity:number}>;
};
type FullVerification = Verification & {organization_id:string;snapshot_row_id:string;policy_id:string};
export type EvidenceSelection = {kind:'import'|'verification';id:string};

type Props = {
  selection:EvidenceSelection|null; root:string; token:string|null;
  lots:Lot[];products:Product[];suppliers:Supplier[];policies:Policy[];
  viewerId:string;role:string;
  onClose:()=>void;onReview:(id:string)=>void;
};
function displayDate(raw?:string){
  if(!raw)return '—';
  const date=new Date(raw.includes('T')?raw:`${raw}T12:00:00`);
  return isNaN(+date)?raw:date.toLocaleDateString('en-US',{year:'numeric',month:'short',day:'numeric'});
}
function shortId(id?:string){return id?`${id.slice(0,8)}…`:'—';}
function escapeCsv(value:string|number){return '"'+String(value).replaceAll('"','""')+'"';}

export function EvidencePanel({selection,root,token,lots,products,suppliers,policies,viewerId,role,onClose,onReview}:Props){
  const [record,setRecord]=useState<ImportDetail|null>(null);
  const [verification,setVerification]=useState<FullVerification|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [acknowledged,setAcknowledged]=useState(false);
  useEffect(()=>{
    if(!selection||!root||!token)return;
    let active=true;
    const work=async()=>{
      try{
        const check=selection.kind==='verification'
          ? await api<FullVerification>(`${root}/recovery/verifications/${selection.id}`,token):null;
        const importId=check?.import_id??selection.id;
        const incoming=await api<ImportDetail>(`${root}/imports/${importId}`,token);
        if(!active)return;
        // Avoid displaying stale data after switching workspaces.
        if(check&&check.organization_id!==incoming.organization_id)throw new Error('Evidence organization mismatch');
        setVerification(check);setRecord(incoming);
      }catch(err){if(active)setError(messageOf(err));}
      finally{if(active)setLoading(false);}
    };
    void work();
    return ()=>{active=false;};
  },[selection,root,token]);

  const decorated=useMemo(()=>record?.rows.map(row=>{
    const lot=lots.find(x=>x.id===row.lot_id);
    const product=products.find(x=>x.id===lot?.product_id);
    const supplier=suppliers.find(x=>x.id===lot?.supplier_id);
    return {row,lot,product,supplier};
  })??[],[record,lots,products,suppliers]);
  const matched=verification ? decorated.filter(x=>x.row.lot_id===verification.lot_id):[];
  const matchedRow=matched.length===1?matched[0]:null;
  const consistent=!!verification && matched.length===1 && matchedRow?.row.observed_quantity===verification.observed_quantity;
  const currentPolicy=policies.find(p=>p.id===verification?.policy_id);
  const allResolved=decorated.length>0 && decorated.every(x=>x.lot&&x.product&&x.supplier);
  const canReview=selection?.kind==='verification' && verification?.status==='pending' &&
    verification.submitted_by_user_id!==viewerId && (role==='owner'||role==='admin');

  const downloadRecorded=()=>{
    if(!record||!allResolved)return;
    const header='product_sku,supplier_code,batch_number,expiry_date,quantity';
    const lines=decorated.map(x=>[x.product!.sku,x.supplier!.code,x.lot!.batch_number,x.lot!.expiry_date,x.row.observed_quantity].map(escapeCsv).join(','));
    // This export is reconstructed from DB rows. It is NOT the uploaded original file.
    const blob=new Blob([`\ufeff${[header,...lines].join('\r\n')}\r\n`],{type:'text/csv;charset=utf-8'});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;a.download=`batchtrace-recorded-snapshot-${record.id.slice(0,8)}.csv`;
    document.body.appendChild(a);a.click();a.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  if(!selection)return null;
  return <div className="evidence-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}>
    <section className="evidence-sheet" role="dialog" aria-modal="true" aria-label={verification?'Verification evidence':'Imported snapshot details'}>
      <header className="evidence-header">
        <div><span className="evidence-eyebrow"><SearchCheck size={15}/> BATCHTRACE / SOURCE EVIDENCE</span>
          <h2>{selection.kind==='verification'?'Review the recorded evidence':'Recorded inventory snapshot'}</h2>
          <p>Compare what was imported with the physical-count attestation before recording a decision.</p>
        </div>
        <button className="evidence-close" onClick={onClose} aria-label="Close evidence viewer"><X size={21}/></button>
      </header>
      <div className="evidence-body">
        {loading&&<p role="status">Loading evidence from your organization’s database…</p>}
        {error&&<div className="evidence-warning" role="alert"><AlertTriangle size={18}/><span>Cannot load evidence: {error}. Review cannot continue.</span></div>}
        {record&&!error&&<>
          <div className="evidence-warning"><AlertTriangle size={18}/><span><strong>Source limitation:</strong> BatchTrace stores verified CSV rows, their import metadata and a fingerprint. The original uploaded CSV file was not archived. The export below reconstructs recorded rows; it is not the original document.</span></div>
          <div className="evidence-section-title"><FileSpreadsheet size={18}/><h3>CSV import provenance</h3></div>
          <div className="evidence-metadata">
            <div><small>Uploaded filename</small><strong>{record.filename}</strong></div>
            <div><small>Observed on</small><strong>{displayDate(record.observed_on)}</strong></div>
            <div><small>Committed at</small><strong>{displayDate(record.created_at)}</strong></div>
            <div><small>Recorded rows</small><strong>{record.rows.length} / {record.row_count}</strong></div>
          </div>
          <details className="evidence-hash"><summary>Show database fingerprint</summary><code>{record.content_sha256}</code></details>
          <div className="evidence-section-title"><FileSpreadsheet size={18}/><h3>Stored observation rows</h3><button className="evidence-link" disabled={!allResolved} onClick={downloadRecorded}><Download size={16}/> Export recorded rows</button></div>
          {!allResolved&&<div className="evidence-warning"><AlertTriangle size={17}/> Some referenced catalog records are outside the current loaded pages. Export is disabled rather than guessing their values.</div>}
          <div className="evidence-table-wrap"><table className="evidence-table"><thead><tr><th>Batch</th><th>SKU</th><th>Supplier</th><th>Expiry</th><th>Observed</th></tr></thead><tbody>{decorated.map(({row,lot,product,supplier})=><tr key={row.lot_id} className={verification?.lot_id===row.lot_id?'evidence-highlight':''}><td>{lot?.batch_number??shortId(row.lot_id)}</td><td>{product?.sku??'Not loaded'}</td><td>{supplier?.code??'Not loaded'}</td><td>{displayDate(lot?.expiry_date)}</td><td><strong>{row.observed_quantity}</strong></td></tr>)}</tbody></table></div>
          {verification&&<>
            <div className="evidence-section-title"><ShieldCheck size={18}/><h3>Staff physical-check attestation</h3></div>
            <div className="evidence-counts"><div><small>CSV observed</small><strong>{verification.observed_quantity} units</strong></div><div><small>Staff counted</small><strong>{verification.counted_quantity} units</strong></div><div><small>Difference</small><strong>{verification.counted_quantity-verification.observed_quantity} units</strong></div></div>
            <div className="evidence-metadata"><div><small>Submitted by</small><strong title={verification.submitted_by_user_id}>{shortId(verification.submitted_by_user_id)}</strong></div><div><small>Submitted at</small><strong>{displayDate(verification.created_at)}</strong></div><div><small>Status</small><strong>{verification.status}</strong></div><div><small>Supplier policy</small><strong>{currentPolicy?`Version ${currentPolicy.version} · ${currentPolicy.days_before_expiry}d before / ${currentPolicy.days_after_expiry}d after`:`Reference ${shortId(verification.policy_id)} (not loaded)`}</strong></div></div>
            <div className="evidence-note"><small>Staff’s verification note (self-reported)</small><p>{verification.note}</p></div>
            {!consistent&&<div className="evidence-warning" role="alert"><AlertTriangle size={18}/> Source row could not be reconciled to the verification. Approval is unavailable in this screen.</div>}
            {consistent&&<div className="evidence-positive"><CheckCircle2 size={18}/> Recorded import row matches the verification’s source reference. This does <strong>not</strong> independently prove the physical count.</div>}
            {canReview&&consistent&&<label className="evidence-ack"><input type="checkbox" checked={acknowledged} onChange={e=>setAcknowledged(e.target.checked)}/><span>I reviewed the recorded CSV snapshot and staff note. I understand these are internal records, not proof that stock was independently inspected.</span></label>}
          </>}
        </>}
      </div>
      <footer className="evidence-footer"><button className="secondary-btn" onClick={onClose}>Close</button>{canReview&&consistent&&<button className="primary-btn" disabled={!acknowledged} onClick={()=>{onClose();onReview(selection.id);}}>Continue to approve / reject</button>}</footer>
    </section>
  </div>;
}
