// Shared components and icons. Uses lucide via global `lucide` UMD.

const { useState, useEffect, useRef, useMemo, useLayoutEffect } = React;

// ─── Lucide icon helper ─────────────────────────────────────────
function Icon({ name, size = 18, color = 'currentColor', strokeWidth = 2, style = {} }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    const def = lucide[name] || lucide[name.charAt(0).toUpperCase() + name.slice(1)];
    if (!def) return;
    ref.current.innerHTML = '';
    const [tag, attrs, children] = def;
    const svgNs = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNs, 'svg');
    Object.entries({ ...attrs, width: size, height: size, stroke: color, 'stroke-width': strokeWidth }).forEach(([k, v]) => svg.setAttribute(k, v));
    (children || []).forEach(([childTag, childAttrs]) => {
      const child = document.createElementNS(svgNs, childTag);
      Object.entries(childAttrs).forEach(([k, v]) => child.setAttribute(k, v));
      svg.appendChild(child);
    });
    ref.current.appendChild(svg);
  }, [name, size, color, strokeWidth]);
  return <span ref={ref} style={{ display: 'inline-flex', lineHeight: 0, ...style }} />;
}

// ─── Status pill (营业中 / 等位) ─────────────────────────────────
function StatusPill({ tone = 'green', children, dot = true }) {
  const tones = {
    green: { bg: '#E8F5EC', fg: '#1F8B4C', dot: '#22C55E' },
    blue: { bg: '#E6F0FB', fg: '#1d63b8', dot: '#3B82F6' },
    amber: { bg: '#FFF1DE', fg: '#D14600', dot: '#F97316' },
    red: { bg: '#FCE9E5', fg: '#B43421', dot: '#EF4444' },
    gray: { bg: '#F1EFEC', fg: '#48484A', dot: '#9CA3AF' }
  };
  const t = tones[tone] || tones.gray;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: t.bg, color: t.fg,
      fontSize: 11.5, fontWeight: 500, padding: '3px 8px',
      borderRadius: 999, lineHeight: 1.2, whiteSpace: 'nowrap'
    }}>
      {dot && <span style={{ width: 5, height: 5, borderRadius: 999, background: t.dot }} />}
      {children}
    </span>);

}

// ─── Tag chip (positive/risk) ───────────────────────────────────
function Tag({ tone = 'green', children }) {
  const tones = {
    green: { bg: '#EAF6EC', fg: '#2c7a44' },
    blue: { bg: '#E6EEF8', fg: '#2456a6' },
    amber: { bg: '#FFF1DE', fg: '#D14600' },
    red: { bg: '#FCE9E5', fg: '#B43421' },
    neutral: { bg: '#F1EFEC', fg: '#454339' }
  };
  const t = tones[tone] || tones.neutral;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      background: t.bg, color: t.fg,
      fontSize: 12, padding: '3.5px 9px',
      borderRadius: 6, lineHeight: 1.25, fontWeight: 500
    }}>{children}</span>);

}

// ─── Quick edit chip (selectable) ───────────────────────────────
function Chip({ children, active, onClick, icon }) {
  return (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '9px 14px', borderRadius: 12,
      background: active ? '#FFF5F0' : '#fff',
      color: active ? '#E94A1A' : '#48484A',
      border: `1.5px solid ${active ? '#FFC8AA' : '#EDEDEF'}`,
      fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap',
      cursor: 'pointer', transition: 'all 0.18s',
      flexShrink: 0,
      boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
    }}>
      {icon && <Icon name={icon} size={13} />}
      {children}
    </button>);

}

// ─── Loading dots ──────────────────────────────────────────────
function LoadingDots({ color = '#F97316', size = 6 }) {
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', height: size + 2 }}>
      {[0, 1, 2].map((i) =>
      <span key={i} className="dot" style={{
        width: size, height: size, borderRadius: 999, background: color
      }} />
      )}
    </span>);

}

// ─── Avatar (assistant) ────────────────────────────────────────
function AssistantAvatar({ size = 28 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: 999,
      background: 'linear-gradient(135deg, #FF6633 0%, #FF6633 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexShrink: 0,
      boxShadow: '0 1px 2px rgba(249, 94, 42, 0.25)'
    }}>
      <svg width={size * 0.55} height={size * 0.55} viewBox="0 0 24 24" fill="none">
        <path d="M12 2L4 7v6c0 4.5 3.5 8.5 8 9 4.5-.5 8-4.5 8-9V7l-8-5z" fill="#fff" opacity="0.18" />
        <circle cx="12" cy="11" r="3" fill="#fff" />
        <path d="M5 19c1.8-2.3 4.3-3.5 7-3.5s5.2 1.2 7 3.5" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" />
      </svg>
    </div>);

}

