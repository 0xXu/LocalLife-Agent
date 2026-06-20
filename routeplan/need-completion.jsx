// Need-completion + multi-route output flow.
// Triggered when the user TAPS a scenario card (not when they type free text).
//
// Flow: tap → SystemPromptCard + NeedCompletionCard (progressive Q&A) →
// after the last key question is answered, auto-generates RouteOptionsCard.

const { useState: useStateNC, useEffect: useEffectNC, useRef: useRefNC } = React;

// ─── Per-scenario data ─────────────────────────────────────────
// `tintIdx` indexes into CARD_TINTS in chat-screen.jsx (peach / green / blue cycle).

// Generate dynamic time options based on current time.
// Always includes "现在" plus 3 upcoming hourly slots.
function getDynamicTimeOptions() {
  var now = new Date();
  var currentHour = now.getHours();
  var slots = ['现在'];
  for (var i = 0; i < 3; i++) {
    var h = (currentHour + i + 1) % 24;
    var hh = h < 10 ? '0' + h : '' + h;
    slots.push(hh + ':00');
  }
  return slots;
}

const SCENARIOS = {
  '朋友聚会': {
    icon: 'Users', tintIdx: 0,
    intro: '我可以帮你规划适合朋友见面、吃饭、聊天或轻活动的路线。先补充几个关键信息。',
    questions: [
      { id: 'time',   label: '几点出发？',         options: getDynamicTimeOptions() },
      { id: 'place',  label: '想在哪附近规划？',   options: ['当前位置附近', '地铁站附近', '指定商圈', '输入地点'] },
      { id: 'budget', label: '人均预算？',          options: ['¥80 以内', '¥150 以内', '¥200 以内', '自定义'] },
      { id: 'duration', label: '预计玩多久？',      options: ['2 小时内', '3 小时内', '4 小时内', '不限'] },
      { id: 'mood',   label: '更想怎么聚？',       options: ['吃饭聊天', '吃饭 + 拍照', '吃饭 + 娱乐', '轻松逛逛'] },
    ],
  },
  '情侣约会': {
    icon: 'Heart', tintIdx: 1,
    intro: '我可以帮你规划安静、有氛围的约会路线，兼顾吃饭、拍照和散步。先补充几个关键信息。',
    questions: [
      { id: 'time',   label: '几点出发？',         options: getDynamicTimeOptions() },
      { id: 'place',  label: '在哪附近？',         options: ['当前位置附近', '地铁站附近', '指定商圈', '输入地点'] },
      { id: 'budget', label: '人均预算？',         options: ['¥150 以内', '¥250 以内', '¥400 以内', '不设上限'] },
      { id: 'duration', label: '预计多久？',       options: ['2 小时内', '3 小时内', '4 小时内', '不限'] },
      { id: 'mood',   label: '想要什么氛围？',     options: ['安静聊天', '出片拍照', '慢节奏散步', '看演出 / 看展'] },
    ],
  },
  '一个人放松': {
    icon: 'Coffee', tintIdx: 2,
    intro: '帮你找能慢下来、不被打扰的地方。咖啡、书店、轻食都可以安排，节奏由你决定。',
    questions: [
      { id: 'time',   label: '几点出发？',     options: getDynamicTimeOptions() },
      { id: 'place',  label: '在哪附近？',     options: ['当前位置附近', '地铁站附近', '指定商圈', '输入地点'] },
      { id: 'budget', label: '预算？',         options: ['¥50 以内', '¥100 以内', '¥200 以内', '不设上限'] },
      { id: 'duration', label: '预计多久？',   options: ['2 小时内', '3 小时内', '4 小时内', '不限'] },
      { id: 'mood',   label: '想做什么？',     options: ['只想发呆', '看书 / 写东西', '拍照 + 散步', '吃点东西'] },
    ],
  },
  '亲子遛娃': {
    icon: 'Baby', tintIdx: 0,
    intro: '帮你规划安全、室内可选、不太远的亲子路线，吃饭和玩都能照顾到。',
    questions: [
      { id: 'time',   label: '几点出发？',       options: getDynamicTimeOptions() },
      { id: 'place',  label: '在哪附近？',       options: ['当前位置附近', '地铁站附近', '指定商圈', '输入地点'] },
      { id: 'budget', label: '人均预算？',       options: ['¥80 以内', '¥150 以内', '¥250 以内', '自定义'] },
      { id: 'duration', label: '预计多久？',     options: ['2 小时内', '4 小时内', '6 小时内', '不限'] },
      { id: 'mood',   label: '孩子喜欢什么？',   options: ['室内乐园', '互动展览', '户外公园', '美食 + 短玩'] },
    ],
  },
  '下班回血': {
    icon: 'Soup', tintIdx: 1,
    intro: '帮你找一份热的、不远的、不用等位的晚餐。快进快出，节奏要轻。',
    questions: [
      { id: 'time',   label: '几点下班出发？',   options: getDynamicTimeOptions() },
      { id: 'place',  label: '在哪附近？',       options: ['当前位置附近', '公司附近', '回家路上', '输入地点'] },
      { id: 'budget', label: '今天想花多少？',   options: ['¥40 以内', '¥60 以内', '¥100 以内', '看心情'] },
      { id: 'duration', label: '预计多久？',     options: ['1 小时内', '2 小时内', '3 小时内', '不限'] },
      { id: 'mood',   label: '今天想吃点什么？', options: ['热汤面食', '正经一顿', '清淡轻食', '喝一口酒'] },
    ],
  },
  '临时救场': {
    icon: 'Zap', tintIdx: 2,
    intro: '马上帮你找一个能见面、能等人或能讲事的地方，节奏要快。',
    questions: [
      { id: 'time',   label: '几点需要？',     options: getDynamicTimeOptions() },
      { id: 'place',  label: '你现在在哪？',   options: ['当前位置', '地铁站附近', '商圈附近', '输入地点'] },
      { id: 'budget', label: '人均预算？',     options: ['不限', '¥80 以内', '¥150 以内', '自定义'] },
      { id: 'duration', label: '预计多久？',   options: ['1 小时内', '2 小时内', '3 小时内', '不限'] },
      { id: 'mood',   label: '用来做什么？',   options: ['见朋友聊事', '等人 / 杀时间', '简单吃一口', '找个安静的角落'] },
    ],
  },
};

