import {useCallback, useEffect, useState, type FormEvent} from 'react';
import {CheckCircle2, CircleAlert, UserPlus, Users, Trash2, RefreshCw} from 'lucide-react';
import {api, json, messageOf} from './api';

type Role='owner'|'admin'|'staff'|'viewer';
type Member={membership_id:string; user_id:string; email:string; role:Role; joined_at:string};

export function TeamPanel({root,token,myRole,myId}:{root:string;token:string;myRole:string;myId:string}) {
  const [members,setMembers]=useState<Member[]>([]);
  const [email,setEmail]=useState('');
  const [role,setRole]=useState<'admin'|'staff'|'viewer'>('staff');
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const manager=myRole==='owner'||myRole==='admin';

  const load=useCallback(async()=>{
    setLoading(true);
    try{setMembers(await api<Member[]>(`${root}/team`,token));setError('');}
    catch(e){setError(messageOf(e));}
    finally{setLoading(false);}
  },[root,token]);
  useEffect(()=>{void load();},[load]);
  async function add(e:FormEvent){
    e.preventDefault();setBusy(true);setError('');setNotice('');
    try{
      await api(`${root}/team`,token,json({email:email.trim().toLowerCase(),role}));
      setEmail('');setNotice('Member added. They can sign in and select this workspace.');await load();
    }catch(e){setError(messageOf(e));}finally{setBusy(false);}
  }
  async function change(member:Member,next:'admin'|'staff'|'viewer'){
    setBusy(true);setError('');setNotice('');
    try{await api(`${root}/team/${member.membership_id}`,token,{method:'PATCH',body:JSON.stringify({role:next})});setNotice('Member role updated.');await load();}
    catch(e){setError(messageOf(e));}finally{setBusy(false);}
  }
  async function remove(member:Member){
    if(!window.confirm(`Remove ${member.email} from this workspace? This does not delete their account.`))return;
    setBusy(true);setError('');setNotice('');
    try{await api(`${root}/team/${member.membership_id}`,token,{method:'DELETE'});setNotice('Membership removed.');await load();}
    catch(e){setError(messageOf(e));}finally{setBusy(false);}
  }
  return <div className="team-panel">
    <div className="team-head"><div><h3><Users size={21}/> Workspace members</h3><p>People who can access this organization. A separate owner or admin can review submitted physical checks.</p></div><button className="secondary-btn small" type="button" onClick={()=>void load()} disabled={busy||loading}><RefreshCw size={15}/> Refresh</button></div>
    {error&&<div className="team-alert team-alert-error" role="alert"><CircleAlert size={17}/>{error}</div>}
    {notice&&<div className="team-alert team-alert-good" role="status"><CheckCircle2 size={17}/>{notice}</div>}
    {manager&&<form onSubmit={add} className="team-add">
      <label>Existing registered user's email<input required type="email" autoComplete="off" placeholder="reviewer@company.com" value={email} onChange={e=>setEmail(e.target.value)}/></label>
      <label>Role<select value={role} onChange={e=>setRole(e.target.value as 'admin'|'staff'|'viewer')}>
        {myRole==='owner'&&<option value="admin">Admin — can review</option>}
        <option value="staff">Staff — can submit</option>
        <option value="viewer">Viewer — read only</option>
      </select></label>
      <button className="primary-btn" disabled={busy} type="submit"><UserPlus size={17}/> Add member</button>
      <p className="team-hint">No external email is sent. The person must already have their own BatchTrace account. Membership takes effect immediately—add trusted users only.</p>
    </form>}
    <div className="team-members">
      {loading?<p>Loading workspace members…</p>:members.length===0?<p>No team members found.</p>:members.map(member=>{
        const self=member.user_id===myId;
        const canEdit=manager&&!self&&member.role!=='owner'&&(myRole==='owner'||(myRole==='admin'&&['staff','viewer'].includes(member.role)));
        return <div className="team-member" key={member.membership_id}>
          <span className="team-avatar">{member.email.slice(0,1).toUpperCase()}</span>
          <div className="team-identity"><strong>{member.email} {self&&<small>(you)</small>}</strong><span>Joined {new Date(member.joined_at).toLocaleDateString()}</span></div>
          {canEdit?<div className="team-controls"><select disabled={busy} aria-label={`Role for ${member.email}`} value={member.role} onChange={e=>void change(member,e.target.value as 'admin'|'staff'|'viewer')}>
            {myRole==='owner'&&<option value="admin">Admin</option>}
            <option value="staff">Staff</option><option value="viewer">Viewer</option>
          </select><button type="button" className="team-remove" disabled={busy} onClick={()=>void remove(member)} aria-label={`Remove ${member.email}`}><Trash2 size={16}/></button></div>:<span className="team-role">{member.role}</span>}
        </div>;
      })}
    </div>
    <p className="team-footnote">Owner/Admin: review submitted checks · Staff: prepare counts and claims · Viewer: read-only. Members never receive access to other organizations automatically.</p>
  </div>;
}
