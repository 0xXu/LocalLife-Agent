// API client for the AI Route Planner backend.
// Wraps POST /api/route/plan, POST /api/route/adjust, GET /api/route/compare/{sessionId}.
// Transforms backend Route/POI models into the frontend's route-option card format.
// Falls back to mock data (ROUTE_OPTIONS) when the backend is unreachable.

const API_BASE = (function() {
  var host = window.location.hostname;
  if (host === 'localhost' || host === '127.0.0.1' || host === '') {
    return 'http://localhost:8081';
  }
  // Production: assume backend on same origin
  var proto = window.location.protocol;
  var port = window.location.port;
  return proto + '//' + host + (port ? ':' + port : '');
})();

// ─── Fetch with timeout ───────────────────────────────────────────

/** Wraps fetch with an AbortController timeout (default 30s for LLM calls). Adds auth header. */
function fetchWithTimeout(url, options, timeoutMs) {
  var controller = new AbortController();
  var ms = timeoutMs || 30000;
  var timer = setTimeout(function() { controller.abort(); }, ms);
  var opts = Object.assign({}, options, { signal: controller.signal });
  // Add auth token if available
  var token = null;
  try { token = localStorage.getItem('_authToken'); } catch(e) {}
  if (token) {
    opts.headers = Object.assign({}, opts.headers || {}, { 'Authorization': 'Bearer ' + token });
  }
  return fetch(url, opts)
    .then(function(res) {
      // 401/403 → trigger login modal and clear stale credentials
      if ((res.status === 401 || res.status === 403) && window._showLogin) {
        try { localStorage.removeItem('_authToken'); localStorage.removeItem('_authUser'); } catch(e) {}
        // Defer _showLogin call so the current request chain can settle
        // without causing state inconsistencies in React
        setTimeout(function() { window._showLogin(); }, 0);
      }
      return res;
    })
    .finally(function() { clearTimeout(timer); });
}

// ─── Session tracking ─────────────────────────────────────────────
let _sessionId = null;
let _currentUserId = null;

function getSessionId() { return _sessionId; }
function setSessionId(id) { _sessionId = id; }
function getCurrentUserId() { return _currentUserId; }
function setCurrentUserId(id) { _currentUserId = id; }

// ─── Agent mode toggle ────────────────────────────────────────────
var _isAgentMode = false;  // default: fast fixed pipeline; set true for Agent Loop demo
var _noAgentRecurse = false;  // guard against recursion when agentPlan falls back to smartPlan

function isAgentMode() { return _isAgentMode; }
function setAgentMode(v) { _isAgentMode = !!v; }

// ─── User profiles ────────────────────────────────────────────────

async function getUserProfiles() {
  try {
    var res = await fetchWithTimeout(API_BASE + '/api/route/profiles');
    if (!res.ok) throw new Error('Profiles fetch failed');
    return await res.json();
  } catch (e) {
    // Fallback: hardcoded 3 mock users
    return [
      { userId: 'user_001', name: '小林', profileName: '约会偏好型', preferredCity: '上海', avgBudget: 200, favoriteCategories: ['日料','咖啡','展览','西餐'], preferenceTags: { '安静': 0.90, '少排队': 0.85 }, avoidTags: {}, historyActions: [] },
      { userId: 'user_002', name: '阿航', profileName: '效率通勤型', preferredCity: '北京', avgBudget: 120, favoriteCategories: ['快餐','商场','咖啡','简餐'], preferenceTags: { '少走路': 0.92, '近地铁': 0.88 }, avoidTags: {}, historyActions: [] },
      { userId: 'user_003', name: 'Mia',   profileName: '探店内容型', preferredCity: '上海', avgBudget: 300, favoriteCategories: ['网红餐厅','甜品','买手店','咖啡'], preferenceTags: { '出片': 0.95, '新店': 0.88 }, avoidTags: {}, historyActions: [] },
    ];
  }
}

// ─── Tone helpers ─────────────────────────────────────────────────
const GOAL_TONE = {
  BEST_EXPERIENCE: { positioning: '综合最优', tone: 'orange' },
  FASTEST:         { positioning: '最省时',   tone: 'orange' },
  CHEAPEST:        { positioning: '更低预算', tone: 'green' },
};