// Map an answer id to its short summary tag (for the parsing summary line)
function summarizeAnswers(scene, answers) {
  const order = ['time', 'place', 'budget', 'mood'];
  const parts = order.map((k) => answers[k]).filter(Boolean);
  return [scene, ...parts].join(' ｜ ');
}

// ─── Per-scenario route options ────────────────────────────────
// Each route variant is light meta-data — the underlying detail page still
// uses MOCK_PLACES / MOCK_ROUTE. (TODO: drive detail page from selected variant id.)
const ROUTE_OPTIONS = {
  '朋友聚会': [
    {
      id: 'r-fr-a', positioning: '综合最优', tone: 'orange',
      route_name: '朋友轻聚会路线',
      total_time: '3-4 小时', total_avg: 135, total_distance: '1.6km',
      transport: '地铁 10 号线 · 步行 5–10 分钟',
      pois: [
        { short: '城东微展厅',     category: '展览' },
        { short: '山野炭火烤肉', category: '烤肉' },
        { short: '慢岛甜品咖啡', category: '甜品' },
      ],
      reason: '兼顾预算、距离和体验：地铁直达，节点离得近，吃完正好聊到甜品。',
      risks: ['晚餐高峰可能等位 15 分钟', '展厅 19:00 闭馆'],
    },
    {
      id: 'r-fr-b', positioning: '更适合拍照', tone: 'pink',
      route_name: '出片版聚会路线',
      total_time: '4-5 小时', total_avg: 150, total_distance: '2.1km',
      transport: '地铁 10 号线 · 步行 10–15 分钟',
      pois: [
        { short: '城东微展厅',     category: '展览' },
        { short: '798 街区漫步', category: '街区' },
        { short: '蘑屋拍照面馆', category: '面食' },
        { short: '慢岛甜品咖啡', category: '甜品' },
      ],
      reason: '强调出片：展览 + 街区 + 拍照面馆，回家相册能凑一组九宫格。',
      risks: ['路线偏长，建议穿舒适鞋', '街区下午光线最好'],
    },
    {
      id: 'r-fr-c', positioning: '更少排队 · 更低预算', tone: 'green',
      route_name: '松弛版聚会路线',
      total_time: '2.5-3 小时', total_avg: 85, total_distance: '1.2km',
      transport: '公交 / 步行均可',
      pois: [
        { short: '团结湖公园',         category: '公园' },
        { short: '渔小馆家常菜',     category: '小馆' },
        { short: '隔壁书店咖啡角', category: '书店' },
      ],
      reason: '预算友好，几乎不用排队，节奏松散，适合慢慢聊。',
      risks: ['书店 21:00 关门'],
    },
  ],
  '情侣约会': [
    {
      id: 'r-cp-a', positioning: '综合最优', tone: 'orange',
      route_name: '安静约会路线',
      total_time: '3-4 小时', total_avg: 220, total_distance: '1.4km',
      transport: '地铁 14 号线 · 步行 5–10 分钟',
      pois: [
        { short: '巷里小馆 · 双人位', category: '私房菜' },
        { short: '城市观景平台',         category: '观景' },
        { short: '雨夜咖啡 · 窗边位', category: '咖啡' },
      ],
      reason: '气氛、距离、预算都稳：两人位提前订，吃完散步看夜景。',
      risks: ['周末晚餐需提前预约'],
    },
    {
      id: 'r-cp-b', positioning: '更适合出片', tone: 'pink',
      route_name: '出片版约会路线',
      total_time: '4 小时', total_avg: 280, total_distance: '2.0km',
      transport: '地铁 14 号线 · 步行 15 分钟',
      pois: [
        { short: '城西胶片小展',     category: '展览' },
        { short: '街角法餐 · 露台', category: '法餐' },
        { short: '蓝色屋顶酒吧',     category: '酒吧' },
      ],
      reason: '画面感强，三段都好拍：展览 + 露台 + 夜景酒吧。',
      risks: ['酒吧 22:00 后较吵', '露台座位有限'],
    },
    {
      id: 'r-cp-c', positioning: '更低预算 · 更轻松', tone: 'green',
      route_name: '随性约会路线',
      total_time: '2-3 小时', total_avg: 120, total_distance: '1.0km',
      transport: '步行可达',
      pois: [
        { short: '园林公园',         category: '公园' },
        { short: '街口面馆',         category: '面食' },
        { short: '河边书店咖啡', category: '书店' },
      ],
      reason: '不赶场，几乎不排队，重点是慢节奏陪伴。',
      risks: [],
    },
  ],
  '一个人放松': [
    {
      id: 'r-so-a', positioning: '安静慢节奏', tone: 'orange',
      route_name: '一个人发呆路线',
      total_time: '2-3 小时', total_avg: 70, total_distance: '0.6km',
      transport: '步行可达',
      pois: [
        { short: '独椅咖啡',     category: '咖啡' },
        { short: '小院图书馆', category: '书店' },
      ],
      reason: '两个都不催台，可以从下午坐到傍晚。',
      risks: ['周末人略多，建议工作日来'],
    },
    {
      id: 'r-so-b', positioning: '换个地方走走', tone: 'green',
      route_name: '微散步路线',
      total_time: '2 小时', total_avg: 50, total_distance: '1.5km',
      transport: '步行 + 公交',
      pois: [
        { short: '运河步道',         category: '散步' },
        { short: '街角面包店',     category: '简餐' },
      ],
      reason: '想动一动但不想很累：走一段路，吃点东西，回家。',
      risks: [],
    },
  ],
  '亲子遛娃': [
    {
      id: 'r-pt-a', positioning: '综合最优', tone: 'orange',
      route_name: '家门口亲子路线',
      total_time: '3 小时', total_avg: 130, total_distance: '1.0km',
      transport: '步行 / 打车 5 分钟',
      pois: [
        { short: '亲子室内乐园', category: '游乐' },
        { short: '邻家厨房',         category: '简餐' },
        { short: '迷你绘本角',     category: '书店' },
      ],
      reason: '不用赶路，吃喝玩睡都能照顾到，孩子状态稳。',
      risks: ['3 岁以下需家长全程陪同', '中午是用餐高峰'],
    },
    {
      id: 'r-pt-b', positioning: '更有体验', tone: 'pink',
      route_name: '互动展览路线',
      total_time: '3.5 小时', total_avg: 180, total_distance: '1.5km',
      transport: '地铁 6 号线 · 步行 8 分钟',
      pois: [
        { short: '城市互动展',     category: '展览' },
        { short: '展厅旁的简餐', category: '简餐' },
      ],
      reason: '互动展能让孩子专注，看完吃一口就能回家。',
      risks: ['展览需提前预约', '记得带身份证'],
    },
    {
      id: 'r-pt-c', positioning: '更低预算 · 更户外', tone: 'green',
      route_name: '公园 + 简餐路线',
      total_time: '2-3 小时', total_avg: 60, total_distance: '0.8km',
      transport: '步行可达',
      pois: [
        { short: '社区公园',         category: '公园' },
        { short: '隔壁便民食堂', category: '简餐' },
      ],
      reason: '便宜、放电、就近吃饭，状态崩了能很快回家。',
      risks: ['雨天不建议'],
    },
  ],
  '下班回血': [
    {
      id: 'r-aw-a', positioning: '综合最优', tone: 'orange',
      route_name: '快进快出晚饭',
      total_time: '45 分钟', total_avg: 55, total_distance: '0.4km',
      transport: '步行 5 分钟',
      pois: [
        { short: '老张牛肉面',  category: '面食' },
      ],
      reason: '不用等位，10 分钟上桌，吃完直接回家。',
      risks: ['辣度可调，建议提前说'],
    },
    {
      id: 'r-aw-b', positioning: '想喝一口', tone: 'pink',
      route_name: '小酌一杯版',
      total_time: '1.5 小时', total_avg: 95, total_distance: '0.5km',
      transport: '步行 8 分钟',
      pois: [
        { short: '居酒屋·味屋', category: '居酒屋' },
      ],
      reason: '能吃一点、能喝一口，安静不吵，适合放松神经。',
      risks: ['晚 19:30 后排队较久'],
    },
  ],
  '临时救场': [
    {
      id: 'r-em-a', positioning: '最近', tone: 'orange',
      route_name: '街角咖啡见面',
      total_time: '即刻', total_avg: 35, total_distance: '0.2km',
      transport: '步行 3 分钟',
      pois: [
        { short: '街角连锁咖啡', category: '咖啡 · 有座' },
      ],
      reason: '走 3 分钟到，几乎一定有座，能讲事能等人。',
      risks: ['晚间座位较紧张'],
    },
    {
      id: 'r-em-b', positioning: '最静', tone: 'green',
      route_name: '社区图书馆门厅',
      total_time: '即刻', total_avg: 0, total_distance: '0.6km',
      transport: '步行 8 分钟',
      pois: [
        { short: '社区图书馆门厅', category: '公共空间' },
      ],
      reason: '绝对安静，适合等人、讲重要的事，免费有座。',
      risks: [],
    },
    {
      id: 'r-em-c', positioning: '最省事', tone: 'pink',
      route_name: '便利店休息区',
      total_time: '即刻', total_avg: 12, total_distance: '0.3km',
      transport: '步行 5 分钟',
      pois: [
        { short: '便利店休息区', category: '便利店' },
      ],
      reason: '几乎不用走路，有座位，能顺手买水或小吃。',
      risks: [],
    },
  ],
};

