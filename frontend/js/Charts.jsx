// SVG Chart primitives — Sparkline, TrendChart, BarChart, Donut, RegressionChart
const { useState, useMemo } = React;

function Sparkline({ values, w = 140, h = 36, color = 'var(--primary-500)', fill = true }) {
  if (!values || values.length === 0) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pad = 2;
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((v - min) / range) * (h - 2 * pad);
    return [x, y];
  });
  const path = pts.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(' ');
  const areaPath = `${path} L${pts[pts.length - 1][0]},${h - pad} L${pts[0][0]},${h - pad} Z`;
  const gradId = 'spark-' + Math.random().toString(36).slice(2, 8);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{display:'block'}}>
      <defs>
        <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      {fill && <path d={areaPath} fill={`url(#${gradId})`}/>}
      <path d={path} fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function TrendChart({ data, w = 720, h = 280, color, accentColor }) {
  const padL = 56, padR = 16, padT = 16, padB = 36;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const [hover, setHover] = useState(null);

  const values = data.map(d => d.value);
  const max = Math.max(...values) * 1.08;
  const min = Math.min(...values) * 0.92;
  const range = max - min || 1;

  const xAt = i => padL + (i / (data.length - 1)) * innerW;
  const yAt = v => padT + innerH - ((v - min) / range) * innerH;

  const pts = data.map((d, i) => [xAt(i), yAt(d.value)]);
  const path = pts.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(' ');
  const areaPath = `${path} L${pts[pts.length-1][0]},${padT+innerH} L${pts[0][0]},${padT+innerH} Z`;

  const ticks = 4;
  const yTicks = Array.from({length: ticks+1}, (_, i) => min + (range * i) / ticks);
  const xTickIdx = data.length <= 8 ? data.map((_,i)=>i) : [0, Math.floor(data.length/3), Math.floor(2*data.length/3), data.length-1];
  const gradId = 'trend-' + Math.random().toString(36).slice(2,8);

  function handleMove(e) {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const sx = (e.clientX - rect.left) * (w / rect.width);
    const idx = Math.round(((sx - padL) / innerW) * (data.length - 1));
    if (idx >= 0 && idx < data.length) setHover(idx);
  }

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`}
         onMouseMove={handleMove} onMouseLeave={()=>setHover(null)}
         style={{display:'block', cursor:'crosshair'}}>
      <defs>
        <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      {yTicks.map((v, i) => (
        <g key={i}>
          {i === 0 && <line x1={padL} x2={padL+innerW} y1={yAt(v)} y2={yAt(v)} stroke="var(--border)"/>}
          <text x={padL-8} y={yAt(v)} textAnchor="end" dy="0.32em" fontSize="10" fill="var(--muted)" fontFamily="var(--font-mono)">
            {formatTWD(v)}
          </text>
        </g>
      ))}
      <path d={areaPath} fill={`url(#${gradId})`}/>
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="4" fill={color}/>
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="8" fill={color} opacity="0.18"/>
      {xTickIdx.map(i => (
        <text key={i} x={xAt(i)} y={h-10} textAnchor="middle" fontSize="10" fill="var(--muted)" fontFamily="var(--font-mono)">
          {data[i].label}
        </text>
      ))}
      {hover != null && (
        <g>
          <line x1={pts[hover][0]} x2={pts[hover][0]} y1={padT} y2={padT+innerH} stroke={color} strokeOpacity="0.3" strokeDasharray="3 3"/>
          <circle cx={pts[hover][0]} cy={pts[hover][1]} r="5" fill={accentColor || color}/>
          <g transform={`translate(${Math.min(pts[hover][0]+10, padL+innerW-130)}, ${Math.max(pts[hover][1]-44, padT+4)})`}>
            <rect width="120" height="38" rx="6" fill="var(--surface)" stroke="var(--border)"/>
            <text x="10" y="14" fontSize="10" fill="var(--muted)">{data[hover].label}</text>
            <text x="10" y="30" fontSize="12" fontWeight="700" fill="var(--text)" fontFamily="var(--font-mono)">
              {formatTWD(data[hover].value)}
            </text>
          </g>
        </g>
      )}
    </svg>
  );
}

