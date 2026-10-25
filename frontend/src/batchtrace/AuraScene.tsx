import type {CSSProperties} from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

/**
 * BatchTrace Harvest illustration — an intentionally editorial, process-oriented
 * motion scene. No live counts and no external assets / network calls.
 * All motion derives from Remotion frames so it also renders deterministically.
 */
const absolute: CSSProperties = {position: 'absolute', inset: 0};

export function AuraScene() {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const intro = interpolate(frame, [0, Math.round(fps * 0.8)], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const bob = Math.sin((time / 12) * Math.PI * 2) * 11;
  const ticket = Math.sin((time / 12) * Math.PI * 2 + 0.9) * 7;
  const pulse = 0.5 + 0.5 * Math.sin((time / 12) * Math.PI * 4);
  const line = interpolate(frame % (fps * 12), [0, fps * 9, fps * 12], [0, 1, 1]);

  return (
    <div style={{...absolute, opacity: intro, overflow: 'hidden', fontFamily: 'system-ui, Arial, sans-serif'}}>
      <svg viewBox="0 0 1000 760" width="100%" height="100%" style={absolute} role="img" aria-label="Animated inventory recovery workflow illustration">
        <defs>
          <filter id="paperShadow" x="-70%" y="-80%" width="240%" height="270%">
            <feDropShadow dx="0" dy="19" stdDeviation="17" floodColor="#304331" floodOpacity=".14"/>
          </filter>
          <pattern id="deskDots" width="28" height="28" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1.5" fill="#234b3a" opacity=".16"/>
          </pattern>
        </defs>
        <circle cx="526" cy="348" r="308" fill="#fff8e8" opacity=".40" />
        <circle cx="526" cy="348" r="303" fill="none" stroke="#2c5948" strokeWidth="1.5" strokeDasharray="5 12" opacity=".24" />
        <circle cx="526" cy="348" r="258" fill="url(#deskDots)" opacity=".76" />
        <path d="M126 507 C254 655 691 650 858 463" fill="none" stroke="#cf996d" strokeWidth="2" strokeDasharray="7 11" opacity=".52"/>
        {/* Warm editorial paper layer */}
        <g transform={`translate(390 ${152 + bob}) rotate(-9 140 235)`} filter="url(#paperShadow)">
          <rect width="315" height="420" rx="24" fill="#fffdf8" stroke="#d5cfbe" strokeWidth="2"/>
          <rect x="28" y="29" width="120" height="12" rx="6" fill="#c4d6c8"/>
          <rect x="28" y="53" width="222" height="8" rx="4" fill="#e7e7dc"/>
          <rect x="28" y="86" width="259" height="1.5" fill="#e9e7df"/>
          <rect x="28" y="109" width="66" height="66" rx="14" fill="#e7efe3"/>
          <path d="M42 144 L60 152 L79 127" fill="none" stroke="#27856d" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round"/>
          <text x="112" y="129" fill="#264537" fontSize="16" fontWeight="700">Batch recorded</text>
          <text x="112" y="153" fill="#8a998e" fontSize="13">Source confirmed</text>
          <rect x="28" y="195" width="259" height="1.5" fill="#e9e7df"/>
          <text x="28" y="229" fill="#84958b" fontSize="13" fontWeight="700" letterSpacing="2">RECOVERY STEPS</text>
          {['Observe stock','Check return window','Review & reconcile'].map((label,i) => (
            <g key={label} transform={`translate(28 ${260 + i * 44})`}>
              <circle cx="11" cy="0" r="11" fill={i === 2 ? '#f2bb84' : '#d8eadd'}/>
              <path d="M6 0 L10 4 L16 -4" fill="none" stroke="#326a54" strokeWidth="2.7" strokeLinecap="round"/>
              <text x="33" y="5" fontSize="15" fill="#344d40" fontWeight="600">{label}</text>
            </g>
          ))}
        </g>
        {/* Real-world parcel rather than robot / orbit icon */}
        <g transform={`translate(206 ${306 - bob * .35}) rotate(-11 120 140)`} filter="url(#paperShadow)">
          <path d="M33 106 L142 47 L242 105 L133 163 Z" fill="#e5ad79" stroke="#9e6947" strokeWidth="2"/>
          <path d="M33 106 L133 163 L133 286 L33 226 Z" fill="#c88151" stroke="#9e6947" strokeWidth="2"/>
          <path d="M133 163 L242 105 L242 226 L133 286 Z" fill="#edb686" stroke="#9e6947" strokeWidth="2"/>
          <path d="M92 74 L193 132 L193 257 L158 277 L158 150 L58 94" fill="#f6d8a9" opacity=".93"/>
          <path d="M91 74 L191 132" fill="none" stroke="#a96e49" strokeWidth="2"/>
          <rect x="158" y="180" width="65" height="40" rx="5" fill="#fff8e9" stroke="#d7b68b"/>
          <path d="M171 191 H209 M171 198 H201 M171 206 H211" stroke="#b2bcb2" strokeWidth="3" strokeLinecap="round"/>
        </g>
        {/* Detached note gently reacts over the cycle */}
        <g transform={`translate(676 ${168 + ticket}) rotate(8 95 62)`} filter="url(#paperShadow)">
          <rect width="191" height="119" rx="19" fill="#254f3f"/>
          <circle cx="29" cy="33" r="12" fill="#d3eeb5"/>
          <path d="M23 33 L28 38 L36 27" stroke="#24503b" fill="none" strokeWidth="3" strokeLinecap="round"/>
          <text x="49" y="38" fill="#f8f5ec" fontWeight="700" fontSize="15">Ready to review</text>
          <rect x="23" y="65" width="141" height="7" rx="4" fill="#658273"/>
          <rect x="23" y="65" width={141 * Math.max(.25, line)} height="7" rx="4" fill="#d6efa9"/>
          <text x="23" y="94" fill="#d9e8db" fontSize="12">Clear, traceable actions</text>
        </g>
        <g transform={`translate(716 ${525 + bob * .25}) rotate(-3 95 45)`} filter="url(#paperShadow)">
          <rect width="193" height="88" rx="18" fill="#fff8eb" stroke="#e3bd9c"/>
          <circle cx="30" cy="43" r={11 + pulse * 3} fill="#eeab73" opacity=".55"/>
          <circle cx="30" cy="43" r="7" fill="#a86137"/>
          <text x="51" y="39" fill="#504132" fontSize="14" fontWeight="700">Less waste</text>
          <text x="51" y="59" fill="#8e7d6d" fontSize="12">More value recovered</text>
        </g>
      </svg>
    </div>
  );
}