// Alt POIs for 临时救场 — shown as a footer list, not full routes.
const EMERGENCY_ALTS = [
  { name: '便利店休息区',     hint: '5 分钟步行，有座位'  },
  { name: '社区图书馆门厅', hint: '8 分钟步行，绝对安静' },
];

// ─── System prompt card (NOT a user bubble) ────────────────────
function SystemPromptCard({ scene, onChangeScene }) {
  const cfg = SCENARIOS[scene];
  if (!cfg) return null;
  const tint = (window.CARD_TINTS || [{ bg: '#FFF1E5', fg: '#E94A1A' }])[cfg.tintIdx % 3];
  return (
    <div className="fade-up" style={{ padding: '14px 16px 0' }}>
      <div style={{
        display: 'flex', gap: 12, padding: '13px 14px',
        background: '#FFFFFF', border: '1px solid #EDEDEF', borderRadius: 14,
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10, flexShrink: 0,
          background: tint.bg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name={cfg.icon} size={18} color={tint.fg} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 3, gap: 8,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a' }}>
              你选择了「{scene}」
            </div>
            <button onClick={onChangeScene} style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              fontSize: 11.5, color: '#8e8e93', padding: 0,
              display: 'inline-flex', alignItems: 'center', gap: 2,
            }}>
              <Icon name="RefreshCw" size={10} color="#8e8e93" />
              换一个
            </button>
          </div>
          <div style={{ fontSize: 12.5, color: '#48484A', lineHeight: 1.55 }}>
            {cfg.intro}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Need-completion card (progressive Q&A) ────────────────────
function NeedCompletionCard({ scene, answers, onAnswer, onSkip, onEditAnswer }) {
  const cfg = SCENARIOS[scene];
  if (!cfg) return null;

  // Find the first unanswered question
  const questions = cfg.questions;
  const qIdx = questions.findIndex((q) => !answers[q.id]);
  const isDone = qIdx === -1;
  const currentQ = isDone ? null : questions[qIdx];
  const answeredQs = questions.filter((q) => answers[q.id]);
  const tint = (window.CARD_TINTS || [{ bg: '#FFF1E5', fg: '#E94A1A' }])[cfg.tintIdx % 3];

  // Custom-input state for "自定义" / "输入地点" options
  const [customMode, setCustomMode] = useStateNC(false);
  const [customText, setCustomText] = useStateNC('');
  useEffectNC(() => { setCustomMode(false); setCustomText(''); }, [qIdx]);

  const isCustomOption = (opt) =>
    opt === '自定义' || opt === '输入地点' || opt === '看心情' || opt === '不设上限' || opt === '不限';

  if (isDone) return null; // parent renders RouteOptionsCard once all answered

  return (
    <div className="fade-up" style={{ padding: '12px 16px 0' }}>
      <div style={{
        background: '#fff', border: '1px solid #EDEDEF', borderRadius: 14,
        overflow: 'hidden',
        boxShadow: '0 1px 0 rgba(0,0,0,0.02)',
      }}>
        {/* head */}
        <div style={{
          padding: '12px 14px 10px',
          borderBottom: '1px solid #EDEDEF',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: 'linear-gradient(180deg, #FFFFFF 0%, #fff 100%)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Icon name="ListChecks" size={13} color={tint.fg} />
            <span style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a' }}>
              {scene} · 需求补全
            </span>
          </div>
          <span className="num" style={{ fontSize: 11.5, color: '#8e8e93' }}>
            {qIdx + 1} / {questions.length}
          </span>
        </div>

        {/* progress bar */}
        <div style={{ height: 3, background: '#EDEDEF', position: 'relative' }}>
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0,
            width: `${(qIdx / questions.length) * 100}%`,
            background: tint.fg, transition: 'width 0.3s',
          }} />
        </div>

        {/* answered pills */}
        {answeredQs.length > 0 && (
          <div style={{ padding: '10px 14px 0', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {answeredQs.map((q) => (
              <button key={q.id} onClick={() => onEditAnswer(q.id)} style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                background: '#F7F7F8', border: '1px solid #EDEDEF',
                borderRadius: 999, padding: '4px 8px 4px 10px',
                fontSize: 11.5, color: '#48484A', cursor: 'pointer',
                fontFamily: 'inherit',
              }}>
                <span style={{ color: '#8e8e93' }}>{shortLabel(q.id)}</span>
                <span style={{ color: '#1a1a1a', fontWeight: 500 }}>{answers[q.id]}</span>
                <Icon name="Pencil" size={10} color="#8e8e93" />
              </button>
            ))}
          </div>
        )}

        {/* current question */}
        <div className="fade-up" key={qIdx} style={{ padding: '14px 14px 4px' }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', marginBottom: 12, lineHeight: 1.4 }}>
            {currentQ.label}
          </div>
          {!customMode && (
            <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
              {currentQ.options.map((opt) => (
                <button
                  key={opt}
                  onClick={() => {
                    if (isCustomOption(opt) && (opt === '自定义' || opt === '输入地点')) {
                      setCustomMode(true);
                    } else {
                      onAnswer(currentQ.id, opt);
                    }
                  }}
                  style={{
                    padding: '11px 12px', borderRadius: 10,
                    background: '#fff', border: '1px solid #E5E5E7',
                    fontSize: 13, fontWeight: 500, color: '#1a1a1a',
                    cursor: 'pointer', fontFamily: 'inherit',
                    textAlign: 'center', transition: 'all 0.15s',
                  }}
                >
                  {opt}
                </button>
              ))}
            </div>
            {/* 如果选项中已有"输入地点"/"自定义"入口，就不重复显示自定义输入按钮 */}
            {!currentQ.options.some(function(o) { return o === '输入地点' || o === '自定义'; }) && (
            <button
              onClick={function() { setCustomMode(true); }}
              style={{
                width: '100%', marginTop: 8, padding: '10px 12px', borderRadius: 10,
                background: '#FFF', border: '1.5px dashed #D1D1D6',
                fontSize: 12.5, fontWeight: 500, color: '#8e8e93',
                cursor: 'pointer', fontFamily: 'inherit',
                textAlign: 'center', transition: 'all 0.15s',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
              }}
            >
              <Icon name="Pencil" size={11} color="#8e8e93" /> 自定义输入
            </button>
            )}
            </div>
          )}

          {customMode && (
            <div className="fade-up" style={{
              display: 'flex', gap: 8, alignItems: 'center',
              padding: '4px 0',
            }}>
              <input
                autoFocus
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && customText.trim()) {
                    onAnswer(currentQ.id, customText.trim());
                  }
                }}
                placeholder={
                  currentQ.id === 'place'  ? '比如：三里屯 / 国贸 / 朝阳大悦城' :
                  currentQ.id === 'time'   ? '比如：明天上午 10 点' :
                  currentQ.id === 'budget' ? '比如：¥120 以内' : '输入自定义内容…'
                }
                style={{
                  flex: 1, padding: '10px 12px', fontSize: 13.5,
                  border: '1px solid #E5E5E7', borderRadius: 10,
                  outline: 'none', fontFamily: 'inherit', background: '#fff',
                  color: '#1a1a1a',
                }}
              />
              <button
                onClick={() => { if (customText.trim()) onAnswer(currentQ.id, customText.trim()); }}
                disabled={!customText.trim()}
                style={{
                  padding: '10px 14px', fontSize: 13, fontWeight: 600,
                  background: customText.trim() ? tint.fg : '#E5E5E7',
                  color: '#fff', border: 'none', borderRadius: 10,
                  cursor: customText.trim() ? 'pointer' : 'default',
                }}
              >确定</button>
              <button
                onClick={() => { setCustomMode(false); setCustomText(''); }}
                style={{
                  padding: '10px 4px', fontSize: 12, color: '#8e8e93',
                  background: 'transparent', border: 'none', cursor: 'pointer',
                }}
              >取消</button>
            </div>
          )}
        </div>

        {/* tertiary skip link */}
        <div style={{ padding: '8px 14px 12px', textAlign: 'right' }}>
          <button onClick={onSkip} style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            fontSize: 12, color: '#8e8e93', padding: 0,
            display: 'inline-flex', alignItems: 'center', gap: 2,
          }}>
            先按默认推荐看看
            <Icon name="ChevronRight" size={11} color="#8e8e93" />
          </button>
        </div>
      </div>
    </div>
  );
}

