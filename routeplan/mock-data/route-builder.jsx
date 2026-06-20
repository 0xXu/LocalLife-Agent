/**
 * 动态路线生成器 —— 从 window.ALL_PLACES（400个真实POI）按场景+答案筛选生成路线。
 * 替代 need-completion.jsx 中旧的硬编码 ROUTE_OPTIONS。
 */

(function() {

  // ─── 场景 → targetAudience 映射 ──────────────────────────────
  var SCENE_AUDIENCE = {
    '朋友聚会':   ['游客', '美食爱好者', '年轻人', '学生'],
    '情侣约会':   ['情侣', '摄影爱好者', '年轻人'],
    '一个人放松': ['文化爱好者', '学生', '老年人', '本地居民'],
    '亲子遛娃':   ['亲子', '家庭'],
    '下班回血':   ['上班族', '美食爱好者'],
    '临时救场':   null, // 不限人群
  };

  // ─── mood → 期望品类 ────────────────────────────────────────
  var MOOD_CATEGORIES = {
    '吃饭聊天':       { main: ['food'],                  tags: ['聚餐', '适合聊天', '朋友聚会', '氛围好'] },
    '吃饭 + 拍照':    { main: ['food', 'attraction'],     tags: ['出片', '拍照', '打卡', '网红'] },
    '吃饭 + 娱乐':    { main: ['food', 'attraction'],     tags: ['娱乐', '演出', '音乐', '热闹'] },
    '轻松逛逛':       { main: ['attraction'],             tags: ['逛街', '散步', '公园', '街区'] },
    '安静聊天':       { main: ['food'],                  tags: ['安静', '氛围', '私密', '适合聊天'] },
    '出片拍照':       { main: ['attraction', 'food'],     tags: ['摄影', '出片', '拍照', '打卡', '网红'] },
    '慢节奏散步':     { main: ['attraction'],             tags: ['散步', '公园', '园林', '湖边', '河畔'] },
    '看演出 / 看展':  { main: ['attraction'],             tags: ['博物馆', '展览', '演出', '艺术', '文化'] },
    '只想发呆':       { main: ['food'],                  tags: ['安静', '咖啡', '书店', '放空'] },
    '看书 / 写东西':  { main: ['food'],                  tags: ['书店', '咖啡', '安静', '图书馆'] },
    '拍照 + 散步':    { main: ['attraction', 'food'],     tags: ['拍照', '摄影', '散步', '公园'] },
    '吃点东西':       { main: ['food'],                  tags: ['简餐', '小吃', '面食'] },
    '室内乐园':       { main: ['attraction'],             tags: ['亲子', '室内', '乐园', '互动'] },
    '互动展览':       { main: ['attraction'],             tags: ['展览', '互动', '博物馆', '科学'] },
    '户外公园':       { main: ['attraction'],             tags: ['公园', '户外', '自然', '亲子'] },
    '美食 + 短玩':    { main: ['food', 'attraction'],     tags: ['美食', '公园', '亲子'] },
    '热汤面食':       { main: ['food'],                  tags: ['面食', '汤面', '暖胃', '家常'] },
    '正经一顿':       { main: ['food'],                  tags: ['正餐', '聚餐', '品质'] },
    '清淡轻食':       { main: ['food'],                  tags: ['轻食', '沙拉', '素食', '健康'] },
    '喝一口酒':       { main: ['food'],                  tags: ['酒吧', '小酌', '居酒屋', '精酿'] },
    '见朋友聊事':     { main: ['food'],                  tags: ['咖啡', '茶馆', '安静', '适合聊天'] },
    '等人 / 杀时间':  { main: ['food'],                  tags: ['咖啡', '书店', '甜品'] },
    '简单吃一口':     { main: ['food'],                  tags: ['快餐', '面食', '简餐', '小吃'] },
    '找个安静的角落': { main: ['food'],                  tags: ['咖啡', '书店', '安静', '图书馆'] },
  };

  // ─── 工具函数 ────────────────────────────────────────────────

  /** "¥150 以内" → 150；没有数字 → Infinity */
  function parseBudget(s) {
    if (!s) return Infinity;
    var m = s.match(/(\d+)/);
    return m ? parseInt(m[1], 10) : Infinity;
  }

  /** 模糊匹配：POI 的 targetAudience 是否命中期望人群之一 */
  function hitsAudience(poi, wantList) {
    if (!wantList || wantList.length === 0) return true;
    var ta = poi.targetAudience || [];
    for (var i = 0; i < wantList.length; i++) {
      var w = wantList[i];
      for (var j = 0; j < ta.length; j++) {
        if (ta[j].indexOf(w) >= 0 || w.indexOf(ta[j]) >= 0) return true;
      }
    }
    return false;
  }

  /** POI 的 tags / category / subcategory 是否命中关键词 */
  function hitsTags(poi, keywords) {
    if (!keywords || keywords.length === 0) return 0;
    var haystack = [
      poi.subcategory || '',
      poi.category || '',
      (poi.tags || []).join(' '),
    ].join(' ').toLowerCase();
    var score = 0;
    for (var i = 0; i < keywords.length; i++) {
      if (haystack.indexOf(keywords[i].toLowerCase()) >= 0) score++;
    }
    return score;
  }

  /** category 白名单匹配 */
  function hitsCategory(poi, cats) {
    if (!cats || cats.length === 0) return 0;
    var cat = (poi.category || '').toLowerCase();
    for (var i = 0; i < cats.length; i++) {
      if (cat === cats[i].toLowerCase()) return 2;
    }
    return 0;
  }

  // ─── 主入口 ──────────────────────────────────────────────────

  /**
   * buildRoutesForScene(scene, answers, city)
   *
   * @param {string} scene   — 场景名（朋友聚会 / 情侣约会 / …）
   * @param {object} answers — { time, place, budget, mood }
   * @param {string} city    — '北京' | '上海'
   * @returns {Array} 2–3 条 frontend route-option 对象
   */
  function buildRoutesForScene(scene, answers, city) {
    answers = answers || {};
    city = city || (typeof window !== 'undefined' && window._currentCity) || '北京';
    var all = Object.values(window.ALL_PLACES || {});
    if (all.length === 0) return null; // 数据未加载，调用方 fallback

    // ── 1. 按城市筛选 ──
    var pool = all.filter(function(p) {
      return (p.city || '') === city;
    });
    // 不够 3 个时扩大范围但不跨城市（改匹配条件，非放宽 city 过滤）
    if (pool.length < 3) {
      pool = all.filter(function(p) {
        var pc = p.city || '';
        return pc === city || pc === '';
      });
    }

    // ── 2. 评分 ──
    var audiences = (SCENE_AUDIENCE[scene] || null);
    var moodRule = MOOD_CATEGORIES[answers.mood] || MOOD_CATEGORIES['吃饭聊天'];
    var budget = parseBudget(answers.budget);

    var scored = pool.map(function(p) {
      var s = 0;
      if (hitsAudience(p, audiences)) s += 4;
      s += hitsTags(p, moodRule.tags) * 2;
      s += hitsCategory(p, moodRule.main);
      if (p.avg_price <= budget) s += 2; else if (p.avg_price > budget * 1.5) s -= 3;
      s += (p.rating || 0) * 0.5;
      return { poi: p, score: s };
    });

    scored.sort(function(a, b) { return b.score - a.score; });

    // ── 3. 去重品类、取候选 ──
    var seenCat = {};
    var candidates = [];
    for (var i = 0; i < scored.length && candidates.length < 12; i++) {
      var item = scored[i];
      if (item.score < 1) continue;
      var catKey = (item.poi.subcategory || item.poi.category || '其它');
      if (!seenCat[catKey]) { seenCat[catKey] = 0; }
      if (seenCat[catKey] < 2) {
        candidates.push(item.poi);
        seenCat[catKey]++;
      }
    }
    if (candidates.length < 2) {
      candidates = pool.sort(function(a, b) { return (b.rating || 0) - (a.rating || 0); }).slice(0, 8);
    }

    // ── 4. 3 条差异化路线 ──
    var routeTemplates = [
      { positioning: '综合最优',   tone: 'orange', label: '',        slice: [0, Math.min(3, candidates.length)], budgetMul: 1.0 },
      { positioning: '体验更强',   tone: 'pink',   label: ' · 体验版', slice: [1, Math.min(4, candidates.length)], budgetMul: 1.3 },
      { positioning: '更稳妥',     tone: 'green',  label: ' · 稳妥版', slice: [2, Math.min(3, candidates.length)], budgetMul: 0.8 },
    ];

    // 候选太少就只出 1–2 条
    var maxRoutes = candidates.length >= 5 ? 3 : (candidates.length >= 3 ? 2 : 1);

    var routes = [];
    for (var r = 0; r < maxRoutes; r++) {
      var tmpl = routeTemplates[r];
      var start = tmpl.slice[0] % candidates.length;
      var count = tmpl.slice[1];
      var poisForRoute = [];
      var usedNames = {};
      for (var j = 0; j < count; j++) {
        var idx = (start + j) % candidates.length;
        var cp = candidates[idx];
        if (!usedNames[cp.id]) {
          poisForRoute.push(cp);
          usedNames[cp.id] = true;
        }
      }

      var totalPrice = 0;
      poisForRoute.forEach(function(p) { totalPrice += p.avg_price || p.price || 0; });
      var avgPrice = Math.round((totalPrice / poisForRoute.length) * tmpl.budgetMul) || 120;
      var dist = (0.4 + poisForRoute.length * 0.35).toFixed(1);
      var totalMin = poisForRoute.reduce(function(s, p) {
        var d = p.duration || '2小时';
        var num = parseFloat(d);
        if (isNaN(num)) num = 2;
        if (d.indexOf('半天') >= 0) num = 4;
        if (d.indexOf('一天') >= 0) num = 8;
        return s + num;
      }, 0) * 60;

      routes.push({
        id: 'r-dyn-' + scene.replace(/[^一-龥]/g, '') + '-' + (r + 1),
        positioning: tmpl.positioning,
        tone: tmpl.tone,
        route_name: scene + '路线' + tmpl.label,
        total_time: totalMin >= 120 ? Math.round(totalMin / 60) + ' 小时' : Math.round(totalMin) + ' 分钟',
        total_avg: avgPrice,
        total_distance: dist + 'km',
        transport: '地铁可达 · 步行 5–10 分钟',
        pois: poisForRoute.map(function(p) {
          return { short: p.name, category: p.subcategory || p.category || '' };
        }),
        reason: '根据你的偏好从 ' + (city || '本地') + ' ' + candidates.length + ' 个精选POI中自动组合，综合考虑评分与距离。',
        risks: [],
      });
    }

    return routes;
  }

  window.buildRoutesForScene = buildRoutesForScene;

  console.log('[路线生成器] 已就绪，支持 6 个场景 × ' + Object.keys(MOOD_CATEGORIES).length + ' 种偏好');
})();