// ─── Big orange button ──────────────────────────────────────────
function PrimaryBtn({ children, onClick, icon, full = false, size = 'md' }) {
  const sizes = { sm: { p: '10px 14px', f: 13 }, md: { p: '12px 18px', f: 14 }, lg: { p: '14px 20px', f: 15 } };
  const s = sizes[size];
  return (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
      padding: s.p, fontSize: s.f, fontWeight: 600,
      background: '#FF6633',
      color: '#fff', border: 'none', borderRadius: 12,
      cursor: 'pointer', width: full ? '100%' : 'auto',
      letterSpacing: 0.2, fontFamily: 'inherit'
    }}>
      {icon && <Icon name={icon} size={s.f + 2} color="#fff" />}
      {children}
    </button>);

}

function SecondaryBtn({ children, onClick, icon, full = false, size = 'md' }) {
  const sizes = { sm: { p: '8px 14px', f: 13 }, md: { p: '10px 16px', f: 14 }, lg: { p: '12px 18px', f: 15 } };
  const s = sizes[size];
  return (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
      padding: s.p, fontSize: s.f, fontWeight: 500,
      background: '#fff', color: '#1d1d1f',
      border: '1px solid #E5E5E7', borderRadius: 12,
      cursor: 'pointer', width: full ? '100%' : 'auto'
    }}>
      {icon && <Icon name={icon} size={s.f + 2} />}
      {children}
    </button>);

}

// ─── Toast ──────────────────────────────────────────────────────
function Toast({ message }) {
  if (!message) return null;
  return (
    <div className="toast" style={{
      position: 'absolute', bottom: 110, left: '50%',
      background: 'rgba(30, 25, 20, 0.92)',
      color: '#fff', fontSize: 13, padding: '10px 18px',
      borderRadius: 999, zIndex: 100, pointerEvents: 'none',
      backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
      boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
      whiteSpace: 'nowrap'
    }}>
      {message}
    </div>);

}

// ─── Mock data ─────────────────────────────────────────────────
const MOCK_ROUTE = {
  route_id: 'r-001',
  route_name: '朋友轻聚会路线',
  total_time: '3-4 小时',
  total_budget: '约 135 元',
  total_avg_per_person: 135,
  total_distance: '约 1.6km',
  transport_summary: '地铁 10 号线可到，节点间步行 5-10 分钟',
  risk_summary: '晚餐高峰可能等位，建议提前取号',
  current_realtime: '山野烤肉当前营业中，预计等位 15 分钟（10 分钟前更新）',
  recommendation_reason:
  '我推荐这条路线，是因为它比较稳：人均在预算内，几个地点离得近，不需要频繁换乘。烤肉店离地铁近，很多评价都提到适合朋友聚会、分量足；吃完后走路几分钟就能到甜品店，方便继续聊天。'
};

