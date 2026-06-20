// Natural-language branching for the chat composer path.
//
// When the user TYPES (vs taps a scenario card), we classify the input into
// one of 4 branches:
//
//   complete   — all key fields present → generate routes + parsing summary
//   assumption — core fields present, missing 1-2 → fill with defaults + banner
//   followup   — too vague → ask 1-2 key questions, then generate
//   conflict   — constraints contradict → user picks priority, then generate
//
// `analyzeNL` is a heuristic-and-keyword classifier (good enough for the
// prototype). The 4 example inputs from the spec are wired to hit their
// intended branch.

// ─── Analyzer ──────────────────────────────────────────────────
function analyzeNL(text) {
  const t = (text || '').trim();

  // 1) Conflict — strict, contradictory constraints clustered together
  const conflicts = [
    /氛围|有格调|有意境|意境感/.test(t),
    /(?:\d{2,3})\s*以?内|便宜|低价|预算少/.test(t),
    /不排队|少排队|不想等|不要等/.test(t),
    /地铁\s*\d\s*分|\d\s*分钟到地铁|地铁口/.test(t),
  ];
  if (conflicts.filter(Boolean).length >= 3) {
    return {
      branch: 'conflict',
      scene: /约会|对象|情侣/.test(t) ? '情侣约会' : '朋友聚会',
      raw: t,
      conditions: [
        { id: 'vibe',    label: '氛围感',  hint: '安静、有格调，往往人均偏高' },
        { id: 'budget',  label: '预算低',  hint: '人均 80 元内' },
        { id: 'noqueue', label: '不排队',  hint: '热门店通常需要等位' },
        { id: 'subway',  label: '离地铁近', hint: '步行 3 分钟以内' },
      ],
    };
  }

  // 2) Detect field presence
  const has = {
    scene:  detectScene(t),
    time:   /现在|马上|今天|明天|后天|本周|周[一二三四五六日末天]|下午|晚上|上午|早上|中午|傍晚|分钟[内后]|小时[内后]|下班|出发|点钟|\d+点/.test(t),
    place:  /附近|地铁|商圈|公司|家|当前|这边|那边|路上|店里|[\u4e00-\u9fa5]{2,4}(?:站|商圈|公园|大厦)|三里屯|国贸|大悦城|后海|簋街|王府井|五道口|中关村|西单|南锣鼓巷|什刹海|工体|蓝色港湾/.test(t),
    budget: /人均|预算|\d+\s*[元块]|¥|￥|以内|左右|便宜|低价|不限/.test(t),
    mood:   /吃|喝|玩|逛|拍|聊|看|展|安静|出片|热闹|放松|暖|热|凉|休息|少走|便宜|不排队|地铁|省钱|口味|换一|不吵|拍照|步行/.test(t),
  };
  const filledCount = Object.values(has).filter(Boolean).length;

  // 3) Complete — 4+ fields including the big four
  if (filledCount >= 4 && has.scene && has.time && has.place && has.budget) {
    return {
      branch: 'complete',
      scene: has.scene,
      raw: t,
      extracted: extractFields(t, has),
    };
  }

  // 4) Assumption — core present, 1-2 missing (allow missing budget or place, not both)
  if (filledCount >= 3 && has.scene && (has.time || has.place) && has.mood) {
    const missing = [];
    if (!has.budget) missing.push('预算');
    if (!has.place)  missing.push('地点');
    if (!has.time)   missing.push('时间');
    return {
      branch: 'assumption',
      scene: has.scene,
      raw: t,
      extracted: extractFields(t, has),
      assumed: defaultsFor(has.scene, missing),
    };
  }

  // 5) Followup — too vague, ask 1-2 key questions
  return {
    branch: 'followup',
    scene: has.scene, // may be null
    raw: t,
    questions: buildFollowupQuestions({ has }),
  };
}