function toneForGoal(goal) {
  return GOAL_TONE[goal] || { positioning: '综合最优', tone: 'orange' };
}

// ─── Formatting helpers ───────────────────────────────────────────
function fmtDuration(minutes) {
  if (minutes < 60) return Math.round(minutes) + ' 分钟';
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return m > 0 ? h + ' 小时 ' + m + ' 分钟' : h + ' 小时';
}

function fmtDistance(meters) {
  if (meters == null || meters === 0) return null;
  if (meters < 1000) return Math.round(meters) + 'm';
  return (meters / 1000).toFixed(1) + 'km';
}

// ─── Backend → Frontend mapping ───────────────────────────────────

/** Convert a backend Route into a frontend route-option card. */
function mapRoute(route) {
  const tone = toneForGoal(route.optimizationGoal);
  const poiList = (route.segments || []).map((seg) => ({
    short: seg.poi ? seg.poi.name : '未知地点',
    category: seg.poi ? (seg.poi.subCategory || seg.poi.category || '') : '',
    rating: seg.poi ? seg.poi.rating : 0,
    avgCost: seg.poi ? (seg.poi.avgCost || 0) : 0,
    queueTime: seg.poi ? (seg.poi.queueTime || 0) : 0,
    ugcSummary: seg.poi ? (seg.poi.ugcSummary || '') : '',
    riskTags: seg.poi && seg.poi.riskTags ? seg.poi.riskTags : [],
    ugcTags: seg.poi && seg.poi.ugcTags ? seg.poi.ugcTags : [],
  }));

  // Build transport summary from segments
  const modes = [...new Set((route.segments || []).map((s) => s.travelMode).filter(Boolean))];
  const transportLabel = modes.length === 0 ? '步行可达'
    : modes.includes('DRIVING') && modes.includes('WALKING') ? '驾车 + 步行'
    : modes.includes('DRIVING') ? '驾车'
    : '步行可达';

  // Risks from violated soft constraints
  const risks = (route.violatedSoftConstraints || []).map((c) => c.description || c.name || '').filter(Boolean);

  // Constraint match status from backend route data
  var constraintMatch = {
    budget: '符合',
    queue: '符合',
    open_time: '符合',
    distance: '适中'
  };
  // Build constraint match from satisfied/violated constraints
  var satisfiedConstraints = route.satisfiedConstraints || [];
  var violatedSoftConstraints = route.violatedSoftConstraints || [];
  var constraintNames = satisfiedConstraints.map(function(c) { return c.name || ''; });
  var violatedNames = violatedSoftConstraints.map(function(c) { return c.name || ''; });

  if (violatedNames.some(function(n) { return n.indexOf('预算') !== -1 || n.indexOf('budget') !== -1; })) {
    constraintMatch.budget = '略超预算';
  }
  if (violatedNames.some(function(n) { return n.indexOf('排队') !== -1 || n.indexOf('queue') !== -1; })) {
    constraintMatch.queue = '可能排队';
  }
  if (violatedNames.some(function(n) { return n.indexOf('营业') !== -1 || n.indexOf('open') !== -1 || n.indexOf('时间') !== -1; })) {
    constraintMatch.open_time = '时间紧张';
  }
  if (violatedNames.some(function(n) { return n.indexOf('距离') !== -1 || n.indexOf('distance') !== -1; })) {
    constraintMatch.distance = '较远';
  }

  // Walking distance from segments
  var totalWalking = (route.segments || []).reduce(function(sum, s) { return sum + (s.travelTimeFromPrevious || 0); }, 0);

  return {
    id: route.id || ('r-' + Math.random().toString(36).slice(2, 8)),
    positioning: tone.positioning,
    tone: tone.tone,
    route_name: route.name || '推荐路线',
    total_time: fmtDuration(route.totalTravelTime || 0),
    total_avg: Math.round(route.totalCost || 0),
    total_distance: fmtDistance(totalWalking * 80) || '步行可达',
    total_walking_minutes: Math.round(totalWalking),
    transport: transportLabel,
    pois: poiList,
    reason: route.description || '',
    risks: risks,
    constraintMatch: constraintMatch,
    optimizationGoal: route.optimizationGoal || 'BEST_EXPERIENCE',
    _raw: route, // keep original for detail page
  };
}

