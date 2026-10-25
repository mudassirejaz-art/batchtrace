import type {Section} from './types';

export type WorkspaceRole = 'owner' | 'admin' | 'staff' | 'viewer';
export function workspaceRole(value?:string):WorkspaceRole {
  return value === 'owner' || value === 'admin' || value === 'staff' ? value : 'viewer';
}
export function canVisit(role:WorkspaceRole, section:Section):boolean {
  if(section==='team'||section==='approvals') return role==='owner'||role==='admin';
  if(section==='credits') return role!=='viewer';
  return true;
}
export function canAct(role:WorkspaceRole, kind:string, action?:string):boolean {
  if(role==='viewer') return false;
  if(kind==='team') return role==='owner'||role==='admin';
  if(kind==='policy'||kind==='terms'||kind==='review-verification'||kind==='review-receipt'||kind==='supplier-response') return role==='owner'||role==='admin';
  if(kind==='note' && (action==='approve'||action==='supplier-response')) return role==='owner'||role==='admin';
  return true;
}
export const roleCopy:Record<WorkspaceRole,{title:string;eyebrow:string;description:string}> = {
  owner: {title:'Owner overview',eyebrow:'WORKSPACE / OWNERSHIP',description:'See the complete recovery picture, review financial evidence, and manage team access.'},
  admin: {title:'Operations overview',eyebrow:'WORKSPACE / ADMIN',description:'Review physical checks, handle supplier decisions, and keep the workflow moving.'},
  staff: {title:'My operations',eyebrow:'WORKSPACE / STAFF',description:'Track batches, upload observations, and submit physical checks for review.'},
  viewer: {title:'Workspace overview',eyebrow:'WORKSPACE / READ ONLY',description:'Follow inventory status and recovery signals without changing records.'},
};