// ─── Adjustment intent detector ─────────────────────────────────
// When the user types a short query that looks like a route adjustment
// (e.g. "少走一点路"), skip NL pipeline and treat as chip adjustment.
function detectAdjustmentIntent(text) {
  const t = (text || '').trim();
  const ADJUSTMENTS = [
    { keys: ['少走', '不想走', '走路少', '少走点', '不想走太多', '少步行', '不走路'], label: '少走路' },
    { keys: ['便宜', '省钱', '不贵', '低预算', '少花', '便宜点', '少花钱', '预算低'], label: '更便宜' },
    { keys: ['不排队', '不等', '不想等', '不等位', '不等候', '少排队', '不排'], label: '不想排队' },
    { keys: ['拍照', '出片', '好看', '上镜', '更出片', '拍出来', '适合拍照'], label: '更出片' },
    { keys: ['地铁', '公交', '公共交通', '坐地铁', '搭地铁', '地铁方便'], label: '地铁优先' },
    { keys: ['换', '换个', '换一种', '换换', '换个口味', '口味'], label: '换个口味' },
    { keys: ['安静', '清净', '不吵', '安静点', '更安静', '安静些', '不嘈杂'], label: '更安静' },
    { keys: ['快', '省时', '快点', '快速', '效率', '高效', '赶时间'], label: '更省时' },
  ];
  for (var i = 0; i < ADJUSTMENTS.length; i++) {
    var adj = ADJUSTMENTS[i];
    for (var j = 0; j < adj.keys.length; j++) {
      if (t.indexOf(adj.keys[j]) !== -1) {
        return { isAdjustment: true, chipLabel: adj.label };
      }
    }
  }
  return null;
}

function detectScene(t) {
  if (/朋友|聚会|哥们|姐妹|同事/.test(t)) return '朋友聚会';
  if (/约会|对象|情侣|男友|女友/.test(t)) return '情侣约会';
  if (/一个人|独自|自己一个|发呆|放空|放松/.test(t)) return '一个人放松';
  if (/亲子|遛娃|带娃|小孩|宝宝|孩子|带儿子|带女儿/.test(t)) return '亲子遛娃';
  if (/下班|加班完|工作日.{0,4}晚/.test(t)) return '下班回血';
  if (/救场|临时|马上要|分钟后到|分钟内/.test(t)) return '临时救场';
  return null;
}

function extractFields(t, has) {
  // Pull readable snippets for the parsing-summary line.
  const out = { time: null, place: null, budget: null, mood: null };
  const tm = t.match(/现在|马上|今天\S{0,3}|明天\S{0,3}|后天\S{0,3}|周[一二三四五六日末天]\S{0,3}|下午|晚上|上午|早上|傍晚|下班\S{0,3}|\d+\s*分钟[内后]/);
  if (tm) out.time = tm[0];
  const pm = t.match(/三里屯|国贸|后海|簋街|王府井|五道口|中关村|西单|南锣鼓巷|什刹海|工体|蓝色港湾|大悦城|当前位置附近|公司附近|地铁站附近|地铁附近|附近|商圈|[\u4e00-\u9fa5]{2,4}(?:站|商圈|公园|大厦)/);
  if (pm) out.place = pm[0];
  const bm = t.match(/人均\s*\d+\s*(?:以内|左右)?|\d+\s*[元块]\s*(?:以内|左右)?|¥\s*\d+(?:\s*以内)?|预算\S{0,4}/);
  if (bm) out.budget = bm[0].replace(/\s+/g, '');
  const moodKeywords = ['吃饭', '拍照', '聊天', '安静', '出片', '热食', '少排队', '不排队', '地铁方便', '逛', '看展', '喝一口', '热的', '暖的', '休息', '看电影', '放空'];
  const found = moodKeywords.filter((m) => t.includes(m));
  if (found.length) out.mood = found.join(' + ');
  return out;
}

function defaultsFor(scene, missingKeys) {
  const tbl = {
    '预算': scene === '下班回血' ? '普通预算' : (scene === '临时救场' ? '不限' : '人均 ¥150'),
    '地点': '当前位置附近',
    '时间': '今天',
  };
  return missingKeys.reduce((acc, k) => ({ ...acc, [k]: tbl[k] || '默认' }), {});
}

