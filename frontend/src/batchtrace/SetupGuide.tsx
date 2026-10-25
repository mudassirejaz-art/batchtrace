import { ArrowRight, Check, ClipboardList, FileDown, PackageCheck } from 'lucide-react';

type SetupSection = 'suppliers' | 'products' | 'lots' | 'policies' | 'imports' | 'opportunities';
type Props = {
  suppliers: number;
  products: number;
  lots: number;
  policies: number;
  imports: number;
  onNavigate: (section: SetupSection) => void;
  onDownloadTemplate: () => void;
};

/** A guide derived from real, currently loaded API records. No fabricated counts. */
export function SetupGuide({ suppliers, products, lots, policies, imports, onNavigate, onDownloadTemplate }: Props) {
  const steps = [
    { key: 'suppliers', title: 'Add a supplier', hint: 'Who accepts your product returns?', complete: suppliers > 0 },
    { key: 'products', title: 'Register products', hint: 'Create SKUs for each product.', complete: products > 0 },
    { key: 'lots', title: 'Add a batch', hint: 'Connect product, supplier and expiry date.', complete: lots > 0 },
    { key: 'policies', title: 'Set a return policy', hint: 'Define the supplier return window.', complete: policies > 0 },
    { key: 'imports', title: 'Import a stock observation', hint: 'Preview the CSV before committing.', complete: imports > 0 },
  ] as const;
  const complete = steps.filter(s => s.complete).length;
  if (complete === steps.length) return null;
  const next = steps.find(s => !s.complete)!;
  return (
    <section className="onboard-panel" aria-labelledby="onboard-title">
      <div className="onboard-header">
        <div className="onboard-heading">
          <span className="onboard-kicker"><ClipboardList size={15} /> YOUR FIRST RECOVERY WORKFLOW</span>
          <h3 id="onboard-title">Start with the essentials</h3>
          <p>Just a few real records are needed before BatchTrace can find return opportunities.</p>
        </div>
        <div className="onboard-progress" aria-label={`${complete} of 5 setup steps completed`}>
          <strong>{complete}<span> / 5</span></strong>
          <div className="onboard-progress-track"><div style={{width:`${complete * 20}%`}} /></div>
          <small>Steps completed</small>
        </div>
      </div>
      <div className="onboard-steps">
        {steps.map((step, index) => (
          <button
            key={step.key}
            type="button"
            onClick={() => onNavigate(step.key)}
            className={`onboard-step ${step.complete ? 'is-complete' : ''} ${step.key === next.key ? 'is-next' : ''}`}
            aria-label={`${step.title}, ${step.complete ? 'complete' : 'not yet complete'}`}
          >
            <span className="onboard-step-number">{step.complete ? <Check size={15} strokeWidth={2.6}/> : String(index + 1).padStart(2,'0')}</span>
            <span className="onboard-step-content"><strong>{step.title}</strong><small>{step.hint}</small></span>
            <ArrowRight size={17} className="onboard-step-arrow"/>
          </button>
        ))}
      </div>
      <div className="onboard-footer">
        <div><PackageCheck size={19}/><span>After these steps, view real recovery signals—not guessed stock values.</span></div>
        <div className="onboard-footer-actions">
          <button type="button" className="onboard-download" onClick={onDownloadTemplate}><FileDown size={16}/> CSV starter</button>
          <button type="button" className="onboard-primary" onClick={() => onNavigate(next.key)}>Next step <ArrowRight size={16}/></button>
        </div>
      </div>
    </section>
  );
}
