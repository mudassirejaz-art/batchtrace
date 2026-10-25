import { useEffect, useState } from 'react';
import { Player } from '@remotion/player';
import {
  ArrowRight, ArrowUpRight, Boxes, CheckCircle2, ClipboardCheck,
  FileSpreadsheet, Layers3, LockKeyhole, PackageCheck, ShieldCheck,
  Sparkles, TrendingUp, Truck, Wallet,
} from 'lucide-react';
import { WorkflowMotion } from './WorkflowMotion';
import './landing.css';

const WORKSPACE_URL = '/app';

const cards = [
  {
    icon: FileSpreadsheet,
    step: '01 / OBSERVE',
    heading: 'Start with an inventory snapshot',
    body: 'Import your CSV, preserve when stock was observed, and trace each batch back to its source.',
  },
  {
    icon: ClipboardCheck,
    step: '02 / VERIFY',
    heading: 'Put evidence before action',
    body: 'Review expiry windows, confirm physical quantities, and require independent approval.',
  },
  {
    icon: Wallet,
    step: '03 / RECONCILE',
    heading: 'Follow the credit trail',
    body: 'Track supplier-return outcomes, recorded credit evidence, and the remaining balance.',
  },
];

const flow = [
  { icon: Boxes, title: 'Capture', text: 'Historical CSV snapshots' },
  { icon: TrendingUp, title: 'Surface', text: 'Expiry and return signals' },
  { icon: ShieldCheck, title: 'Approve', text: 'Two-person review' },
  { icon: Truck, title: 'Return', text: 'Supplier claim workflow' },
  { icon: PackageCheck, title: 'Reconcile', text: 'Internal credit records' },
];

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener?.('change', update);
    return () => query.removeEventListener?.('change', update);
  }, []);
  return reduced;
}