function buildFollowupQuestions({ has }) {
  const qs = [];
  if (!has.scene) {
    qs.push({
      id: 'scene',
      label: '你更想规划哪类路线？',
      options: ['朋友聚会', '情侣约会', '一个人放松', '亲子遛娃'],
    });
  }
  if (!has.place && qs.length < 2) {
    qs.push({
      id: 'place',
      label: '想在哪附近？',
      options: ['当前位置附近', '地铁站附近', '指定商圈', '输入地点'],
    });
  }
  if (qs.length === 0 && !has.time) {
    qs.push({
      id: 'time',
      label: '什么时候出发？',
      options: ['现在', '今天晚上', '周末下午', '自定义'],
    });
  }
  return qs.slice(0, 2);
}

// ─── Loading message tuned per branch ──────────────────────────
function nlLoadingText(branch) {
  switch (branch) {
    case 'complete':   return '已经理解你的需求，正在按这些条件挑路线…';
    case 'assumption': return '已经记下你说的，缺的几个我用默认值先补上，开始挑路线…';
    case 'followup':   return '收到，按你刚补充的信息为你挑路线…';
    case 'conflict':   return '按你选的优先级为你重排路线…';
    default:           return '正在结合店铺信息、真实评价和交通情况为你生成…';
  }
}