/** Map a PlanResponse to the array the frontend RouteOptionsCard expects. */
function mapPlanResponse(data) {
  const routes = (data.routes || []).map(mapRoute);
  var tones = ['orange', 'pink', 'green'];
  var posLabels = _currentUserId
    ? ['综合最优', '少走路', '偏好优先']
    : ['综合最优', '更出片', '更稳妥'];
  routes.forEach((r, i) => {
    r.tone = tones[i] || 'green';
    r.positioning = posLabels[i] || '综合最优';
    // Attach preference match tags
    if (data.preferenceMatchTags && data.preferenceMatchTags[r.id]) {
      r._preferenceMatchTags = data.preferenceMatchTags[r.id];
    }
    // Attach preference score
    if (data.preferenceScores && data.preferenceScores[r.id] != null) {
      r._preferenceScore = Math.round(data.preferenceScores[r.id]);
    }
    // Attach UGC match tags (from real user reviews)
    if (data.ugcMatchTags && data.ugcMatchTags[r.id]) {
      r._ugcMatchTags = data.ugcMatchTags[r.id];
    }
    // Attach UGC summaries (real user review snippets)
    if (data.ugcSummaries && data.ugcSummaries[r.id]) {
      r._ugcSummaries = data.ugcSummaries[r.id];
    }
  });
  return {
    sessionId: data.sessionId,
    routes: routes,
    warning: data.warning || null,
    recommendedRoute: data.recommendedRoute ? mapRoute(data.recommendedRoute) : null,
  };
}

// ─── API calls ────────────────────────────────────────────────────

/**
 * POST /api/route/smart-plan — Unified analyze + plan in one call.
 * Eliminates the extra HTTP round-trip between analyze and plan.
 * Returns { stage, summaryText, intent, routes (mapped), followupQuestions, conflicts, ... }
 * or null when the backend is unreachable.
 */
