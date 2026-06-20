// Main app — orchestrates chat state machine + page transitions, mounts iOS frame.
//
// State machine (`chatState.stage`):
//   welcome     — initial home
//   completing  — scene-tap path: SystemPromptCard + NeedCompletionCard Q&A
//   nl_followup — NL path: too vague, asking 1-2 followup questions
//   nl_conflict — NL path: constraints contradict, user picks priority
//   generating  — spinner before route output
//   route       — multi-route output (RouteOptionsCard, 1-3 routes)

const { useState: useStateApp, useEffect: useEffectApp, useLayoutEffect: useLayoutEffectApp } = React;

function PhoneStage({ children }) {
  const [scale, setScale] = useStateApp(1);
  const FRAME_W = 402, FRAME_H = 874;

  useLayoutEffectApp(() => {
    const compute = () => {
      const padding = 32;
      const availW = window.innerWidth - padding * 2;
      const availH = window.innerHeight - padding * 2;
      const s = Math.min(1, availW / FRAME_W, availH / FRAME_H);
      setScale(s);
    };
    compute();
    window.addEventListener('resize', compute);
    return () => window.removeEventListener('resize', compute);
  }, []);

  return (
    <div className="stage">
      <div style={{ width: FRAME_W * scale, height: FRAME_H * scale, position: 'relative' }}>
        <div style={{
          transformOrigin: 'top left',
          transform: `scale(${scale})`,
          width: FRAME_W, height: FRAME_H,
          position: 'absolute', top: 0, left: 0,
        }}>
          {children}
        </div>
      </div>
    </div>
  );
}

const INITIAL_STATE = {
  stage: 'welcome',
  userText: '',
  scene: null,
  answers: {},        // scene-tap or nl-followup answers
  defaulted: false,   // user tapped "先按默认推荐看看"
  nl: null,           // analyzer result {branch, extracted, assumed, questions, conditions, ...}
  conflictPriority: null,
  activeChip: null,   // chip label that drove the current generation (drives summary banner)
  routes: null,       // API response routes for RouteOptionsCard
  sessionId: null,    // backend session id
  detailRoute: null,  // selected route for detail page
  routeWarning: null,  // backend warning (budget ceiling, etc.)
  conversationMessages: [], // accumulated route-history blocks for chat-like flow
};