export function Landing() {
  const reducedMotion = useReducedMotion();
  return (
    <div className="bt-landing" id="top">
      <a className="bt-skip" href="#main">Skip to content</a>
      <div className="bt-ambient bt-ambient-one" aria-hidden="true" />
      <div className="bt-ambient bt-ambient-two" aria-hidden="true" />
      <header className="bt-header">
        <a className="bt-logo" href="/" aria-label="BatchTrace home">
          <span className="bt-logo-mark"><Layers3 size={22} strokeWidth={2.35} /></span>
          <span>Batch<span className="bt-logo-em">Trace</span><span className="bt-logo-period">.</span></span>
        </a>
        <nav className="bt-nav" aria-label="Main navigation">
          <a href="#why">Why BatchTrace</a>
          <a href="#workflow">How it works</a>
          <a href="#controls">Built for trust</a>
        </nav>
        <a className="bt-nav-cta" href={WORKSPACE_URL}>Open workspace <ArrowUpRight size={16} /></a>
      </header>

      <main id="main">
        <section className="bt-hero bt-wrap" aria-labelledby="bt-hero-title">
          <div className="bt-hero-copy">
            <span className="bt-kicker"><span className="bt-kicker-dot" /> INVENTORY RECOVERY, WITH EVIDENCE</span>
            <h1 id="bt-hero-title">Find the value <em>hiding</em> in your batches.</h1>
            <p className="bt-lede">From ageing stock to supplier returns and credit follow-up, BatchTrace gives your team one clear, accountable workflow.</p>
            <div className="bt-hero-actions">
              <a className="bt-btn bt-btn-primary" href={WORKSPACE_URL}>Get into BatchTrace <ArrowRight size={19} /></a>
              <a className="bt-btn bt-btn-link" href="#workflow">Explore the workflow <ArrowUpRight size={18} /></a>
            </div>
            <div className="bt-proof"><span className="bt-proof-icons"><CheckCircle2 size={17} /><ShieldCheck size={17} /></span> Historical evidence. Independent reviews. Clear reconciliation.</div>
          </div>
          <div className="bt-hero-media" aria-label="Illustrated example of the BatchTrace workflow">
            <div className="bt-media-toolbar"><span><i /> <i /> <i /></span><strong>Workflow overview</strong><span className="bt-media-demo">PRODUCT ILLUSTRATION</span></div>
            <div className="bt-player-shell">
              <Player
                component={WorkflowMotion}
                durationInFrames={180}
                compositionWidth={960}
                compositionHeight={610}
                fps={30}
                autoPlay={!reducedMotion}
                loop={!reducedMotion}
                initiallyMuted
                clickToPlay={false}
                controls={false}
                style={{ width: '100%', aspectRatio: '960 / 610' }}
              />
            </div>
            <div className="bt-media-bottom"><span><span className="bt-live-dot" /> Evidence-led workflow</span><span>Illustrative, not live customer data</span></div>
          </div>
        </section>

        <section className="bt-insight" id="why">
          <div className="bt-wrap bt-insight-inner">
            <span className="bt-insight-symbol"><Sparkles size={21}/></span>
            <p>Expired opportunities rarely announce themselves. <strong>BatchTrace helps your team spot, verify, and follow through.</strong></p>
            <span className="bt-insight-label">BEFORE VALUE SLIPS AWAY</span>
          </div>
        </section>

        <section className="bt-section bt-wrap" aria-labelledby="bt-benefits-title">
          <div className="bt-section-heading">
            <span className="bt-section-overline">ONE CONNECTED PROCESS</span>
            <h2 id="bt-benefits-title">Less guesswork.<br /><span>More accountability.</span></h2>
            <p>Designed for the moments between discovering a stock problem and closing the loop with a supplier.</p>
          </div>
          <div className="bt-card-grid">
            {cards.map(({ icon: Icon, step, heading, body }) => (
              <article className="bt-feature" key={step}>
                <div className="bt-feature-top"><span className="bt-feature-icon"><Icon size={25} strokeWidth={1.8}/></span><span>{step}</span></div>
                <h3>{heading}</h3><p>{body}</p>
                <div className="bt-feature-bottom"><span>Traceable by design</span><ArrowUpRight size={18}/></div>
              </article>
            ))}
          </div>
        </section>

        <section className="bt-process" id="workflow" aria-labelledby="bt-process-title">
          <div className="bt-wrap">
            <div className="bt-process-heading"><div><span className="bt-section-overline">FROM SNAPSHOT TO OUTCOME</span><h2 id="bt-process-title">Five steps. One shared picture.</h2></div><p>Keep context as work moves from the stockroom to approvals and supplier follow-up.</p></div>
            <div className="bt-flow">
              {flow.map(({icon: Icon, title, text}, i) => (
                <div className="bt-flow-step" key={title}>
                  <div className="bt-flow-badge">{String(i + 1).padStart(2, '0')}</div>
                  <span className="bt-flow-icon"><Icon size={24}/></span>
                  <h3>{title}</h3><p>{text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="bt-trust bt-wrap" id="controls" aria-labelledby="bt-trust-title">
          <div className="bt-trust-copy"><span className="bt-section-overline">BUILT FOR RESPONSIBLE TEAMS</span><h2 id="bt-trust-title">The right people.<br/><em>The right decisions.</em></h2><p>Separate workspaces, role-based access, independent reviews, and preserved evidence make important decisions easier to trace.</p><a className="bt-btn bt-btn-light" href={WORKSPACE_URL}>Open your workspace <ArrowRight size={18}/></a></div>
          <div className="bt-trust-grid">
            <div><LockKeyhole size={25}/><strong>Workspace isolation</strong><span>Keep each team's records in their own authorized workspace.</span></div>
            <div><ShieldCheck size={25}/><strong>Independent review</strong><span>Approval steps with distinct reviewer permissions.</span></div>
            <div><Layers3 size={25}/><strong>Preserved history</strong><span>Understand which observation and policy supported a decision.</span></div>
            <div><Wallet size={25}/><strong>Honest reconciliation</strong><span>Internal credit evidence is not represented as a verified bank payment.</span></div>
          </div>
        </section>

        <section className="bt-final-cta bt-wrap" aria-labelledby="bt-final-title">
          <div className="bt-final-icon"><Boxes size={27}/></div>
          <div><span className="bt-section-overline">FROM REACTIVE TO READY</span><h2 id="bt-final-title">Know which batches need action.</h2><p>Bring evidence, approvals, claims, and credit follow-up into one place.</p></div>
          <a className="bt-btn bt-btn-primary" href={WORKSPACE_URL}>Enter BatchTrace <ArrowRight size={19}/></a>
        </section>
      </main>
      <footer className="bt-footer"><div className="bt-wrap"><a className="bt-logo bt-logo-footer" href="/"><span className="bt-logo-mark"><Layers3 size={18}/></span><span>BatchTrace<span className="bt-logo-period">.</span></span></a><span>Thoughtful inventory recovery, from evidence to outcome.</span><a href="#top">Back to top ↑</a></div></footer>
    </div>
  );
}
