// Route comparison page — full-screen side-by-side multi-dimension view (TC18).
// Slides in from the right like route-detail, fills the entire main screen.

const { useState: useStateRC, useEffect: useEffectRC } = React;

// ─── Tone colors per positioning ─────────────────────────────────
function compareTone(positioning) {
  if (positioning && positioning.indexOf('综合最优') !== -1) return { dot: '#FF6633', soft: '#FFF1E5', label: '综合最优' };
  if (positioning && (positioning.indexOf('少走路') !== -1 || positioning.indexOf('省时') !== -1)) return { dot: '#1FAA59', soft: '#E1F4E8', label: '效率优先' };
  if (positioning && positioning.indexOf('偏好') !== -1) return { dot: '#2456a6', soft: '#E6EEF8', label: '偏好优先' };
  return { dot: '#8E8E93', soft: '#F1EFEC', label: positioning || '' };
}

// ─── Star rating ─────────────────────────────────────────────────
function StarRow({ score }) {
  var s = Math.min(100, Math.max(0, score || 0));
  var stars = Math.round(s / 20);
  var elms = [];
  for (var i = 0; i < 5; i++) {
    elms.push(
      <span key={i} style={{
        fontSize: 16, color: i < stars ? '#FF6633' : '#E0E0E0',
        marginRight: 2,
      }}>{i < stars ? '★' : '☆'}</span>
    );
  }
  return <span style={{ display: 'inline-flex', alignItems: 'center' }}>{elms}</span>;
}