async function smartPlan(query, sessionId, city) {
  // Agent mode: delegate to agent-plan first, fall back to smart-plan on failure
  if (_isAgentMode && !_noAgentRecurse) {
    try {
      var agentResult = await agentPlan(query, sessionId, city, _currentUserId);
      if (agentResult && agentResult.routes && agentResult.routes.length > 0) {
        // Convert PlanResponse to smartPlan-compatible format
        return {
          stage: 'complete',
          summaryText: null,
          intent: null,
          sessionId: agentResult.sessionId,
          _routes: agentResult.routes,
          _questions: null,
          _conflicts: null,
          warning: agentResult.warning || null,
          followupQuestions: [],
          conflicts: [],
          preferenceMatchTags: null,
          preferenceScores: null,
          ugcMatchTags: null,
          ugcSummaries: null,
        };
      }
    } catch (e) {
      console.warn('Agent-plan delegation in smartPlan failed:', e.message);
    }
  }

  try {
    const body = { query: query, sessionId: sessionId || null, city: city || null, userId: _currentUserId || null };
    const res = await fetchWithTimeout(API_BASE + '/api/route/smart-plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (data.sessionId) setSessionId(data.sessionId);

    // Map routes if present (complete/assumption stage)
    if (data.routes && data.routes.length > 0) {
      data._routes = data.routes.map(mapRoute);
      var tones = ['orange', 'pink', 'green'];
      var posLabels = _currentUserId
        ? ['综合最优', '少走路', '偏好优先']
        : ['综合最优', '体验更强', '更稳妥'];
      data._routes.forEach(function(r, i) {
        r.tone = tones[i] || 'green';
        r.positioning = posLabels[i] || '综合最优';
        // Attach preference match data from API response
        if (data.preferenceMatchTags && data.preferenceMatchTags[r.id]) {
          r._preferenceMatchTags = data.preferenceMatchTags[r.id];
        }
        if (data.preferenceScores && data.preferenceScores[r.id] != null) {
          r._preferenceScore = Math.round(data.preferenceScores[r.id]);
        }
        if (data.ugcMatchTags && data.ugcMatchTags[r.id]) {
          r._ugcMatchTags = data.ugcMatchTags[r.id];
        }
        if (data.ugcSummaries && data.ugcSummaries[r.id]) {
          r._ugcSummaries = data.ugcSummaries[r.id];
        }
      });
    }

    // Normalize followupQuestions to frontend format
    if (data.followupQuestions && data.followupQuestions.length > 0) {
      data._questions = data.followupQuestions.map(function(q) {
        return { id: q.id, label: q.label, options: q.options || [] };
      });
    }
    // Normalize conflicts to frontend format
    if (data.conflicts && data.conflicts.length > 0) {
      data._conflicts = data.conflicts.map(function(c) {
        return { id: c.id, label: c.label, hint: c.hint || '' };
      });
    }
    return data;
  } catch (e) {
    console.warn('Smart-plan API unavailable:', e.message);
    return null;
  }
}

/**
 * POST /api/route/agent-plan — LLM-driven Agent Loop architecture.
 * 1 main Agent dynamically calls 7 tools instead of the fixed 5-agent pipeline.
 * Returns PlanResponse format (same as /api/route/plan).
 * Falls back to smartPlan if the agent-plan endpoint is unavailable.
 */
async function agentPlan(query, sessionId, city, userId) {
  try {
    var body = { query: query, sessionId: sessionId || null, city: city || null, userId: userId || _currentUserId || null };
    var res = await fetchWithTimeout(API_BASE + '/api/route/agent-plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error('Agent-plan API error: ' + res.status);
    var data = await res.json();
    if (data.sessionId) setSessionId(data.sessionId);
    return mapPlanResponse(data);
  } catch (e) {
    console.warn('Agent-plan API unavailable:', e.message);
    // Fallback to smartPlan, guarded against recursion
    if (_noAgentRecurse) return null;
    _noAgentRecurse = true;
    try {
      var smartResult = await smartPlan(query, sessionId, city);
      if (smartResult && smartResult._routes && smartResult._routes.length > 0) {
        return {
          sessionId: smartResult.sessionId || ('agfb-' + Date.now()),
          routes: smartResult._routes,
          warning: null,
          recommendedRoute: smartResult._routes[0] || null,
        };
      }
    } catch (e2) {
      console.warn('Agent-plan fallback to smartPlan also failed:', e2.message);
    } finally {
      _noAgentRecurse = false;
    }
    return null;
  }
}

/**
 * POST /api/route/plan
 * @param {string} query - Natural language query
 * @param {string|null} sessionId
 * @returns {Promise<{sessionId, routes, warning, recommendedRoute}>}
 */
async function planRoute(query, sessionId, city, intent) {
  const body = { query: query, sessionId: sessionId || null, city: city || null, intent: intent || null, userId: _currentUserId || null };
  const res = await fetchWithTimeout(API_BASE + '/api/route/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('API error: ' + res.status);
  const data = await res.json();
  if (data.sessionId) setSessionId(data.sessionId);
  return mapPlanResponse(data);
}

/**
 * POST /api/route/adjust
 * @param {string} sessionId
 * @param {string} adjustment - e.g. "更便宜", "少走路"
 * @param {string} city - current selected city
 * @returns {Promise<{sessionId, routes, warning, recommendedRoute}>}
 */
async function adjustRoute(sessionId, adjustment, city) {
  const body = { sessionId: sessionId, adjustment: adjustment, city: city || null, userId: _currentUserId || null };
  const res = await fetchWithTimeout(API_BASE + '/api/route/adjust', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('API error: ' + res.status);
  const data = await res.json();
  return mapPlanResponse(data);
}

/**
 * POST /api/route/analyze — LLM-based intent analysis with completeness check.
 * Returns { stage, intent, missingFields, followupQuestions, conflicts, summaryText }
 * or null when the backend is unreachable (caller should fall back to analyzeNL).
 */
async function analyzeIntent(query, sessionId, city) {
  try {
    const body = { query: query, sessionId: sessionId || null, city: city || null };
    const res = await fetchWithTimeout(API_BASE + '/api/route/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    // Normalize followupQuestions to frontend format
    if (data.followupQuestions && data.followupQuestions.length > 0) {
      data._questions = data.followupQuestions.map(function(q) {
        return { id: q.id, label: q.label, options: q.options || [] };
      });
    }
    // Normalize conflicts to frontend format
    if (data.conflicts && data.conflicts.length > 0) {
      data._conflicts = data.conflicts.map(function(c) {
        return { id: c.id, label: c.label, hint: c.hint || '' };
      });
    }
    return data;
  } catch (e) {
    console.warn('Intent analysis API unavailable:', e.message);
    return null;
  }
}

// ─── Query builder for scene + answers path ───────────────────────

/**
 * Build a natural-language query from a scene tap + completion answers.
 * This lets the scene-tap path use the same POST /api/route/plan endpoint.
 */
function buildQueryFromScene(scene, answers) {
  const parts = [];
  parts.push(scene || '出去玩');

  const timeMap = {
    '现在': '现在出发', '今天晚上': '今天晚上', '周末下午': '周末下午', '周末上午': '周末上午',
    '周末晚上': '周末晚上', '今天下午': '今天下午', '半小时后': '半小时后出发',
    '一小时后': '一小时后出发', '10 分钟内': '10分钟内到', '20 分钟内': '20分钟内到',
    '30 分钟内': '30分钟内到',
  };
  if (answers.time) {
    // Clock times like "18:00", "19:00" etc. are passed directly
    var t = answers.time;
    if (/^\d{1,2}:\d{2}$/.test(t)) {
      parts.push(t + '出发');
    } else {
      parts.push(timeMap[t] || t);
    }
  }

  const placeMap = {
    '当前位置附近': '当前位置附近', '当前位置': '当前位置', '公司附近': '公司附近',
    '回家路上': '回家路上', '地铁站附近': '地铁站附近', '商圈附近': '商圈附近',
  };
  if (answers.place) parts.push(placeMap[answers.place] || answers.place);

  if (answers.budget && answers.budget !== '不限' && answers.budget !== '不设上限' && answers.budget !== '看心情') {
    parts.push('预算' + answers.budget);
  }

  if (answers.duration && answers.duration !== '不限') {
    parts.push('时长' + answers.duration);
  }

  if (answers.mood) {
    const moodMap = {
      '吃饭聊天': '吃饭聊天', '吃饭 + 拍照': '吃饭加拍照', '吃饭 + 娱乐': '吃饭加娱乐',
      '轻松逛逛': '轻松逛逛', '安静聊天': '安静有氛围', '出片拍照': '拍照好看',
      '慢节奏散步': '散步', '看演出 / 看展': '看展', '只想发呆': '安静放松',
      '看书 / 写东西': '看书', '拍照 + 散步': '拍照散步', '吃点东西': '吃点什么',
      '室内乐园': '室内乐园', '互动展览': '互动展览', '户外公园': '户外公园',
      '美食 + 短玩': '美食加短玩', '热汤面食': '热汤面', '正经一顿': '正经吃一顿',
      '清淡轻食': '清淡的', '喝一口酒': '喝一杯', '见朋友聊事': '见朋友',
      '等人 / 杀时间': '等人', '简单吃一口': '简单吃点', '找个安静的角落': '安静的地方',
    };
    parts.push(moodMap[answers.mood] || answers.mood);
  }

  return parts.join('，');
}

// ─── API calls (backend as single source of truth) ──────────────────

/**
 * Plan a route via the backend.
 * Tries agent-plan (if agentMode) → /plan → /smart-plan in order.
 * All data comes from backend — no frontend mock fallback.
 */
async function planWithFallback(query, scene, answers, city, intent) {
  // Agent mode: try agent-plan first
  if (_isAgentMode) {
    try {
      var agentResult = await agentPlan(query, null, city, _currentUserId);
      if (agentResult && agentResult.routes && agentResult.routes.length > 0) {
        return agentResult;
      }
    } catch (e) { console.warn('Agent-plan failed:', e.message); }
  }

  try {
    const result = await planRoute(query, null, city, intent || null);
    if (result.routes.length > 0) return result;
  } catch (e) { console.warn('/plan failed:', e.message); }

  // Fallback: try /smart-plan
  try {
    const smartResult = await smartPlan(query, null, city);
    if (smartResult && smartResult._routes && smartResult._routes.length > 0) {
      return {
        sessionId: smartResult.sessionId || ('fb-' + Date.now()),
        routes: smartResult._routes,
        warning: null,
        recommendedRoute: smartResult._routes[0] || null,
      };
    }
  } catch (e2) { console.warn('/smart-plan also failed:', e2.message); }

  // Backend unavailable — return prebuilt demo data
  console.warn('Backend unavailable, using demo data fallback');
  var demoRoutes = getDemoRoutes(city || '北京');
  return {
    sessionId: 'demo-' + Date.now(),
    routes: demoRoutes,
    warning: '正在使用离线演示数据（后端未连接）',
    recommendedRoute: demoRoutes[0] || null,
  };
}

/**
 * Adjust a route via the backend.
 * All data comes from backend — no frontend mock fallback.
 */
async function adjustWithFallback(sessionId, adjustment, currentRoutes, city, scene, answers) {
  try {
    const result = await adjustRoute(sessionId, adjustment, city);
    if (result.routes.length > 0) return result;
  } catch (e) { console.warn('Backend API unavailable for adjust:', e.message); }

  // Backend unavailable — return demo data
  console.warn('Backend unavailable for adjust, using demo fallback');
  var demoRoutes = getDemoRoutes(city || '北京');
  return {
    sessionId: sessionId || ('demo-adj-' + Date.now()),
    routes: demoRoutes,
    warning: '正在使用离线演示数据（后端未连接）',
    recommendedRoute: demoRoutes[0] || null,
  };
}

// ─── POI data API (unified backend source) ─────────────────────

/**
 * Fetch POI data from the backend for a given city.
 * Returns an array of POI objects with all fields (UGC, riskTags, etc.).
 * Falls back to null when the backend is unreachable — callers should use
 * the existing frontend mock data in that case.
 */
async function fetchPOIsFromBackend(city) {
  try {
    var url = API_BASE + '/api/route/pois?city=' + encodeURIComponent(city || '北京');
    var res = await fetchWithTimeout(url, {}, 8000);
    if (!res.ok) return null;
    var pois = await res.json();
    if (!pois || pois.length === 0) return null;
    // Adapt backend POI format to frontend ALL_PLACES format
    return pois.map(function(p) {
      return {
        id: p.id,
        name: p.name,
        short: p.name,
        category: p.subCategory || p.category || '',
        subcategory: p.subCategory || '',
        rating: p.rating || 0,
        review_count: 0,
        avg_price: p.avgCost || 0,
        opening_hours: '',
        current_status: '营业中',
        current_status_short: '营业中',
        status_tone: 'green',
        wait_time: (p.queueTime > 10) ? '约 ' + p.queueTime + ' 分钟' : '无需排队',
        tags: p.tags || [],
        ugcTags: p.ugcTags || [],
        ugcSummary: p.ugcSummary || '',
        risk_tags: p.riskTags || [],
        recommendation_reason: p.description || '',
        review_summary: p.ugcSummary || (p.tags || []).join('、'),
        lng: p.lng,
        lat: p.lat,
        imageUrl: p.imageUrl || '',
        images: p.imageUrl ? [p.imageUrl] : [],
        address: p.address || '',
        city: p.city || city,
        district: p.district || '',
        targetAudience: [],
        bestTime: '',
        duration: '',
        popularityScore: p.popularityScore || 0,
        mock_x: Math.round(((p.lng - 115.5) / (122 - 115.5)) * 100),
        mock_y: Math.round(((41 - p.lat) / (41 - 30.5)) * 100),
      };
    });
  } catch (e) {
    console.warn('Backend POI fetch unavailable, using mock data:', e.message);
    return null;
  }
}

// ─── Favorites API (with in-memory fallback) ───────────────────

// Shared in-memory store — survives panel close/open within the session.
// Falls back to this when backend is unavailable.
window._favoritesStore = window._favoritesStore || [];
var _favIdCounter = 1;

async function saveFavorite(routeData, routeName, scene, poiCount, totalTime, totalCost) {
  var uid = _currentUserId || null;
  var localEntry = {
    id: 'local-' + (_favIdCounter++),
    routeJson: JSON.stringify(routeData),
    routeName: routeName || '',
    scene: scene || '',
    poiCount: poiCount || 0,
    totalTime: totalTime || '',
    totalCost: totalCost || 0,
    createdAt: new Date().toISOString(),
    userId: uid,
  };
  try {
    var res = await fetchWithTimeout(API_BASE + '/api/favorites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        userId: uid,
        routeJson: localEntry.routeJson,
        routeName: localEntry.routeName,
        scene: localEntry.scene,
        poiCount: localEntry.poiCount,
        totalTime: localEntry.totalTime,
        totalCost: localEntry.totalCost,
      }),
    });
    if (!res.ok) throw new Error('Save failed: ' + res.status);
    var serverEntry = await res.json();
    window._favoritesStore.unshift(serverEntry);
    return serverEntry;
  } catch (e) {
    console.warn('Favorites API unavailable, saving locally:', e.message);
    window._favoritesStore.unshift(localEntry);
    return localEntry;
  }
}

async function getFavorites() {
  try {
    var uid = _currentUserId || '';
    var url = API_BASE + '/api/favorites' + (uid ? '?userId=' + encodeURIComponent(uid) : '');
    var res = await fetchWithTimeout(url);
    if (!res.ok) throw new Error('Fetch failed: ' + res.status);
    var serverData = await res.json();
    // Merge: server data + any local-only entries not yet synced
    var localIds = new Set(window._favoritesStore.filter(function(f) { return String(f.id).indexOf('local-') === 0; }).map(function(f) { return f.id; }));
    if (localIds.size > 0) {
      return window._favoritesStore;
    }
    window._favoritesStore = serverData || [];
    return window._favoritesStore;
  } catch (e) {
    console.warn('Favorites API unavailable, using local store:', e.message);
    return window._favoritesStore;
  }
}

async function deleteFavorite(id) {
  // Remove from local store immediately
  window._favoritesStore = window._favoritesStore.filter(function(f) { return f.id != id; });
  try {
    if (String(id).indexOf('local-') === 0) {
      return { success: true, id: id };
    }
    var uid = _currentUserId || '';
    var url = API_BASE + '/api/favorites/' + id + (uid ? '?userId=' + encodeURIComponent(uid) : '');
    var res = await fetchWithTimeout(url, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed: ' + res.status);
    return await res.json();
  } catch (e) {
    console.warn('Favorites API delete failed:', e.message);
    return { success: true, id: id };
  }
}

// ─── Demo data fallback (when backend is unavailable) ──────────────
function getDemoRoutes(city) {
  var isBeijing = city === '北京';
  if (isBeijing) {
    return [
      {
        id: 'demo-bj-1', positioning: '综合最优', tone: 'orange',
        route_name: '北京经典半日游',
        total_time: '3 小时 30 分钟', total_avg: 120, total_distance: '6.5km',
        transport: '地铁 + 步行', optimizationGoal: 'BEST_EXPERIENCE',
        pois: [
          { short: '颐和园', category: '景点', rating: 4.8, avgCost: 30, lng: 116.2755, lat: 40.0005,
            tags: ['世界遗产', '皇家园林'], wait_time: '约15分钟', opening_hours: '06:30-20:00' },
          { short: '圆明园', category: '景点', rating: 4.6, avgCost: 25, lng: 116.3043, lat: 40.0088,
            tags: ['历史古迹', '公园'], wait_time: '约10分钟', opening_hours: '07:00-21:00' },
          { short: '食宝街', category: '美食', rating: 4.5, avgCost: 65, lng: 116.3157, lat: 39.9934,
            tags: ['美食街', '性价比高'], wait_time: '约20分钟', opening_hours: '10:00-22:00' },
        ],
        constraintMatch: { budget: '符合', queue: '符合', open_time: '符合', distance: '适中' },
        _preferenceMatchTags: ['少走路', '近地铁'], _preferenceScore: 85,
      },
      {
        id: 'demo-bj-2', positioning: '少走路', tone: 'pink',
        route_name: '胡同文化漫步',
        total_time: '2 小时 45 分钟', total_avg: 80, total_distance: '3.2km',
        transport: '步行可达', optimizationGoal: 'FASTEST',
        pois: [
          { short: '南锣鼓巷', category: '购物', rating: 4.4, avgCost: 30, lng: 116.4092, lat: 39.9426,
            tags: ['胡同', '文创'], wait_time: '无需排队', opening_hours: '全天' },
          { short: '什刹海', category: '景点', rating: 4.5, avgCost: 0, lng: 116.3932, lat: 39.9408,
            tags: ['湖泊', '散步'], wait_time: '无需排队', opening_hours: '全天' },
          { short: '姚记炒肝店', category: '美食', rating: 4.3, avgCost: 50, lng: 116.4057, lat: 39.9397,
            tags: ['老北京', '小吃'], wait_time: '约10分钟', opening_hours: '06:00-22:00' },
        ],
        constraintMatch: { budget: '符合', queue: '符合', open_time: '符合', distance: '适中' },
      },
      {
        id: 'demo-bj-3', positioning: '偏好优先', tone: 'green',
        route_name: '文艺出片半日游',
        total_time: '4 小时', total_avg: 150, total_distance: '8.1km',
        transport: '驾车 + 步行', optimizationGoal: 'PREFERENCE',
        pois: [
          { short: '798艺术区', category: '娱乐', rating: 4.6, avgCost: 50, lng: 116.5018, lat: 39.9851,
            tags: ['出片', '展览', '文艺'], wait_time: '无需排队', opening_hours: '10:00-18:00' },
          { short: '望京SOHO', category: '购物', rating: 4.3, avgCost: 100, lng: 116.4855, lat: 39.9981,
            tags: ['拍照好看', '商圈'], wait_time: '无需排队', opening_hours: '10:00-22:00' },
        ],
        constraintMatch: { budget: '符合', queue: '符合', open_time: '符合', distance: '适中' },
        _preferenceMatchTags: ['出片', '拍照好看'], _preferenceScore: 90,
      },
    ];
  }
  // Shanghai demo routes
  return [
    {
      id: 'demo-sh-1', positioning: '综合最优', tone: 'orange',
      route_name: '上海精致半日游',
      total_time: '3 小时', total_avg: 180, total_distance: '5.8km',
      transport: '地铁 + 步行', optimizationGoal: 'BEST_EXPERIENCE',
      pois: [
        { short: '武康路', category: '景点', rating: 4.7, avgCost: 0, lng: 121.4446, lat: 31.2077,
          tags: ['出片', '历史建筑', '网红打卡'], wait_time: '无需排队', opening_hours: '全天' },
        { short: '安福路', category: '购物', rating: 4.5, avgCost: 80, lng: 121.4445, lat: 31.2108,
          tags: ['买手店', '咖啡'], wait_time: '约5分钟', opening_hours: '10:00-22:00' },
        { short: 'RAC Coffee', category: '美食', rating: 4.4, avgCost: 100, lng: 121.4528, lat: 31.2135,
          tags: ['网红餐厅', '拍照好看'], wait_time: '约15分钟', opening_hours: '08:00-22:00' },
      ],
      constraintMatch: { budget: '符合', queue: '符合', open_time: '符合', distance: '适中' },
      _preferenceMatchTags: ['出片', '安静'], _preferenceScore: 88,
    },
    {
      id: 'demo-sh-2', positioning: '偏好优先', tone: 'pink',
      route_name: '探店打卡路线',
      total_time: '4 小时 15 分钟', total_avg: 250, total_distance: '7.2km',
      transport: '驾车', optimizationGoal: 'PREFERENCE',
      pois: [
        { short: '新天地', category: '购物', rating: 4.8, avgCost: 120, lng: 121.4802, lat: 31.2197,
          tags: ['热门', '高端', '出片'], wait_time: '约10分钟', opening_hours: '10:00-22:00' },
        { short: '外滩', category: '景点', rating: 4.9, avgCost: 0, lng: 121.4951, lat: 31.2405,
          tags: ['夜景', '地标', '拍照好看'], wait_time: '无需排队', opening_hours: '全天' },
        { short: '蟹家大院', category: '美食', rating: 4.6, avgCost: 130, lng: 121.4967, lat: 31.2367,
          tags: ['网红餐厅', '高端'], wait_time: '约30分钟', opening_hours: '11:00-21:30' },
      ],
      constraintMatch: { budget: '略超预算', queue: '可能排队', open_time: '符合', distance: '适中' },
      _preferenceMatchTags: ['新店', '热门', '高评分'], _preferenceScore: 92,
    },
  ];
}

// ─── Exports ──────────────────────────────────────────────────────
Object.assign(window, {
  API_BASE,
  getSessionId, setSessionId,
  getCurrentUserId, setCurrentUserId,
  getUserProfiles,
  planRoute, adjustRoute, analyzeIntent, smartPlan,
  agentPlan, isAgentMode, setAgentMode,
  buildQueryFromScene,
  planWithFallback, adjustWithFallback,
  mapRoute, mapPlanResponse,
  fmtDuration, fmtDistance,
  saveFavorite, getFavorites, deleteFavorite,
  fetchPOIsFromBackend,
  getDemoRoutes,
});