function App() {
  const [page, setPage] = useStateApp('chat');
  const [chatState, setChatState] = useStateApp(INITIAL_STATE);
  const [history, setHistory] = useStateApp([]);
  const [historyOpen, setHistoryOpen] = useStateApp(false);
  const [toast, setToast] = useStateApp(null);
  const [city, setCity] = useStateApp('北京');
  const [currentUser, setCurrentUser] = useStateApp(null);

  // Sync city and user to global window
  // Use safe setter that works with Object.defineProperty interception in mock-data/index.jsx
  useEffectApp(() => {
    if (typeof window._setCityDirectly === 'function') {
      window._setCityDirectly(city);
    } else {
      window._currentCity = city;
    }
  }, [city]);
  useEffectApp(() => { window._currentUserId = currentUser ? currentUser.userId : null; }, [currentUser]);

  // Auth gate: must login before using the product
  const [showLogin, setShowLogin] = useStateApp(true);
  // Expose for api.js to trigger on 401 — also resets React state properly
  useEffectApp(function() {
    window._showLogin = function() {
      // Clear stale user state so the login gate re-appears
      setCurrentUser(null);
      setAuthChecked(true);
      setShowLogin(true);
    };
    return function() { delete window._showLogin; };
  }, []);
  const [authChecked, setAuthChecked] = useStateApp(false);

  // Auth check — use cached credentials directly (synchronous, no blocking fetch).
  // Token validity is verified by backend 401 responses on actual API calls,
  // which trigger the login modal via api.js → window._showLogin().
  // This avoids blocking the UI on a slow /api/auth/me call when the backend is running.
  useEffectApp(function() {
    var authUser = null;
    var token = null;
    try {
      authUser = JSON.parse(localStorage.getItem('_authUser') || 'null');
      token = localStorage.getItem('_authToken');
    } catch(e) {}

    if (authUser && authUser.userId && token) {
      setCurrentUser(authUser);
      setShowLogin(false);
    }
    setAuthChecked(true);
  }, []);

  // ─── Conversation history with localStorage persistence (per user) ────
  const recordRef = React.useRef({ suppress: false });

  // Load user's history from localStorage on login
  useEffectApp(() => {
    var uid = currentUser && currentUser.userId;
    if (uid) {
      try {
        var key = '_chatHistory_' + uid;
        var raw = localStorage.getItem(key);
        var stored = raw ? JSON.parse(raw) : [];
        if (stored.length > 0) setHistory(stored);
      } catch(e) {}
    } else if (!currentUser) {
      setHistory([]);
    }
  }, [currentUser ? currentUser.userId : null]);

  // Persist history to localStorage when it changes
  useEffectApp(() => {
    var uid = currentUser && currentUser.userId;
    if (uid && history.length > 0) {
      try {
        var key = '_chatHistory_' + uid;
        localStorage.setItem(key, JSON.stringify(history.slice(-50)));
      } catch(e) {}
    }
  }, [history, currentUser ? currentUser.userId : null]);

  const saveConversationToHistory = (s) => {
    if (recordRef.current.suppress) {
      recordRef.current.suppress = false;
      return;
    }
    // Only save if there's meaningful conversation (has routes or messages)
    var msgs = s.conversationMessages || [];
    var hasContent = s.routes || msgs.length > 0 || s.scene;
    if (!hasContent) return;

    // Find first user message as conversation summary
    var firstUserMsg = msgs.find(function(m) { return m.type === 'user'; });
    var routeMsgs = msgs.filter(function(m) { return m.type === 'route'; });

    setHistory(function(h) {
      var entry = {
        ts: Date.now(),
        timeLabel: '刚刚',
        scene: s.scene || (firstUserMsg ? '对话' : '未指定'),
        firstQuery: firstUserMsg ? firstUserMsg.text : null,
        messageCount: msgs.length,
        turnCount: routeMsgs.length + (s.routes ? 1 : 0),
        routes: s.routes,
        sessionId: s.sessionId,
        conversationMessages: msgs,
      };
      return h.concat([entry]);
    });
  };

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 1800);
  };
  // Expose for cross-component use (FavoritesPanel, RouteOption, etc.)
  window.showToast = showToast;

  // ─── Map backend IntentAnalysisResult → frontend nl format ──
  const mapApiToNL = (result, rawText) => {
    var scene = detectSceneFromIntent(result.intent);
    var extracted = {
      time: result.intent && result.intent.startTime ? result.intent.startTime : null,
      place: result.intent && result.intent.district || null,
      budget: result.intent && result.intent.budget > 0 ? '¥' + Math.round(result.intent.budget) : null,
      mood: result.intent && result.intent.keywords ? result.intent.keywords.join(' + ') : null,
    };

    if (result.stage === 'complete') {
      return { branch: 'complete', scene: scene, raw: rawText, extracted: extracted };
    }
    if (result.stage === 'assumption') {
      var missingFields = result.missingFields || [];
      var assumed = {};
      missingFields.forEach(function(f) {
        if (f === 'budget') assumed['预算'] = '人均 ¥150';
        if (f === 'district') assumed['地点'] = '当前位置附近';
        if (f === 'preferences') assumed['偏好'] = '综合体验';
      });
      return { branch: 'assumption', scene: scene, raw: rawText, extracted: extracted, assumed: assumed };
    }
    if (result.stage === 'followup') {
      var questions = (result.followupQuestions || []).map(function(q) {
        return { id: q.id, label: q.label, options: q.options || [] };
      });
      if (questions.length === 0) {
        questions = [
          { id: 'scene', label: '你想规划哪类路线？', options: ['朋友聚会', '情侣约会', '一个人放松', '亲子遛娃'] },
          { id: 'place', label: '想在哪附近？', options: ['当前位置附近', '地铁站附近', '指定商圈', '输入地点'] },
        ];
      }
      return { branch: 'followup', scene: scene, raw: rawText, questions: questions };
    }
    if (result.stage === 'conflict') {
      var conditions = (result.conflicts || []).map(function(c) {
        return { id: c.id, label: c.label, hint: c.hint || '' };
      });
      return { branch: 'conflict', scene: scene || '朋友聚会', raw: rawText, conditions: conditions };
    }
    return { branch: 'complete', scene: scene, raw: rawText, extracted: extracted };
  };

  // Detect scene from UserIntent fields
  const detectSceneFromIntent = (intent) => {
    if (!intent) return null;
    var cats = (intent.preferredCategories || []).join(' ');
    var kw = (intent.keywords || []).join(' ');
    var sp = intent.specialRequest || '';
    var all = cats + ' ' + kw + ' ' + sp;
    if (/约会|情侣|男友|女友/.test(all)) return '情侣约会';
    if (/亲子|遛娃|带娃|小孩|宝宝/.test(all)) return '亲子遛娃';
    if (/朋友|聚会|哥们|姐妹|同事/.test(all)) return '朋友聚会';
    if (/一个人|独自|发呆|放空|放松/.test(all)) return '一个人放松';
    if (/下班|加班|回血/.test(all)) return '下班回血';
    if (/救场|临时|马上/.test(all)) return '临时救场';
    return (intent.preferredCategories || []).length > 0 ? '朋友聚会' : null;
  };

  // ─── NL path entry (composer send) — appends to conversation ──
  const handleSend = async (text) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    // Detect adjustment intent first — short queries like "少走一点路"
    const adj = window.detectAdjustmentIntent && window.detectAdjustmentIntent(trimmed);

    // Read current state snapshot for the adjustment check
    const snap = chatState;

    // ── Adjustment path: treat as chip-like adjustment ──
    if (adj && adj.isAdjustment && snap.stage === 'route' && snap.routes && snap.routes.length > 0) {
      setChatState((s) => {
        var prevMessages = (s.conversationMessages || []).concat([
          { type: 'route', scene: s.scene, answers: s.answers, defaulted: !!s.defaulted, routes: s.routes, chipLabel: s.activeChip, _key: Date.now() },
          { type: 'user', text: trimmed, _key: Date.now() + 1 },
        ]);
        var sid = s.sessionId || window.getSessionId();
        window.adjustWithFallback(sid, adj.chipLabel, s.routes, city, s.scene, s.answers).then((result) => {
          setChatState((s2) => ({
            ...s2, stage: 'route',
            routes: result.routes,
            conversationMessages: prevMessages,
            sessionId: result.sessionId || sid,
          }));
        }).catch(function(err) {
          console.error('[handleSend] adjustWithFallback error:', err);
          setChatState((s2) => ({ ...s2, stage: 'route', conversationMessages: prevMessages }));
          showToast('调整失败，请重试');
        });
        return { ...s, stage: 'generating', activeChip: adj.chipLabel, conversationMessages: prevMessages, routes: null };
      });
      return;
    }

    // ── Build conversation history ──
    var prevMessages = (snap.conversationMessages || []).slice();
    if (snap.stage === 'route' && snap.routes && snap.routes.length > 0) {
      prevMessages = prevMessages.concat([{
        type: 'route', scene: snap.scene, answers: snap.answers,
        defaulted: !!snap.defaulted, routes: snap.routes,
        chipLabel: snap.activeChip, _key: Date.now(),
      }]);
    }
    prevMessages = prevMessages.concat([{
      type: 'user', text: trimmed, _key: Date.now() + 1,
    }]);

    var sid = snap.sessionId || window.getSessionId();

    // Set generating state immediately
    setChatState((prev) => ({
      ...prev,
      stage: 'generating', userText: trimmed,
      scene: null, nl: null, answers: {},
      conversationMessages: prevMessages,
      sessionId: sid, routes: null,
      defaulted: false, conflictPriority: null, activeChip: null,
    }));

    // ── Unified smart-plan call (single HTTP round-trip) ──
    try {
    var smartResult = await window.smartPlan(trimmed, sid, city);

    // Determine effective city: LLM-detected city from query takes priority over tag
    var effectiveCity = (smartResult && smartResult.intent && smartResult.intent.city) || city;
    var knownCities = ['北京', '上海'];
    if (effectiveCity !== city && knownCities.indexOf(effectiveCity) !== -1) {
      setCity(effectiveCity);
    }

    if (smartResult && smartResult._routes && smartResult._routes.length > 0) {
      // Routes returned directly — no second API call needed
      var analysis = mapApiToNL(smartResult, trimmed);
      setChatState((s2) => ({
        ...s2, stage: 'route', scene: analysis.scene, nl: analysis,
        routes: smartResult._routes, sessionId: smartResult.sessionId || sid,
      }));
    } else if (smartResult) {
      // followup or conflict: no routes yet
      var analysis2 = mapApiToNL(smartResult, trimmed);
      if (analysis2.branch === 'followup') {
        // Store detected city in nl so followup handler can use it
        analysis2._detectedCity = effectiveCity;
        setChatState((s2) => ({ ...s2, stage: 'nl_followup', scene: analysis2.scene, nl: analysis2 }));
      } else if (analysis2.branch === 'conflict') {
        analysis2._detectedCity = effectiveCity;
        setChatState((s2) => ({ ...s2, stage: 'nl_conflict', scene: analysis2.scene, nl: analysis2 }));
      } else {
        // Unexpected stage — fall back to plan with the parsed intent
        window.planWithFallback(trimmed, analysis2.scene, {}, effectiveCity, smartResult.intent).then((result) => {
          setChatState((s2) => ({
            ...s2, stage: 'route', scene: analysis2.scene, nl: analysis2,
            routes: result.routes, sessionId: result.sessionId || sid,
          }));
        }).catch(function(err) {
          console.error('[handleSend] planWithFallback error:', err);
          setChatState((s2) => ({ ...s2, stage: 'welcome' }));
          showToast('路线生成失败，请重试');
        });
      }
    } else {
      // API unavailable — fall back to heuristic analyze + plan (two-step)
      var hAnalysis = window.analyzeNL(trimmed);
      if (hAnalysis.branch === 'complete' || hAnalysis.branch === 'assumption') {
        window.planWithFallback(trimmed, hAnalysis.scene, {}, effectiveCity).then((result) => {
          setChatState((s2) => ({
            ...s2, stage: 'route', scene: hAnalysis.scene, nl: hAnalysis,
            routes: result.routes, sessionId: result.sessionId || sid,
          }));
        }).catch(function(err) {
          console.error('[handleSend] planWithFallback error:', err);
          setChatState((s2) => ({ ...s2, stage: 'welcome' }));
          showToast('路线生成失败，请重试');
        });
      } else if (hAnalysis.branch === 'followup') {
        hAnalysis._detectedCity = effectiveCity;
        setChatState((s2) => ({ ...s2, stage: 'nl_followup', scene: hAnalysis.scene, nl: hAnalysis }));
      } else if (hAnalysis.branch === 'conflict') {
        setChatState((s2) => ({ ...s2, stage: 'nl_conflict', scene: hAnalysis.scene, nl: hAnalysis }));
      } else {
        window.planWithFallback(trimmed, hAnalysis.scene, {}, effectiveCity).then((result) => {
          setChatState((s2) => ({
            ...s2, stage: 'route', scene: hAnalysis.scene, nl: hAnalysis,
            routes: result.routes, sessionId: result.sessionId || sid,
          }));
        }).catch(function(err) {
          console.error('[handleSend] planWithFallback error:', err);
          setChatState((s2) => ({ ...s2, stage: 'welcome' }));
          showToast('路线生成失败，请重试');
        });
      }
    }
    } catch (err) {
      console.error('[handleSend] smartPlan error:', err);
      setChatState((s2) => ({ ...s2, stage: 'welcome' }));
      showToast('请求失败，请重试');
    }
  };

  // ─── NL followup: record answer, auto-generate when all done ─
  const handleNLFollowupAnswer = (qid, value) => {
    setChatState((s) => {
      const nextAnswers = { ...s.answers, [qid]: value };
      const allDone = s.nl.questions.every((q) => nextAnswers[q.id]);
      if (allDone) {
        const nextScene = nextAnswers.scene && window.SCENARIOS[nextAnswers.scene]
          ? nextAnswers.scene
          : s.scene || '朋友聚会';
        const query = window.buildQueryFromScene(nextScene, nextAnswers);
        // Use detected city from API response, fall back to state city
        var effectiveCity = (s.nl && s.nl._detectedCity) || city;
        // Append followup answers as a user message
        var prevMessages = s.conversationMessages || [];
        prevMessages = prevMessages.concat([{
          type: 'user', text: query, _key: Date.now(),
        }]);
        window.planWithFallback(query, nextScene, nextAnswers, effectiveCity).then((result) => {
          setChatState((s2) => ({ ...s2, stage: 'route', routes: result.routes, routeWarning: result.warning || null, conversationMessages: prevMessages, sessionId: result.sessionId || s2.sessionId }));
        }).catch(function(err) {
          console.error('[handleNLFollowupAnswer] planWithFallback error:', err);
          setChatState((s2) => ({ ...s2, stage: 'nl_followup' }));
          showToast('路线生成失败，请重试');
        });
        return { ...s, answers: nextAnswers, stage: 'generating', conversationMessages: prevMessages };
      }
      return { ...s, answers: nextAnswers };
    });
  };

  // ─── NL conflict: user picked their priority ─────────────────
  const handleConflictPriority = (priority) => {
    setChatState((s) => {
      const query = `${s.userText}，优先${priority.label}`;
      // Save current route block to conversation history
      var prevMessages = s.conversationMessages || [];
      if (s.stage === 'route' && s.routes && s.routes.length > 0) {
        prevMessages = prevMessages.concat([{
          type: 'route', scene: s.scene, answers: s.answers,
          defaulted: !!s.defaulted, routes: s.routes,
          chipLabel: s.activeChip, _key: Date.now(),
        }]);
      }
      // Append user choice as a user message
      prevMessages = prevMessages.concat([{
        type: 'user', text: '优先' + priority.label, _key: Date.now() + 1,
      }]);
      var effectiveCity = (s.nl && s.nl._detectedCity) || city;
      window.planWithFallback(query, s.scene || '朋友聚会', s.answers, effectiveCity).then((result) => {
        setChatState((s2) => ({ ...s2, stage: 'route', routes: result.routes, routeWarning: result.warning || null, sessionId: result.sessionId }));
      }).catch(function(err) {
        console.error('[handleConflictPriority] planWithFallback error:', err);
        setChatState((s2) => ({ ...s2, stage: 'nl_conflict' }));
        showToast('路线生成失败，请重试');
      });
      return { ...s, stage: 'generating', conflictPriority: priority, conversationMessages: prevMessages };
    });
  };

  // ─── Scene-tap entry (welcome grid) ──────────────────────────
  const handlePickScene = (scene) => {
    setChatState(function(s) {
      saveConversationToHistory(s);
      return { ...INITIAL_STATE, stage: 'completing', scene };
    });
  };

  // ─── Scene-tap: record answer, auto-generate on last one ─────
  const handleAnswer = (qid, value) => {
    setChatState((s) => {
      const nextAnswers = { ...s.answers, [qid]: value };
      const cfg = window.SCENARIOS && window.SCENARIOS[s.scene];
      const allDone = cfg && cfg.questions.every((q) => nextAnswers[q.id]);
      if (allDone) {
        const query = window.buildQueryFromScene(s.scene, nextAnswers);
        window.planWithFallback(query, s.scene, nextAnswers, city).then((result) => {
          setChatState((s2) => ({ ...s2, stage: 'route', routes: result.routes, routeWarning: result.warning || null, sessionId: result.sessionId }));
        }).catch(function(err) {
          console.error('[handleAnswer] planWithFallback error:', err);
          setChatState((s2) => ({ ...s2, stage: 'completing' }));
          showToast('路线生成失败，请重试');
        });
        return { ...s, answers: nextAnswers, stage: 'generating' };
      }
      return { ...s, answers: nextAnswers };
    });
  };

  // ─── Scene-tap: tertiary "先按默认推荐看看" ──────────────────
  const handleSkipCompletion = () => {
    setChatState((s) => {
      const query = window.buildQueryFromScene(s.scene, s.answers);
      window.planWithFallback(query, s.scene, s.answers, city).then((result) => {
        setChatState((s2) => ({ ...s2, stage: 'route', routes: result.routes, routeWarning: result.warning || null, sessionId: result.sessionId }));
      }).catch(function(err) {
        console.error('[handleSkipCompletion] planWithFallback error:', err);
        setChatState((s2) => ({ ...s2, stage: 'completing' }));
        showToast('路线生成失败，请重试');
      });
      return { ...s, stage: 'generating', defaulted: true };
    });
  };

  // ─── Tap an answered pill to revise it ───────────────────────
  const handleEditAnswer = (qid) => {
    setChatState((s) => {
      const next = { ...s.answers };
      delete next[qid];
      // Revert to the matching completing stage (scene-tap vs nl-followup)
      const stage = s.nl?.branch === 'followup' ? 'nl_followup' : 'completing';
      return { ...s, answers: next, stage };
    });
  };

  // ─── Top-of-completion "换一个" — back home ──────────────────
  const handleResetScene = () => {
    setChatState(function(s) {
      saveConversationToHistory(s);
      return INITIAL_STATE;
    });
  };

  const handleAddMore = () => showToast('请在下方继续补充你的需求');

  const handleChip = (label) => {
    setChatState((s) => {
      if (s.stage !== 'route') return s;
      const sid = s.sessionId || window.getSessionId();
      // Push current route block to conversation history before replacing
      const prevMessages = (s.conversationMessages || []).concat([{
        type: 'route',
        scene: s.scene,
        answers: s.answers,
        defaulted: s.defaulted,
        routes: s.routes,
        chipLabel: s.activeChip,
        _key: Date.now(),
      }]);
      window.adjustWithFallback(sid, label, s.routes, city, s.scene, s.answers).then((result) => {
        setChatState((s2) => ({
          ...s2, stage: 'route',
          routes: result.routes,
          conversationMessages: prevMessages,
          sessionId: result.sessionId || sid,
        }));
      }).catch(function(err) {
        console.error('[handleChip] adjustWithFallback error:', err);
        setChatState((s2) => ({ ...s2, stage: 'route', conversationMessages: prevMessages }));
        showToast('调整失败，请重试');
      });
      return { ...s, stage: 'generating', activeChip: label, conversationMessages: prevMessages };
    });
  };

  const handleOpenHistory = () => setHistoryOpen(true);
  const handleCloseHistory = () => setHistoryOpen(false);
  const handleNewConversation = () => {
    setChatState(function(s) {
      saveConversationToHistory(s);
      recordRef.current.suppress = true;
      return { ...INITIAL_STATE, conversationMessages: [] };
    });
    setHistoryOpen(false);
  };

  const handleLogout = () => {
    try { localStorage.removeItem('_authToken'); localStorage.removeItem('_authUser'); } catch(e) {}
    setCurrentUser(null);
    setShowLogin(true);
  };
  const handleReplayHistory = (idx) => {
    const entry = history[idx];
    if (!entry) return;
    recordRef.current.suppress = true;
    setHistoryOpen(false);
    // Derive NL path flag from whether there are user messages
    const msgs = entry.conversationMessages || [];
    const firstUser = msgs.find(function(m) { return m.type === 'user'; });
    setChatState({
      ...INITIAL_STATE,
      stage: 'route',
      scene: entry.scene || '朋友聚会',
      userText: firstUser ? firstUser.text : '',
      routes: entry.routes || null,
      sessionId: entry.sessionId || null,
      conversationMessages: msgs,
    });
  };

  return (
    <PhoneStage>
      <IOSDevice width={402} height={874} dark={false}>
        <div style={{
          position: 'absolute', top: 47, left: 0, right: 0, bottom: 0,
          overflow: 'hidden',
        }}>
          {/* Loading while checking auth */}
          {!authChecked && (
            <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FBFBFD' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ width: 48, height: 48, borderRadius: 16, background: '#FFF1E5', margin: '0 auto 16px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 24 }}>...</span>
                </div>
                <div style={{ fontSize: 14, color: '#8E8E93' }}>加载中...</div>
              </div>
            </div>
          )}

          {/* Login gate */}
          {authChecked && !currentUser && window.LoginModal && (
            <window.LoginModal
              open={showLogin}
              onLogin={function(user) {
                if (user) {
                  setCurrentUser(user);
                  if (user.preferredCity) setCity(user.preferredCity);
                }
                setShowLogin(false);
              }}
            />
          )}

          {/* Main app — only when authenticated */}
          {!authChecked || !currentUser ? null : (
          <div style={{ display: 'contents' }}>
          <div style={{ display: page === 'chat' ? 'block' : 'none', height: '100%' }}>
            <ChatScreen
              chatState={chatState}
              city={city}
              onCityChange={setCity}
              currentUser={currentUser}
              onUserChange={setCurrentUser}
              onLogout={handleLogout}
              onSend={handleSend}
              onPickScene={handlePickScene}
              onAnswer={handleAnswer}
              onSkipCompletion={handleSkipCompletion}
              onEditAnswer={handleEditAnswer}
              onResetScene={handleResetScene}
              onNLFollowupAnswer={handleNLFollowupAnswer}
              onConflictPriority={handleConflictPriority}
              onAddMore={handleAddMore}
              onOpenDetail={(route) => { setChatState((s) => ({ ...s, detailRoute: route })); setPage('detail'); }}
              onNav={() => showToast('已模拟跳转导航')}
              onAdjust={() => showToast('请告诉我你希望怎么调整')}
              onSwap={() => showToast('已为你换一条候选路线')}
              onChip={handleChip}
              toast={toast}
              history={history}
              historyOpen={historyOpen}
              onOpenHistory={handleOpenHistory}
              onCloseHistory={handleCloseHistory}
              onReplayHistory={handleReplayHistory}
              onNewConversation={handleNewConversation}
            />
          </div>
          <div style={{ display: page === 'detail' ? 'block' : 'none', height: '100%' }}>
            <RouteDetailScreen
              route={chatState.detailRoute}
              onBack={() => setPage('chat')}
              toast={toast}
              setToast={setToast}
            />
          </div>
          </div>)}
        </div>
      </IOSDevice>
    </PhoneStage>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