// Short label for the answered-question pill
function shortLabel(qid) {
  return { time: '时间', place: '地点', budget: '预算', mood: '偏好' }[qid] || qid;
}

// ─── Parsing-summary chip (top of route results) ───────────────
function ParsingSummary({ scene, answers, defaulted, routeCount }) {
  const summary = summarizeAnswers(scene, answers);
  const count = routeCount || (ROUTE_OPTIONS[scene]?.length || 1);
  return (
    <div className="fade-up" style={{ padding: '4px 16px 0' }}>
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 8,
        padding: '9px 12px',
        background: '#FFF1E5', border: '1px solid #FFD8B8',
        borderRadius: 10,
      }}>
        <Icon name="Wand2" size={13} color="#D14600" style={{ marginTop: 2, flexShrink: 0 }} />
        <div style={{ fontSize: 12, color: '#D14600', lineHeight: 1.55, flex: 1, minWidth: 0 }}>
          {defaulted
            ? <>已按默认设定为你生成路线 — <span style={{ fontWeight: 600 }}>{summary}</span>。你可以随时在下方继续补充。</>
            : <>已按 <span style={{ fontWeight: 600 }}>{summary}</span> 为你生成 {count} 条路线。</>
          }
        </div>
      </div>
    </div>
  );
}

// ─── Single route option card (editorial, swipeable) ──────────
// Each tone uses ONE accent dot color; the card body stays mostly black-on-
// cream so typography drives the hierarchy, not color.
const ROUTE_TONE = {
  orange: { dot: '#FF6633', soft: '#FFEEE5', kicker: '综合最优' },
  pink:   { dot: '#E91E63', soft: '#FCE4EC', kicker: '体验更强' },
  green:  { dot: '#1FAA59', soft: '#E1F4E8', kicker: '更稳妥'   },
};