// ─── Followup card (vague NL input) ────────────────────────────
function FollowupCard({ rawText, questions, answers, onAnswer }) {
  const qIdx = questions.findIndex((q) => !answers[q.id]);
  if (qIdx === -1) return null;
  const q = questions[qIdx];
  const total = questions.length;

  // Custom-input state for "自定义" / "输入地点" options
  const [customMode, setCustomMode] = React.useState(false);
  const [customText, setCustomText] = React.useState('');
  React.useEffect(() => { setCustomMode(false); setCustomText(''); }, [qIdx]);

  const isCustomOption = (opt) =>
    opt === '自定义' || opt === '输入地点' || opt === '看心情' || opt === '不设上限' || opt === '不限';

  return (
    <AssistantMsg label="路线助手 · 还差一点">
      <div style={{
        background: '#fff', border: '1px solid #EDEDEF', borderRadius: 14,
        overflow: 'hidden', boxShadow: '0 1px 0 rgba(0,0,0,0.02)',
      }}>
        <div style={{
          padding: '12px 14px 10px',
          borderBottom: '1px solid #EDEDEF',
          background: 'linear-gradient(180deg, #FFFFFF 0%, #fff 100%)',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 4, gap: 8,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icon name="HelpCircle" size={14} color="#E94A1A" />
              <span style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a' }}>
                {total > 1 ? `还差一点，再问你 ${total} 个关键问题` : '还差一点，再问你一个问题'}
              </span>
            </div>
            {total > 1 && (
              <span className="num" style={{ fontSize: 11.5, color: '#8e8e93' }}>
                {qIdx + 1} / {total}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: '#6E6E73', lineHeight: 1.55 }}>
            「{rawText.length > 24 ? rawText.slice(0, 24) + '…' : rawText}」太宽了，补一点就能给你具体路线
          </div>
        </div>

        {total > 1 && (
          <div style={{ height: 3, background: '#EDEDEF', position: 'relative' }}>
            <div style={{
              position: 'absolute', left: 0, top: 0, bottom: 0,
              width: `${(qIdx / total) * 100}%`,
              background: '#E94A1A', transition: 'width 0.3s',
            }} />
          </div>
        )}

        <div className="fade-up" key={qIdx} style={{ padding: '14px 14px 12px' }}>
          <div style={{ fontSize: 14.5, fontWeight: 600, color: '#1a1a1a', marginBottom: 10, lineHeight: 1.4 }}>
            {q.label}
          </div>
          {!customMode && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
              {q.options.map((opt) => (
                <button key={opt} onClick={() => {
                  if (isCustomOption(opt) && (opt === '自定义' || opt === '输入地点')) {
                    setCustomMode(true);
                  } else {
                    onAnswer(q.id, opt);
                  }
                }} style={{
                  padding: '11px 12px', borderRadius: 10,
                  background: '#fff', border: '1px solid #E5E5E7',
                  fontSize: 13, fontWeight: 500, color: '#1a1a1a',
                  cursor: 'pointer', fontFamily: 'inherit',
                  textAlign: 'center', transition: 'all 0.15s',
                }}>
                  {opt}
                </button>
              ))}
            </div>
          )}

          {customMode && (
            <div style={{
              display: 'flex', gap: 8, alignItems: 'center',
            }}>
              <input
                autoFocus
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && customText.trim()) {
                    onAnswer(q.id, customText.trim());
                  }
                }}
                placeholder={
                  q.id === 'place'  ? '比如：三里屯 / 国贸 / 朝阳大悦城' :
                  q.id === 'time'   ? '比如：明天上午 10 点' :
                  q.id === 'budget' ? '比如：¥120 以内' : '输入自定义内容…'
                }
                style={{
                  flex: 1, padding: '10px 12px', fontSize: 13.5,
                  border: '1px solid #E5E5E7', borderRadius: 10,
                  outline: 'none', fontFamily: 'inherit', background: '#fff',
                  color: '#1a1a1a',
                }}
              />
              <button
                onClick={() => { if (customText.trim()) onAnswer(q.id, customText.trim()); }}
                disabled={!customText.trim()}
                style={{
                  padding: '10px 14px', fontSize: 13, fontWeight: 600,
                  background: customText.trim() ? '#E94A1A' : '#E5E5E7',
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
      </div>
    </AssistantMsg>
  );
}

// ─── Conflict card (over-constrained NL input) ─────────────────
function ConflictCard({ scene, conditions, onPickPriority }) {
  const labels = conditions.map((c) => c.label).join('、');
  return (
    <AssistantMsg label="路线助手 · 条件较严">
      <div style={{
        background: '#fff', border: '1px solid #EDEDEF', borderRadius: 14,
        overflow: 'hidden',
      }}>
        <div style={{
          padding: '13px 14px 11px',
          background: 'linear-gradient(180deg, #FFF1DE 0%, #FFFFFF 100%)',
          borderBottom: '1px solid #FFD8B8',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Icon name="AlertTriangle" size={14} color="#D14600" />
            <span style={{ fontSize: 13, fontWeight: 600, color: '#D14600' }}>
              你的条件比较严格
            </span>
          </div>
          <div style={{ fontSize: 12.5, color: '#48484A', lineHeight: 1.6 }}>
            <span style={{ color: '#D14600' }}>{labels}</span>，市面上很少能同时满足。
            你更想优先保证哪一点？我会沿着这条思路再排路线。
          </div>
        </div>
        <div style={{ padding: '12px 14px 14px' }}>
          <div style={{ fontSize: 12, color: '#8e8e93', marginBottom: 8 }}>选一个优先项</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {conditions.map((c) => (
              <button key={c.id} onClick={() => onPickPriority(c)} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                gap: 10, padding: '11px 12px', borderRadius: 10,
                background: '#F7F7F8', border: '1px solid #EDEDEF',
                cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
                width: '100%', transition: 'all 0.15s',
              }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: '#1a1a1a' }}>
                    优先 {c.label}
                  </div>
                  <div style={{ fontSize: 11.5, color: '#8e8e93', marginTop: 2, lineHeight: 1.4 }}>
                    {c.hint}
                  </div>
                </div>
                <Icon name="ChevronRight" size={15} color="#8e8e93" />
              </button>
            ))}
          </div>
        </div>
      </div>
    </AssistantMsg>
  );
}

// ─── Assumption banner (basic-complete path) ───────────────────
function AssumptionBanner({ scene, extracted, assumed }) {
  const knownParts = [scene, extracted.time, extracted.place, extracted.budget, extracted.mood].filter(Boolean);
  const assumedKeys = Object.keys(assumed || {});
  return (
    <div className="fade-up" style={{ padding: '4px 16px 0' }}>
      <div style={{
        padding: '10px 12px',
        background: '#FFF1E5', border: '1px solid #FFD8B8', borderRadius: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <Icon name="Wand2" size={13} color="#D14600" style={{ marginTop: 2, flexShrink: 0 }} />
          <div style={{ fontSize: 12, color: '#D14600', lineHeight: 1.6, flex: 1, minWidth: 0 }}>
            我先按 <span style={{ fontWeight: 600 }}>{knownParts.join(' ｜ ')}</span> 为你规划。
            {assumedKeys.length > 0 && (
              <>
                {' '}其中 <span style={{ fontWeight: 600 }}>{assumedKeys.map((k) => `${k}=${assumed[k]}`).join('、')}</span> 是我用的默认设定，你可以随时补充。
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Complete-path parsing summary (replaces ParsingSummary defaults) ──
function CompleteSummary({ scene, extracted }) {
  const parts = [scene, extracted.time, extracted.place, extracted.budget, extracted.mood].filter(Boolean);
  return (
    <div className="fade-up" style={{ padding: '4px 16px 0' }}>
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 8,
        padding: '9px 12px',
        background: '#FFF1E5', border: '1px solid #FFD8B8', borderRadius: 10,
      }}>
        <Icon name="Wand2" size={13} color="#D14600" style={{ marginTop: 2, flexShrink: 0 }} />
        <div style={{ fontSize: 12, color: '#D14600', lineHeight: 1.55, flex: 1, minWidth: 0 }}>
          已按 <span style={{ fontWeight: 600 }}>{parts.join(' ｜ ')}</span> 为你生成路线。
        </div>
      </div>
    </div>
  );
}

// ─── Conflict-path summary (after priority pick) ───────────────
function ConflictSummary({ scene, priority }) {
  if (!priority) return null;
  return (
    <div className="fade-up" style={{ padding: '4px 16px 0' }}>
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 8,
        padding: '9px 12px',
        background: '#FFF1E5', border: '1px solid #FFD8B8', borderRadius: 10,
      }}>
        <Icon name="Wand2" size={13} color="#D14600" style={{ marginTop: 2, flexShrink: 0 }} />
        <div style={{ fontSize: 12, color: '#D14600', lineHeight: 1.55, flex: 1, minWidth: 0 }}>
          已优先保证 <span style={{ fontWeight: 600 }}>{priority.label}</span>，其他条件做了一些放宽。
        </div>
      </div>
    </div>
  );
}

// ─── Followup-path summary (after follow-up answered) ──────────
function FollowupSummary({ scene, raw, answers }) {
  const ans = Object.values(answers || {}).join(' ｜ ');
  return (
    <div className="fade-up" style={{ padding: '4px 16px 0' }}>
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 8,
        padding: '9px 12px',
        background: '#FFF1E5', border: '1px solid #FFD8B8', borderRadius: 10,
      }}>
        <Icon name="Wand2" size={13} color="#D14600" style={{ marginTop: 2, flexShrink: 0 }} />
        <div style={{ fontSize: 12, color: '#D14600', lineHeight: 1.55, flex: 1, minWidth: 0 }}>
          已按「{raw.length > 16 ? raw.slice(0, 16) + '…' : raw}」+ <span style={{ fontWeight: 600 }}>{ans}</span> 为你生成路线。
        </div>
      </div>
    </div>
  );
}

// ─── Chip-adjustment summary (after tapping "更便宜" etc.) ─────
function ChipAdjustmentSummary({ chip }) {
  return (
    <div className="fade-up" style={{ padding: '4px 16px 0' }}>
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 8,
        padding: '9px 12px',
        background: '#F4EFE3', border: '1px solid #E5E5E7', borderRadius: 10,
      }}>
        <Icon name="RefreshCw" size={13} color="#48484A" style={{ marginTop: 2, flexShrink: 0 }} />
        <div style={{ fontSize: 12, color: '#48484A', lineHeight: 1.55, flex: 1, minWidth: 0 }}>
          已按 <span style={{ fontWeight: 600, color: '#1a1a1a' }}>{chip}</span> 重新挑了一组路线，原来的还在上面，可以一起看。
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  analyzeNL, detectAdjustmentIntent, nlLoadingText,
  FollowupCard, ConflictCard,
  AssumptionBanner, CompleteSummary, ConflictSummary, FollowupSummary,
  ChipAdjustmentSummary,
});