// ─── Dimension row in the comparison table ────────────────────────
function CompareRow({ label, icon, values, format, highlight }) {
  var numericValues = values.map(function(v) {
    if (typeof v === 'number') return v;
    return parseFloat(String(v).replace(/[^0-9.]/g, '')) || 0;
  });

  var bestIdx = -1;
  if (highlight === 'highest') {
    bestIdx = numericValues.indexOf(Math.max.apply(null, numericValues));
  } else if (highlight === 'lowest') {
    bestIdx = numericValues.indexOf(Math.min.apply(null, numericValues));
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      padding: '10px 0', borderBottom: '1px solid #F0F0F3',
    }}>
      <div style={{
        width: 80, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 6,
        fontSize: 12.5, color: '#48484A', fontWeight: 600,
      }}>
        <Icon name={icon} size={13} color="#8E8E93" />
        {label}
      </div>
      {values.map(function(v, i) {
        var isBest = i === bestIdx;
        var displayVal = format ? format(v) : v;
        return (
          <div key={i} style={{
            flex: 1, textAlign: 'center',
            padding: '4px 6px', borderRadius: 8,
            background: isBest ? 'rgba(255,102,51,0.08)' : 'transparent',
          }}>
            <span className="num" style={{
              fontSize: 13.5, fontWeight: isBest ? 700 : 500,
              color: isBest ? '#FF6633' : '#1A1A1A',
            }}>
              {displayVal}
            </span>
            {isBest && (
              <div style={{ fontSize: 9, color: '#FF6633', fontWeight: 600, marginTop: 1 }}>
                最优
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Full-screen compare page ─────────────────────────────────────
function RouteComparePage({ routes, onBack, onSelectRoute }) {
  if (!routes || routes.length < 2) return null;

  var headers = routes.map(function(r, i) {
    var t = compareTone(r.positioning);
    return { label: r.positioning || ('方案 ' + (i + 1)), dot: t.dot, soft: t.soft, id: r.id };
  });

  function fmtMinutes(v) { return typeof v === 'number' ? v + '分钟' : String(v); }
  function fmtYuan(v) { return '¥' + (typeof v === 'number' ? v : String(v)); }

  var budgetValues = routes.map(function(r) { return r.total_avg || 0; });
  var timeValues = routes.map(function(r) {
    if (r.total_walking_minutes) return r.total_walking_minutes;
    var match = (r.total_time || '').match(/(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
  });
  var walkingValues = routes.map(function(r) {
    if (r.total_walking_minutes) return r.total_walking_minutes;
    if (r.total_distance) {
      var m = String(r.total_distance).match(/([\d.]+)/);
      return m ? parseFloat(m[1]) * 1000 / 80 : 0;
    }
    return 0;
  });
  var queueValues = routes.map(function(r) {
    if (r.constraintMatch && r.constraintMatch.queue === '可能排队') return 2;
    if (r.risks && r.risks.some(function(rk) { return rk.indexOf('排队') !== -1 || rk.indexOf('等位') !== -1; })) return 1;
    return 0;
  });
  var prefValues = routes.map(function(r) { return r._preferenceScore || 50; });
  var poiCounts = routes.map(function(r) { return (r.pois || []).length; });

  return (
    <div className="page-enter" style={{
      height: '100%', display: 'flex', flexDirection: 'column',
      background: '#F7F7F8',
    }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 14px', background: '#FBFBFD',
        borderBottom: '1px solid #EDEDEF',
      }}>
        <button onClick={onBack} style={{
          width: 36, height: 36, borderRadius: 10,
          background: 'transparent', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 0,
        }}>
          <Icon name="ChevronLeft" size={22} color="#1A1A1A" />
        </button>
        <div style={{ fontWeight: 700, fontSize: 17, color: '#1A1A1A', flex: 1 }}>
          多维度路线对比
        </div>
        <div style={{ width: 36 }} />
      </div>

      {/* Scrollable content */}
      <div className="frame-scroll" style={{
        flex: 1, overflowY: 'auto', overflowX: 'hidden',
        paddingBottom: 24,
      }}>
        {/* Column headers */}
        <div style={{
          display: 'flex', alignItems: 'stretch',
          padding: '16px 16px 12px', gap: 8,
        }}>
          <div style={{ width: 80, flexShrink: 0 }} />
          {headers.map(function(h, i) { return (
            <button key={i} onClick={function() { if (onSelectRoute) onSelectRoute(routes[i]); }} style={{
              flex: 1, textAlign: 'center', padding: '10px 8px',
              borderRadius: 12, border: 'none', cursor: 'pointer',
              background: h.soft, fontFamily: 'inherit',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, marginBottom: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: 999, background: h.dot, display: 'inline-block' }} />
                <span style={{ fontSize: 12, fontWeight: 700, color: h.dot }}>{h.label}</span>
              </div>
              <div style={{ fontSize: 9, color: '#8E8E93' }}>点击选择</div>
            </button>
          );})}
        </div>

        {/* Comparison table */}
        <div style={{ padding: '0 16px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>
            基础信息
          </div>

          <CompareRow label="预算" icon="Wallet" values={budgetValues} format={fmtYuan} highlight="lowest" />
          <CompareRow label="耗时" icon="Clock" values={timeValues} format={fmtMinutes} highlight="lowest" />
          <CompareRow label="步行" icon="Footprints" values={walkingValues} format={function(v) { return Math.round(v) + '分钟'; }} highlight="lowest" />
          <CompareRow label="POI数" icon="MapPin" values={poiCounts} format={function(v) { return v + '个'; }} highlight="highest" />

          <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', marginTop: 16, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>
            风险与质量
          </div>

          <CompareRow label="排队风险" icon="AlertTriangle" values={queueValues} format={function(v) {
            return v === 0 ? '低' : v === 1 ? '中' : '高';
          }} highlight="lowest" />

          <CompareRow label="偏好匹配" icon="Sparkles" values={prefValues} format={function(v) { return v + '分'; }} highlight="highest" />

          {/* Star row */}
          <div style={{
            display: 'flex', alignItems: 'center',
            padding: '12px 0', borderBottom: '1px solid #F0F0F3',
          }}>
            <div style={{
              width: 80, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 12.5, color: '#48484A', fontWeight: 600,
            }}>
              <Icon name="Star" size={13} color="#8E8E93" />
              偏好星级
            </div>
            {prefValues.map(function(v, i) { return (
              <div key={i} style={{ flex: 1, textAlign: 'center' }}>
                <StarRow score={v} />
              </div>
            );})}
          </div>

          {/* Route overview */}
          <div style={{ fontSize: 11, fontWeight: 700, color: '#8E8E93', marginTop: 16, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>
            路线概览
          </div>
          {routes.map(function(r, i) { return (
            <button key={i} onClick={function() { if (onSelectRoute) onSelectRoute(r); }} style={{
              width: '100%', padding: '12px 14px', marginBottom: 6,
              borderRadius: 12, background: '#fff', border: '1px solid #EDEDEF',
              cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
              display: 'flex', alignItems: 'center', gap: 10,
              boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: 999,
                background: compareTone(r.positioning).soft,
                color: compareTone(r.positioning).dot,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 700, flexShrink: 0,
              }}>{i + 1}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#1A1A1A' }}>
                  {r.route_name}
                </div>
                <div style={{ fontSize: 11, color: '#8E8E93', marginTop: 2 }}>
                  {(r.pois || []).map(function(p) { return p.short; }).join(' → ')}
                </div>
              </div>
              <Icon name="ChevronRight" size={14} color="#C7C7CC" />
            </button>
          );})}
        </div>
      </div>
    </div>
  );
}

// ─── Compare button (placed in RouteOptionsCard) ──────────────────
function CompareButton({ onClick, routeCount }) {
  return (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '10px 16px', borderRadius: 12,
      background: '#1A1A1A', color: '#fff',
      border: 'none', fontSize: 13, fontWeight: 600,
      cursor: 'pointer', fontFamily: 'inherit',
      boxShadow: '0 2px 10px rgba(0,0,0,0.12)',
    }}>
      <Icon name="LayoutGrid" size={14} color="#fff" />
      对比 {routeCount} 条路线
    </button>
  );
}

// Also expose the old name for backward compat
Object.assign(window, { RouteComparePanel: RouteComparePage, RouteComparePage, CompareButton });
