/**
 * Remotion-powered illustrative hero preview. It intentionally uses no API or customer data.
 * The production app already depends on remotion and @remotion/player.
 */
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';

const steps = [
  {name: 'CSV snapshot saved', tag: 'SOURCE', glyph: '↧'},
  {name: 'Return window identified', tag: 'SIGNAL', glyph: '◈'},
  {name: 'Independent review', tag: 'REVIEW', glyph: '✓'},
  {name: 'Credit evidence recorded', tag: 'RECORD', glyph: '↗'},
];
const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};

export function WorkflowMotion() {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const active = Math.min(3, Math.floor(frame / (1.5 * fps)));
  return (
    <div style={{width:960,height:610,position:'relative',overflow:'hidden',background:'#f8f8f2',fontFamily:'Inter, Avenir Next, Arial, sans-serif',color:'#253e31'}}>
      <div style={{position:'absolute',top:0,bottom:0,left:0,width:188,background:'#263f34',padding:'28px 20px',color:'#eef4e9'}}>
        <div style={{display:'flex',alignItems:'center',gap:10,fontSize:18,fontWeight:800,letterSpacing:'-.5px'}}><div style={{width:27,height:27,borderRadius:8,background:'#f2c59a',display:'grid',placeItems:'center',fontSize:16,color:'#284d3d'}}>▤</div>BatchTrace</div>
        <div style={{marginTop:72,fontSize:10,fontWeight:800,letterSpacing:2,color:'#b0c5b5'}}>WORKSPACE</div>
        <div style={{marginTop:24,background:'#f6e8cd',color:'#2f503e',borderRadius:12,padding:'13px 14px',fontSize:13,fontWeight:800}}>▥ &nbsp; Overview</div>
        <div style={{marginTop:13,padding:'10px 12px',fontSize:13,color:'#cad9cb'}}>▣ &nbsp; Recovery signals</div>
        <div style={{marginTop:12,padding:'10px 12px',fontSize:13,color:'#cad9cb'}}>◫ &nbsp; Batches</div>
        <div style={{marginTop:12,padding:'10px 12px',fontSize:13,color:'#cad9cb'}}>☷ &nbsp; Claims</div>
        <div style={{position:'absolute',bottom:24,left:22,fontSize:10,color:'#aec6b3',lineHeight:1.8}}>ILLUSTRATIVE VIEW<br/>NO LIVE DATA</div>
      </div>
      <div style={{position:'absolute',left:188,right:0,top:0,bottom:0,padding:'34px 35px'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><span style={{fontSize:11,color:'#a66c43',letterSpacing:1.9,fontWeight:800}}>RECOVERY WORKFLOW</span><h2 style={{fontSize:26,letterSpacing:'-1px',margin:'7px 0 0',fontWeight:800}}>From signal to evidence</h2></div><div style={{fontSize:12,background:'#e5efe5',color:'#33654c',padding:'10px 13px',borderRadius:12,fontWeight:700}}>● &nbsp; In review</div></div>
        <div style={{display:'flex',gap:13,marginTop:31}}>
          {[['SOURCE','Recorded'],['WINDOW','Evaluated'],['APPROVAL','Controlled']].map(([name,value])=><div key={name} style={{flex:1,background:'#fffefa',border:'1px solid #e7e7dd',padding:'18px 17px',borderRadius:14}}><div style={{fontSize:10,color:'#8b9288',letterSpacing:1.7,fontWeight:800}}>{name}</div><div style={{fontSize:19,marginTop:14,fontWeight:800}}>{value}</div></div>)}
        </div>
        <div style={{marginTop:23,background:'#fffefa',border:'1px solid #e5e5dc',borderRadius:20,padding:'20px 24px',position:'relative',boxShadow:'0 10px 24px rgba(38,63,52,.04)'}}>
          <div style={{fontSize:12,fontWeight:800,color:'#3b5845',marginBottom:22}}>Evidence trail <span style={{float:'right',color:'#aa7e5a'}}>SAMPLE</span></div>
          <div style={{position:'absolute',left:41,top:76,bottom:49,width:3,background:'#edf0e6',borderRadius:3}}/>
          <div style={{position:'absolute',left:41,top:76,width:3,height:interpolate(frame,[0,4.8*fps],[0,226],clamp),maxHeight:226,background:'#76a989',borderRadius:3}}/>
          {steps.map((s,i)=>{
            const shown=interpolate(frame,[i*1.1*fps,(i*1.1+.5)*fps],[0,1],{...clamp,easing:Easing.bezier(.2,.8,.2,1)});
            return <div key={s.tag} style={{position:'relative',display:'flex',alignItems:'center',gap:17,height:66,opacity:.35+shown*.65,translate:`${interpolate(frame,[i*1.1*fps,(i*1.1+.5)*fps],[13,0],clamp)}px 0px`}}>
              <span style={{width:34,height:34,borderRadius:11,display:'grid',placeItems:'center',fontSize:18,fontWeight:800,zIndex:1,background:active>=i?'#d8e9d9':'#e9ece5',color:active>=i?'#35684d':'#919e94',border:'3px solid #fffefa'}}>{s.glyph}</span>
              <div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'space-between',borderBottom:'1px solid #f0f0e9',paddingBottom:12}}><span style={{fontSize:15,fontWeight:750}}>{s.name}</span><span style={{color:i===active?'#a06b48':'#89988a',fontSize:10,fontWeight:800,letterSpacing:1.5}}>{s.tag}</span></div>
            </div>
          })}
        </div>
        <div style={{marginTop:17,display:'flex',alignItems:'center',gap:10,padding:'13px 16px',background:'#edf3e9',borderRadius:12,color:'#43775b',fontSize:13,fontWeight:750}}>✓ &nbsp; An auditable workflow, not a payment confirmation</div>
      </div>
    </div>
  );
}