function RouteOption({ route, index, total, onOpenDetail }) {
  const t = ROUTE_TONE[route.tone] || ROUTE_TONE.orange;
  const [favved, setFavved] = React.useState(false);
  const [favId, setFavId] = React.useState(null);

  const handleFav = function(e) {
    e.stopPropagation();
    if (favved) {
      if (favId) {
        window.deleteFavorite(favId).catch(function() {});
      }
      setFavved(false);
      setFavId(null);
      if (window.showToast) window.showToast('已取消收藏');
    } else {
      var poiCount = (route.pois || []).length;
      window.saveFavorite(route, route.route_name || '', route._scene || '', poiCount, route.total_time || '', route.total_avg || 0)
        .then(function(data) {
          setFavved(true);
          setFavId(data.id);
          if (window.showToast) window.showToast('已加入收藏');
        })
        .catch(function() {
          // Mock fallback — save locally
          setFavved(true);
          if (window.showToast) window.showToast('已加入收藏');
        });
    }
  };

  return (
    <article
      onClick={() => onOpenDetail(route)}
      style={{
        width: 370, flexShrink: 0, scrollSnapAlign: 'start',
        background: '#fff', borderRadius: 22,
        border: '1px solid #E8E8EA',
        padding: '24px 22px 20px',
        display: 'flex', flexDirection: 'column',
        boxShadow: '0 1px 0 rgba(0,0,0,0.02), 0 12px 30px -18px rgba(80, 50, 20, 0.18)',
        cursor: 'pointer', fontFamily: 'inherit',
        position: 'relative',
      }}
    >
      {/* Kicker — index + positioning (centered, large Dianping style) */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 10, paddingRight: 0, gap: 10,
      }}>
        <span className="num" style={{
          fontSize: 12, color: '#C7C7CC', fontWeight: 600,
        }}>
          {index + 1}/{total}
        </span>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          fontSize: 13, color: t.dot, fontWeight: 700,
          letterSpacing: 0.5,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: 999, background: t.dot }} />
          {route.positioning}
        </span>
      </div>

      {/* Title — centered WeChat style */}
      <h3 style={{
        margin: 0, fontSize: 20, fontWeight: 700,
        color: '#1a1a1a', letterSpacing: -0.3, lineHeight: 1.3,
        textAlign: 'center',
      }}>
        {route.route_name}
      </h3>

      {/* Inline stats row — centered */}
      <div style={{
        marginTop: 10, fontSize: 12.5, color: '#6E6E73',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, flexWrap: 'wrap',
        lineHeight: 1.4,
      }}>
        <span className="num">{route.total_time}</span>
        <span style={{ color: '#C8C8CC' }}>·</span>
        <span>
          <span style={{ color: '#8e8e93' }}>人均 </span>
          <span className="num" style={{ color: '#1a1a1a', fontWeight: 600 }}>¥{route.total_avg}</span>
        </span>
        <span style={{ color: '#C8C8CC' }}>·</span>
        <span className="num">{route.total_distance}</span>
      </div>

      {/* hairline divider */}
      <div style={{ height: 1, background: '#EDEDEF', margin: '18px 0 16px' }} />

      {/* POI vertical timeline */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {route.pois.map((p, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'stretch', gap: 14 }}>
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              flexShrink: 0, width: 22,
            }}>
              <span className="num" style={{
                width: 22, height: 22, borderRadius: 999,
                background: t.soft, color: t.dot,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700, flexShrink: 0,
              }}>{i + 1}</span>
              {i < route.pois.length - 1 && (
                <span style={{
                  width: 1, flex: 1, background: '#E8E2D4',
                  marginTop: 4, marginBottom: 4, minHeight: 14,
                }} />
              )}
            </div>
            <div style={{
              flex: 1, paddingTop: 2,
              paddingBottom: i < route.pois.length - 1 ? 14 : 2,
              minWidth: 0,
            }}>
              <div style={{
                fontSize: 14.5, fontWeight: 600, color: '#1a1a1a',
                lineHeight: 1.3,
              }}>{p.short}</div>
              <div style={{
                fontSize: 11.5, color: '#8e8e93', marginTop: 2,
                letterSpacing: 0.2,
              }}>{p.category}</div>
              {/* Risk tags per POI */}
              {p.riskTags && p.riskTags.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginTop: 4 }}>
                  {p.riskTags.map(function(rt) { return (
                    <span key={rt} style={{
                      background: '#FCE9E5', color: '#B43421',
                      padding: '1px 6px', borderRadius: 4,
                      fontSize: 10, fontWeight: 500,
                    }}>{rt}</span>
                  );})}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Transport */}
      <div style={{
        marginTop: 14, paddingTop: 14, borderTop: '1px dashed #E8E8EA',
        fontSize: 11.5, color: '#6E6E73', lineHeight: 1.5,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <Icon name="TrainFront" size={12} color="#8e8e93" />
        <span>{route.transport}</span>
      </div>

      {/* Reason */}
      <p style={{
        margin: '14px 0 0', fontSize: 13, color: '#1d1d1f',
        lineHeight: 1.7, textWrap: 'pretty',
      }}>{route.reason}</p>

      {/* ── Constraint Match Status ── */}
      {route.constraintMatch && (
        <div style={{
          marginTop: 14, padding: '10px 12px',
          background: '#F7F7F8', borderRadius: 10,
          border: '1px solid #EDEDEF',
        }}>
          <div style={{ fontSize: 11, color: '#8E8E93', marginBottom: 8, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Icon name="CheckCircle2" size={12} color="#8E8E93" />
            约束满足状态
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {[
              { label: '预算', value: route.constraintMatch.budget, icon: 'Wallet' },
              { label: '排队', value: route.constraintMatch.queue, icon: 'Clock' },
              { label: '营业', value: route.constraintMatch.open_time, icon: 'Store' },
              { label: '距离', value: route.constraintMatch.distance, icon: 'Footprints' },
            ].map(function(item) {
              var isOk = item.value === '符合' || item.value === '适中';
              return (
                <div key={item.label} style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  fontSize: 11.5, padding: '6px 8px',
                  background: '#fff', borderRadius: 6,
                }}>
                  <Icon name={item.icon} size={11} color={isOk ? '#1F8B4C' : '#D14600'} />
                  <span style={{ color: '#8E8E93' }}>{item.label}</span>
                  <span style={{
                    marginLeft: 'auto', fontWeight: 600,
                    color: isOk ? '#1F8B4C' : '#D14600',
                    fontSize: 11,
                  }}>{item.value}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Preference Match with Causal Explanation & Score ── */}
      {route._preferenceMatchTags && route._preferenceMatchTags.length > 0 && (
        <div style={{
          marginTop: 12, padding: '10px 12px',
          background: 'linear-gradient(135deg, #F0F7FF 0%, #F5F9FC 100%)',
          borderRadius: 10, border: '1px solid #D0E4F7',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <div style={{ fontSize: 11, color: '#2456a6', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
              <Icon name="Sparkles" size={12} color="#2456a6" />
              匹配你的历史偏好
            </div>
            {route._preferenceScore != null && (
              <span className="num" style={{
                fontSize: 12, fontWeight: 700, color: '#2456a6',
                background: '#E6EEF8', padding: '2px 8px', borderRadius: 999,
              }}>
                {route._preferenceScore} 分
              </span>
            )}
          </div>
          <div style={{ fontSize: 11.5, color: '#48484A', lineHeight: 1.5, marginBottom: 6 }}>
            因为你过去偏好「{route._preferenceMatchTags.slice(0, 3).join('、')}」{route._preferenceMatchTags.length > 3 ? '等' : ''}，这条路线优先匹配这些偏好。
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {route._preferenceMatchTags.map(function(tag) { return (
              <span key={tag} style={{
                background: '#E6EEF8', color: '#2456a6',
                padding: '2px 8px', borderRadius: 999,
                fontSize: 11, fontWeight: 500,
              }}>{tag}</span>
            );})}
          </div>
        </div>
      )}

      {/* ── UGC Review Summaries (from real user reviews) ── */}
      {route._ugcSummaries && route._ugcSummaries.length > 0 && (
        <div style={{
          marginTop: 12, padding: '10px 12px',
          background: 'linear-gradient(135deg, #FFF8F0 0%, #FFFBF6 100%)',
          borderRadius: 10, border: '1px solid #FFE4CC',
        }}>
          <div style={{ fontSize: 11, color: '#D14600', marginBottom: 8, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Icon name="MessageCircle" size={12} color="#D14600" />
            来自真实用户评价
          </div>
          {route._ugcSummaries.map(function(summary, idx) { return (
            <div key={idx} style={{
              fontSize: 11.5, color: '#6E6E73', lineHeight: 1.5,
              padding: '4px 0', borderBottom: idx < route._ugcSummaries.length - 1 ? '1px solid #F0EDE8' : 'none',
            }}>
              💬 {summary}
            </div>
          );})}
          {route._ugcMatchTags && route._ugcMatchTags.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
              <span style={{ fontSize: 10, color: '#8E8E93' }}>真实评价关键词：</span>
              {route._ugcMatchTags.map(function(tag) { return (
                <span key={tag} style={{
                  background: '#FFF1E5', color: '#D14600',
                  padding: '2px 6px', borderRadius: 999,
                  fontSize: 10, fontWeight: 500,
                }}>{tag}</span>
              );})}
            </div>
          )}
        </div>
      )}

      {/* Risks — inline, no pills */}
      {route.risks && route.risks.length > 0 && (
        <div style={{
          marginTop: 14, display: 'flex', flexDirection: 'column', gap: 6,
        }}>
          {route.risks.map((r) => (
            <div key={r} style={{
              display: 'flex', alignItems: 'flex-start', gap: 7,
              fontSize: 11.5, color: '#8a6a3a', lineHeight: 1.5,
            }}>
              <span style={{
                width: 3, height: 3, borderRadius: 999,
                background: '#C8964A', marginTop: 7, flexShrink: 0,
              }} />
              <span>{r}</span>
            </div>
          ))}
        </div>
      )}

      {/* CTA — single dark slab */}
      <button
        onClick={(e) => { e.stopPropagation(); onOpenDetail(route); }}
        style={{
          marginTop: 20,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 18px',
          background: '#FF6633', color: '#fff',
          border: 'none', borderRadius: 14,
          fontSize: 14, fontWeight: 600, letterSpacing: 0.2,
          cursor: 'pointer', fontFamily: 'inherit',
          width: '100%',
        }}
      >
        <span>查看完整路线</span>
        <Icon name="ArrowRight" size={16} color="#fff" />
      </button>
    </article>
  );
}

// ─── Multi-route output ────────────────────────────────────────
// `summaryNode` lets the caller override the default ParsingSummary banner —
// used by the NL paths (complete / assumption / conflict / followup).
// `readOnly` hides the bottom quick-adjust chip row — for history items.
function RouteOptionsCard({ scene, answers, defaulted, summaryNode, readOnly, routes: routesProp, onOpenDetail, onSwap, onChip, city, onCompare }) {
  var routes = routesProp && routesProp.length > 0
    ? routesProp
    : (window.buildRoutesForScene && window.buildRoutesForScene(scene, answers, city || window._currentCity))
    || [];
  // If still empty after all sources, show error state
  if (!routes || routes.length === 0) {
    return (
      <div style={{ padding: '40px 20px', textAlign: 'center' }}>
        <div style={{ fontSize: 36, marginBottom: 10, opacity: 0.4 }}>📡</div>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a', marginBottom: 6 }}>路线生成失败</div>
        <div style={{ fontSize: 12, color: '#8e8e93', lineHeight: 1.6 }}>
          服务暂时不可用<br/>请检查网络后返回重试
        </div>
      </div>
    );
  }
  // Stamp _scene on each route so getPlacesForRoute can find places
  // Also add default constraint_match for mock routes that don't have it
  routes = routes.map(function(r) {
    r._scene = scene;
    if (!r.constraintMatch) {
      r.constraintMatch = {
        budget: '符合',
        queue: (r.risks || []).some(function(rk) { return rk.indexOf('排队') !== -1 || rk.indexOf('等位') !== -1; }) ? '可能排队' : '符合',
        open_time: '符合',
        distance: (function() {
          var dist = (r.total_distance || '');
          if (dist.indexOf('km') !== -1) { var km = parseFloat(dist); return km > 2 ? '较远' : '适中'; }
          return '适中';
        })()
      };
    }
    return r;
  });
  const isEmergency = scene === '临时救场';
  const scrollerRef = useRefNC(null);
  const [activeIdx, setActiveIdx] = useStateNC(0);

  // Track scroll position for the pager
  useEffectNC(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const CARD_STRIDE = 370 + 12; // card width + gap
    const onScroll = () => {
      const idx = Math.round(el.scrollLeft / CARD_STRIDE);
      setActiveIdx(Math.min(routes.length - 1, Math.max(0, idx)));
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, [routes.length]);

  // Pager dot click → scroll to that card
  const scrollToIdx = (i) => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTo({ left: i * (370 + 12), behavior: 'smooth' });
  };

  return (
    <div className="fade-up" style={{ padding: '4px 0 0' }}>
      {summaryNode || <ParsingSummary scene={scene} answers={answers} defaulted={defaulted} routeCount={routes.length} />}

      {/* Section label */}
      {!readOnly && (
        <div style={{ padding: '14px 18px 14px', minWidth: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div style={{
            fontSize: 17, fontWeight: 700, color: '#1a1a1a',
            letterSpacing: -0.3, lineHeight: 1.2,
          }}>
            <span className="num">{routes.length}</span> 条路线，左右滑动选一条
          </div>
          {routes.length >= 2 && window.CompareButton && (
            <window.CompareButton routeCount={routes.length} onClick={function() { if (onCompare) onCompare(routes); }} />
          )}
        </div>
      )}
      {readOnly && <div style={{ height: 6 }} />}

      {/* Horizontal scroll-snap carousel — full-bleed, no peek */}
      <div
        ref={scrollerRef}
        className="frame-scroll"
        style={{
          display: 'flex', gap: 12, overflowX: 'auto', overflowY: 'visible',
          padding: '4px 16px 4px',
          scrollSnapType: 'x mandatory',
          scrollPaddingLeft: 16,
          scrollbarWidth: 'none',
        }}
      >
        {routes.map((r, i) => (
          <RouteOption
            key={r.id}
            route={r}
            index={i}
            total={routes.length}
            onOpenDetail={onOpenDetail}
          />
        ))}
        {/* trailing spacer so the last card lands flush */}
        <div style={{ width: 4, flexShrink: 0 }} />
      </div>

      {/* Pager dots — centered below the carousel */}
      {routes.length > 1 && (
        <div style={{
          display: 'flex', justifyContent: 'center', alignItems: 'center',
          gap: 6, padding: '14px 0 4px',
        }}>
          {routes.map((_, i) => (
            <button key={i} onClick={() => scrollToIdx(i)} style={{
              width: i === activeIdx ? 20 : 6, height: 6,
              borderRadius: 999, padding: 0,
              background: i === activeIdx ? '#FF6633' : '#C8C8CC',
              border: 'none', cursor: 'pointer',
              transition: 'width 0.3s, background 0.3s',
            }} aria-label={`Route ${i + 1}`} />
          ))}
        </div>
      )}

      {/* Emergency alts removed — integrated as full route variants above. */}

      {/* Quick-adjust chips — hidden in history mode */}
      {!readOnly && (
        <div style={{ padding: '14px 18px 4px' }}>
          <div style={{
            fontSize: 10.5, color: '#8e8e93', fontWeight: 600,
            letterSpacing: 1.2, textTransform: 'uppercase', marginBottom: 8,
          }}>
            还想调整些什么
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {['更便宜', '少走路', '不想排队', '换个口味', '更出片', '地铁优先', '更安静'].map((c) => (
              <Chip key={c} onClick={() => onChip(c)}>{c}</Chip>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

Object.assign(window, {
  SCENARIOS, ROUTE_OPTIONS, EMERGENCY_ALTS,
  SystemPromptCard, NeedCompletionCard, ParsingSummary, RouteOptionsCard,
  summarizeAnswers,
});