function BarChart({ data, w = 720, h = 380, color, accentColor, valueFormat, activeKey }) {
  const fmtFn = valueFormat || formatTWD;
  const padL = 110, padR = 56, padT = 8, padB = 8;
  const innerW = w - padL - padR;
  const barH = (h - padT - padB) / data.length;
  const max = Math.max(...data.map(d => d.value)) * 1.05;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} style={{display:'block'}}>
      {data.map((d, i) => {
        const y = padT + i * barH;
        const bw = max > 0 ? (d.value / max) * innerW : 0;
        const isActive = activeKey === d.key;
        const c = isActive ? (accentColor || color) : (d.color || color);
        return (
          <g key={d.key || i}>
            <text x={padL-12} y={y+barH/2} textAnchor="end" dy="0.32em" fontSize="11.5" fill="var(--text)" fontWeight={isActive?700:500}>
              {d.label}
            </text>
            <rect x={padL} y={y+barH*0.18} width={innerW} height={barH*0.64} rx="3" fill="var(--bar-track)"/>
            <rect x={padL} y={y+barH*0.18} width={bw} height={barH*0.64} rx="3" fill={c}
                  style={{transition:'width .5s cubic-bezier(.4,0,.2,1)'}}/>
            <text x={padL+bw+8} y={y+barH/2} dy="0.32em" fontSize="11" fill="var(--muted)" fontFamily="var(--font-mono)">
              {fmtFn(d.value)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function Donut({ data, size = 200 }) {
  const r = size / 2 - 6;
  const cx = size / 2, cy = size / 2;
  const total = data.reduce((s,d) => s + d.value, 0);
  let acc = 0;
  const segments = data.map(d => {
    const start = (acc / total) * Math.PI * 2 - Math.PI / 2;
    acc += d.value;
    const end = (acc / total) * Math.PI * 2 - Math.PI / 2;
    const largeArc = end - start > Math.PI ? 1 : 0;
    const x1 = cx + r * Math.cos(start), y1 = cy + r * Math.sin(start);
    const x2 = cx + r * Math.cos(end), y2 = cy + r * Math.sin(end);
    const path = `M${x1},${y1} A${r},${r} 0 ${largeArc} 1 ${x2},${y2}`;
    return { path, color: d.color };
  });
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{display:'block'}}>
      {segments.map((s, i) => (
        <path key={i} d={s.path} fill="none" stroke={s.color} strokeWidth="20" strokeLinecap="butt"/>
      ))}
      <text x={cx} y={cy-6} textAnchor="middle" fontSize="11" fill="var(--muted)">總計</text>
      <text x={cx} y={cy+14} textAnchor="middle" fontSize="16" fontWeight="700" fill="var(--text)" fontFamily="var(--font-mono)">
        {formatTWD(total)}
      </text>
    </svg>
  );
}

function RegressionChart({ history, regression, predictX, predictY, band, dataXMax,
                           w = 720, h = 360, color, accentColor }) {
  const padL = 64, padR = 24, padT = 24, padB = 44;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const [hoverPt, setHoverPt] = useState(null);

  const allX = [...history.map(p => p.area), predictX].filter(Boolean);
  const allY = [...history.map(p => p.cost), predictY].filter(Boolean);
  const bandYs = (band || []).flatMap(b => [b[1], b[2]]);
  const xMin = Math.min(...allX) * 0.85;
  const xMax = Math.max(...allX) * 1.05;
  const yMin = Math.min(...allY, ...(bandYs.length ? [Math.min(...bandYs)] : [])) * 0.85;
  const yMax = Math.max(...allY, ...(bandYs.length ? [Math.max(...bandYs)] : [])) * 1.05;

  const xAt = v => padL + ((v - xMin) / (xMax - xMin)) * innerW;
  const yAt = v => padT + innerH - ((v - yMin) / ((yMax - yMin) || 1)) * innerH;
  const clampY = v => Math.max(padT, Math.min(padT + innerH, v));

  const { slope, intercept, se, r2 } = regression;
  const lineX1 = xMin, lineY1 = slope * lineX1 + intercept;
  const lineX2 = xMax, lineY2 = slope * lineX2 + intercept;

  // 信賴帶：優先用後端 t 分佈預測區間（喇叭形），無則退回固定 ±1.96·se
  let bandPts;
  if (band && band.length >= 2) {
    bandPts = band
      .filter(b => b[0] >= xMin && b[0] <= xMax)
      .map(b => [xAt(b[0]), clampY(yAt(b[2])), clampY(yAt(b[1]))]);
  } else {
    bandPts = [];
    for (let i = 0; i <= 40; i++) {
      const x = xMin + (xMax - xMin) * (i / 40);
      const yMid = slope * x + intercept;
      bandPts.push([xAt(x), clampY(yAt(yMid + 1.96 * se)), clampY(yAt(yMid - 1.96 * se))]);
    }
  }
  const bandPath = bandPts.length >= 2
    ? bandPts.map((p,i) => (i===0?`M${p[0]},${p[1]}`:`L${p[0]},${p[1]}`)).join(' ') +
      bandPts.slice().reverse().map(p => `L${p[0]},${p[2]}`).join(' ') + 'Z'
    : '';

  const yTicks = 4;
  const yTickVals = Array.from({length:yTicks+1}, (_,i) => yMin + (yMax-yMin)*i/yTicks);
  const xTicks = 4;
  const xTickVals = Array.from({length:xTicks+1}, (_,i) => xMin + (xMax-xMin)*i/xTicks);

  // 外插區：超出歷史資料範圍的右側區域淡色提示
  const extraZone = dataXMax != null && xMax > dataXMax;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} style={{display:'block'}}
         onMouseLeave={() => setHoverPt(null)}>
      {extraZone && (
        <rect x={xAt(dataXMax)} y={padT} width={padL + innerW - xAt(dataXMax)} height={innerH}
              fill="var(--warn)" fillOpacity="0.05"/>
      )}
      {yTickVals.map((v,i) => (
        <line key={i} x1={padL} x2={padL+innerW} y1={yAt(v)} y2={yAt(v)} stroke="var(--border)" strokeDasharray={i===0?'':'2 4'}/>
      ))}
      {yTickVals.map((v,i) => (
        <text key={'t'+i} x={padL-8} y={yAt(v)} textAnchor="end" dy="0.32em" fontSize="10" fill="var(--muted)" fontFamily="var(--font-mono)">
          {formatTWD(v)}
        </text>
      ))}
      {xTickVals.map((v,i) => (
        <text key={'x'+i} x={xAt(v)} y={h-10} textAnchor="middle" fontSize="10" fill="var(--muted)" fontFamily="var(--font-mono)">
          {Math.round(v).toLocaleString()}
        </text>
      ))}
      <text x={padL+innerW} y={h-10} textAnchor="end" fontSize="9.5" fill="var(--muted)" dx="-4" dy="-14">坪</text>
      {bandPath && <path d={bandPath} fill={color} fillOpacity="0.1"/>}
      <line x1={xAt(lineX1)} x2={xAt(lineX2)} y1={clampY(yAt(lineY1))} y2={clampY(yAt(lineY2))} stroke={color} strokeWidth="2" strokeDasharray="6 4"/>
      {history.map((p, i) => (
        <g key={i}>
          <circle cx={xAt(p.area)} cy={yAt(p.cost)} r={hoverPt === i ? 7 : 5}
                  fill={p.outlier ? 'var(--warn)' : 'var(--surface)'}
                  stroke={p.outlier ? 'var(--warn)' : color} strokeWidth="2"
                  style={{cursor:'pointer', transition:'r .15s'}}
                  onMouseEnter={() => setHoverPt(i)}/>
          {p.outlier && (
            <text x={xAt(p.area)} y={yAt(p.cost)-12} textAnchor="middle" fontSize="9" fill="var(--warn)" fontWeight="700">
              離群
            </text>
          )}
        </g>
      ))}
      {predictX != null && predictY != null && (
        <g>
          <line x1={xAt(predictX)} x2={xAt(predictX)} y1={padT} y2={padT+innerH}
                stroke={accentColor} strokeOpacity="0.25" strokeDasharray="3 3"/>
          <circle cx={xAt(predictX)} cy={yAt(predictY)} r="10" fill={accentColor} opacity="0.18"/>
          <circle cx={xAt(predictX)} cy={yAt(predictY)} r="6" fill={accentColor}/>
          <text x={Math.min(xAt(predictX)+12, padL+innerW-150)} y={Math.max(yAt(predictY)-8, padT+12)}
                fontSize="11" fontWeight="700" fill={accentColor} fontFamily="var(--font-mono)">
            預估 {formatTWD(predictY)}
          </text>
        </g>
      )}
      {hoverPt != null && history[hoverPt] && (() => {
        const p = history[hoverPt];
        const tx = Math.min(xAt(p.area)+12, padL+innerW-170);
        const ty = Math.max(yAt(p.cost)-58, padT+4);
        return (
          <g transform={`translate(${tx}, ${ty})`} pointerEvents="none">
            <rect width="162" height="52" rx="6" fill="var(--surface)" stroke="var(--border)"/>
            <text x="10" y="16" fontSize="10" fill="var(--text)" fontWeight="600">
              {(p.display_name || '').slice(0, 18)}
            </text>
            <text x="10" y="31" fontSize="10" fill="var(--muted)" fontFamily="var(--font-mono)">
              {p.area?.toLocaleString()} 坪
            </text>
            <text x="10" y="45" fontSize="11" fontWeight="700" fill="var(--text)" fontFamily="var(--font-mono)">
              {formatTWD(p.cost)}
            </text>
          </g>
        );
      })()}
      <g transform={`translate(${padL+12}, ${padT+12})`}>
        <rect width="98" height="22" rx="11" fill={color} fillOpacity="0.12"/>
        <text x="49" y="11" textAnchor="middle" dy="0.32em" fontSize="11" fontWeight="700" fill={color} fontFamily="var(--font-mono)">
          R² = {r2.toFixed(3)}
        </text>
      </g>
    </svg>
  );
}

Object.assign(window, { Sparkline, TrendChart, BarChart, Donut, RegressionChart });