const MOCK_PLACES = [
{
  id: 'p1',
  name: '城东微展厅 · 当代城市影像',
  short: '小型展览 / 街区拍照',
  category: '展览',
  rating: 4.7,
  review_count: 1284,
  avg_price: 30,
  distance: '距出发地 2.3km',
  opening_hours: '10:00 - 19:00',
  current_status: '当前开放中',
  current_status_short: '开放中',
  status_tone: 'green',
  wait_time: '无需排队',
  tags: ['出片好看', '适合拍照', '人不多', '安静'],
  risk_tags: ['闭馆较早'],
  recommendation_reason:
  '这是这条路线的轻量起点，离地铁口 8 分钟。展厅不大，最近评价里很多人说"出片好看、不挤"，逛完正好饭点。',
  review_summary: '近 30 天里被提到最多的是「光线好」「适合拍照」「氛围安静」。',
  lng: 116.4600, lat: 39.9325,
  imageUrl: 'images/stores/chenxi-exhibition-1.jpg',
  images: [
    'images/stores/chenxi-exhibition-1.jpg',
    'images/stores/chenxi-exhibition-2.jpg',
    'images/stores/chenxi-exhibition-3.jpg',
    'images/stores/chenxi-exhibition-4.jpg',
  ],
  address: '朝阳区团结湖北路3号',
  mock_x: 28, mock_y: 22
},
{
  id: 'p2',
  name: '山野炭火烤肉（团结湖店）',
  short: '山野烤肉',
  category: '烤肉',
  rating: 4.6,
  review_count: 3412,
  avg_price: 95,
  distance: '距上一站 650m',
  opening_hours: '11:30 - 22:30',
  current_status: '当前营业中 · 预计等位 15 分钟',
  current_status_short: '等位约 15 分',
  status_tone: 'amber',
  wait_time: '约 15 分钟',
  tags: ['适合朋友聚会', '分量足', '离地铁近', '适合聊天', '服务好'],
  risk_tags: ['晚高峰可能等位', '环境偏热闹'],
  recommendation_reason:
  '这家是路线主菜：人均 95，靠近地铁口，很多评价都说"分量足、适合一群人吃"。我把它放在你饭点会到的时间，已经预留好取号时间。',
  review_summary: '最近 30 天里高频提到「分量足」「服务热情」「适合多人」。',
  lng: 116.4655, lat: 39.9270,
  imageUrl: 'images/stores/shanye-kaorou-1.jpg',
  images: [
    'images/stores/shanye-kaorou-1.jpg',
    'images/stores/shanye-kaorou-2.jpg',
    'images/stores/shanye-kaorou-3.jpg',
    'images/stores/shanye-kaorou-4.jpg',
  ],
  address: '朝阳区团结湖南路12号',
  mock_x: 52, mock_y: 60
},
{
  id: 'p3',
  name: '慢岛 · 甜品咖啡',
  short: '慢岛甜品咖啡',
  category: '咖啡 / 甜品',
  rating: 4.8,
  review_count: 902,
  avg_price: 38,
  distance: '距上一站 400m',
  opening_hours: '11:00 - 22:00',
  current_status: '当前营业中',
  current_status_short: '营业中',
  status_tone: 'green',
  wait_time: '无需排队',
  tags: ['适合聊天', '环境安静', '出片好看', '甜品好吃'],
  risk_tags: [],
  recommendation_reason:
  '吃完走 6 分钟就到，环境安静，可以坐着继续聊天。最近评价里被提到最多的是"提拉米苏"和"窗边位"。',
  review_summary: '常被提到「氛围好」「适合两三人慢聊」「不催台」。',
  lng: 116.4625, lat: 39.9310,
  imageUrl: 'images/stores/mandao-dessert-1.jpg',
  images: [
    'images/stores/mandao-dessert-1.jpg',
    'images/stores/mandao-dessert-2.jpg',
    'images/stores/mandao-dessert-3.jpg',
    'images/stores/mandao-dessert-4.jpg',
  ],
  address: '朝阳区团结湖东街5号',
  mock_x: 80, mock_y: 30
}];


const MOCK_TRANSPORT = [
{
  from: '当前位置',
  to: '城东微展厅',
  mode: '地铁优先',
  icon: 'TrainFront',
  detail: '乘坐地铁 10 号线至团结湖站，从 A 口出，步行约 8 分钟',
  metro_line: '10 号线',
  station: '团结湖站',
  exit: 'A 口',
  walking_time: '8 分钟',
  distance: '2.3km',
  primary: '一键导航',
  secondary: null
},
{
  from: '城东微展厅',
  to: '山野烤肉',
  mode: '步行',
  icon: 'Footprints',
  detail: '距离约 650m，步行约 9 分钟，沿团结湖南路向东',
  walking_time: '9 分钟',
  distance: '650m',
  primary: '查看步行路线',
  secondary: null
},
{
  from: '山野烤肉',
  to: '慢岛甜品咖啡',
  mode: '步行',
  icon: 'Footprints',
  detail: '距离约 400m，步行约 6 分钟，穿过一条小街区',
  walking_time: '6 分钟',
  distance: '400m',
  primary: '查看路线',
  secondary: null
},
{
  from: '慢岛甜品咖啡',
  to: '返程',
  mode: '地铁 / 打车',
  icon: 'Home',
  detail: '步行 5 分钟到地铁站；如果较晚可打车，预计 20 元',
  walking_time: '5 分钟',
  taxi_cost: '约 20 元',
  primary: '导航回家',
  secondary: '一键打车'
}];


const REQUIREMENTS = [
{ label: '场景', value: '朋友周末轻聚会', status: 'inferred', icon: 'Users' },
{ label: '时间', value: '周六下午', status: 'user', icon: 'Clock' },
{ label: '地点', value: '当前定位附近', status: 'inferred', icon: 'MapPin' },
{ label: '同行人', value: '朋友', status: 'user', icon: 'Users' },
{ label: '预算', value: '人均 150 元以内', status: 'user', icon: 'Wallet' },
{ label: '想做的事', value: '吃饭 · 拍照 · 聊天', status: 'user', icon: 'Sparkles' },
{ label: '怎么去更方便', value: '少走路 · 地铁可达', status: 'inferred', icon: 'TrainFront' },
{ label: '特别注意', value: '不想排队，稳妥优先', status: 'user', icon: 'AlertCircle' }];


Object.assign(window, {
  Icon, StatusPill, Tag, Chip, LoadingDots, AssistantAvatar,
  PrimaryBtn, SecondaryBtn, Toast,
  MOCK_ROUTE, MOCK_PLACES, MOCK_TRANSPORT, REQUIREMENTS
});