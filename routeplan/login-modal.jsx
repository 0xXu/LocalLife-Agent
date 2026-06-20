// Login / Register gate — mandatory auth before product access.
// Features 3 user personas for quick selection: 小林(约会), 阿航(效率), Mia(探店).
// Stores JWT token + user info in localStorage.

const { useState: useStateLogin, useEffect: useEffectLogin } = React;

const AVATAR_COLORS = [
  { bg: '#FDE8E8', fg: '#C53030' },
  { bg: '#E8F4E8', fg: '#2F855A' },
  { bg: '#FEF3E2', fg: '#C05621' },
  { bg: '#E8EAF6', fg: '#3F51B5' },
  { bg: '#F3E5F5', fg: '#7B1FA2' },
  { bg: '#E0F2F1', fg: '#00695C' },
];

// 3 built-in user personas — matched to backend seed data
const PERSONAS = [
  {
    userId: 'user_001',
    name: '小林',
    personaName: '约会偏好型',
    city: '上海',
    password: '1234',
    avatarBg: '#FDE8E8', avatarFg: '#C53030',
    label: '约会',
    description: '喜欢安静、出片的约会路线，预算中等偏上，日料和咖啡爱好者',
    budget: 200,
    tags: ['安静', '少排队', '拍照好看', '适合约会', '日料'],
    icon: 'Heart',
  },
  {
    userId: 'user_002',
    name: '阿航',
    personaName: '效率通勤型',
    city: '北京',
    password: '1234',
    avatarBg: '#E8F4E8', avatarFg: '#2F855A',
    label: '效率',
    description: '追求高效、少走路的路线，近地铁优先，性价比导向',
    budget: 120,
    tags: ['少走路', '近地铁', '不用排队', '省时', '性价比'],
    icon: 'Zap',
  },
  {
    userId: 'user_003',
    name: 'Mia',
    personaName: '探店内容型',
    city: '上海',
    password: '1234',
    avatarBg: '#FEF3E2', avatarFg: '#C05621',
    label: '探店',
    description: '追逐新店、热门打卡地，注重出片和评分，预算宽裕',
    budget: 300,
    tags: ['出片', '新店', '热门', '高评分', '拍照好看'],
    icon: 'Camera',
  },
];

function LoginModal({ open, onLogin }) {
  const [mode, setMode] = useStateLogin('login');
  const [name, setName] = useStateLogin('');
  const [password, setPassword] = useStateLogin('');
  const [city, setCity] = useStateLogin('北京');
  const [selectedPersona, setSelectedPersona] = useStateLogin(null); // persona index or null
  const [avatarIdx, setAvatarIdx] = useStateLogin(0);
  const [cityPickerOpen, setCityPickerOpen] = useStateLogin(false);
  const [error, setError] = useStateLogin('');
  const [loading, setLoading] = useStateLogin(false);

  useEffectLogin(function() {
    if (open) {
      setName(''); setPassword(''); setCity('北京');
      setSelectedPersona(null); setAvatarIdx(0);
      setError(''); setLoading(false); setMode('login');
    }
  }, [open]);

  if (!open) return null;

  var ac = AVATAR_COLORS[avatarIdx];

  async function handleSubmit() {
    var t = name.trim();
    if (!t) { setError('请输入昵称'); return; }
    if (t.length > 10) { setError('昵称最多10个字'); return; }
    if (!password || password.length < 4) { setError('密码至少4位'); return; }

    setLoading(true); setError('');
    try {
      var endpoint = mode === 'register' ? '/api/auth/register' : '/api/auth/login';
      var body = mode === 'register'
        ? { name: t, password: password, city: city, personaId: selectedPersona != null ? PERSONAS[selectedPersona].userId : null }
        : { name: t, password: password };

      var res = await fetch((window.API_BASE || '') + endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      var data = await res.json();

      if (!data.success) { setError(data.error || '操作失败'); setLoading(false); return; }

      localStorage.setItem('_authToken', data.token);

      // Build user object — if persona was selected, use persona data
      var persona = selectedPersona != null ? PERSONAS[selectedPersona] : null;
      var userObj = {
        userId: data.userId, name: data.name, avatarIdx: persona ? PERSONAS.indexOf(persona) : avatarIdx,
        preferredCity: persona ? persona.city : city,
      };
      localStorage.setItem('_authUser', JSON.stringify(userObj));

      setLoading(false);
      onLogin({
        userId: data.userId, name: data.name,
        profileName: persona ? persona.personaName : (city === '上海' ? '上海探索者' : '北京探索者'),
        preferredCity: persona ? persona.city : city,
        avgBudget: persona ? persona.budget : 150,
        favoriteCategories: persona ? [] : [],
        preferenceTags: persona
          ? Object.fromEntries(persona.tags.map(function(t) { return [t, 0.8]; }))
          : { '高评分': 0.5, '性价比': 0.5 },
        avoidTags: {},
        historyActions: [],
        isCustom: !persona,
        avatarIdx: persona ? PERSONAS.indexOf(persona) : avatarIdx,
        token: data.token,
        personaId: persona ? persona.userId : null,
      });
    } catch(e) {
      // Network error — if backend is unreachable, provide a useful message
      // and offer offline mode so the UI doesn't get stuck
      setError('网络错误，请检查后端是否启动');
      setLoading(false);
    }
  }

  // Quick persona login — uses built-in seed credentials
  async function handlePersonaLogin(personaIdx) {
    var p = PERSONAS[personaIdx];
    setLoading(true); setError('');
    try {
      var res = await fetch((window.API_BASE || '') + '/api/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: p.name, password: p.password }),
      });
      var data = await res.json();

      if (!data.success) {
        // Seed user may not exist yet — try registering
        var regRes = await fetch((window.API_BASE || '') + '/api/auth/register', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: p.name, password: p.password, city: p.city, personaId: p.userId }),
        });
        data = await regRes.json();
        if (!data.success) { setError(data.error || '登录失败'); setLoading(false); return; }
      }

      localStorage.setItem('_authToken', data.token);
      var userObj = {
        userId: data.userId, name: data.name, avatarIdx: personaIdx,
        preferredCity: p.city,
      };
      localStorage.setItem('_authUser', JSON.stringify(userObj));

      setLoading(false);
      onLogin({
        userId: data.userId, name: data.name,
        profileName: p.personaName,
        preferredCity: p.city, avgBudget: p.budget,
        favoriteCategories: [],
        preferenceTags: Object.fromEntries(p.tags.map(function(t) { return [t, 0.8]; })),
        avoidTags: {}, historyActions: [],
        isCustom: false,
        avatarIdx: personaIdx, token: data.token,
        personaId: p.userId,
      });
    } catch(e) {
      setError('网络错误，请检查后端是否启动');
      setLoading(false);
    }
  }

  // Select persona for registration (pre-fills name and city)
  function selectPersona(idx) {
    var p = PERSONAS[idx];
    setSelectedPersona(idx === selectedPersona ? null : idx);
    if (idx !== selectedPersona) {
      setName(p.name);
      setCity(p.city);
      setAvatarIdx(idx);
    } else {
      setName('');
      setCity('北京');
      setAvatarIdx(0);
    }
  }

  return (
    <div style={{
      position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)',
      zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        width: 310, background: '#fff', borderRadius: 16,
        padding: '18px 18px 16px', boxShadow: '0 16px 48px rgba(0,0,0,0.15)',
        textAlign: 'center',
      }}>
        {/* App logo/title */}
        <div style={{ marginBottom: 4 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'linear-gradient(135deg, #FF6633, #FF8C5A)',
            color: '#fff', fontSize: 18, fontWeight: 700,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 6px',
          }}>🗺</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#1A1A1A' }}>路线助手</div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', marginBottom: 10, background: '#F2F2F7', borderRadius: 7, padding: 2 }}>
          <button onClick={function() { setMode('login'); setError(''); }} style={{
            flex: 1, padding: '6px', borderRadius: 6, border: 'none', cursor: 'pointer',
            fontFamily: 'inherit', fontSize: 12, fontWeight: 600,
            background: mode === 'login' ? '#fff' : 'transparent',
            color: mode === 'login' ? '#1A1A1A' : '#8E8E93',
            boxShadow: mode === 'login' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none', transition: 'all 0.2s',
          }}>登录</button>
          <button onClick={function() { setMode('register'); setError(''); }} style={{
            flex: 1, padding: '6px', borderRadius: 6, border: 'none', cursor: 'pointer',
            fontFamily: 'inherit', fontSize: 12, fontWeight: 600,
            background: mode === 'register' ? '#fff' : 'transparent',
            color: mode === 'register' ? '#1A1A1A' : '#8E8E93',
            boxShadow: mode === 'register' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none', transition: 'all 0.2s',
          }}>注册</button>
        </div>

        {/* Persona quick-login cards */}
        <div style={{ fontSize: 11, fontWeight: 600, color: '#48484A', marginBottom: 6 }}>
          {mode === 'login' ? '快速体验' : '选择画像创建账户'}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 5, marginBottom: 10 }}>
          {PERSONAS.map(function(p, i) {
            var isSelected = mode === 'register' && selectedPersona === i;
            return (
              <button
                key={p.userId}
                onClick={function() {
                  if (mode === 'login') { handlePersonaLogin(i); }
                  else { selectPersona(i); }
                }}
                disabled={loading}
                style={{
                  padding: '8px 3px', borderRadius: 10,
                  background: isSelected ? '#FFF5F0' : '#F9F9FB',
                  border: isSelected ? '2px solid #FFC8AA' : '1px solid #F0F0F3',
                  cursor: loading ? 'default' : 'pointer',
                  textAlign: 'center', fontFamily: 'inherit',
                  transition: 'all 0.15s', opacity: loading ? 0.6 : 1,
                }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 8,
                  background: p.avatarBg, color: p.avatarFg,
                  fontSize: 13, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto 3px',
                }}>{p.name.charAt(0)}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#1A1A1A' }}>{p.name}</div>
                <div style={{
                  display: 'inline-block', marginTop: 2,
                  fontSize: 9, fontWeight: 500, color: p.avatarFg,
                  background: p.avatarBg, padding: '1px 4px', borderRadius: 4,
                }}>{p.label}</div>
              </button>
            );
          })}
        </div>

        {/* Divider */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10,
        }}>
          <div style={{ flex: 1, height: 1, background: '#EDEDEF' }} />
          <span style={{ fontSize: 10, color: '#C7C7CC', fontWeight: 500 }}>
            {mode === 'register' ? '或手动注册' : '或账号密码登录'}
          </span>
          <div style={{ flex: 1, height: 1, background: '#EDEDEF' }} />
        </div>

        <input type="text" placeholder="昵称" value={name}
          onChange={function(e) { setName(e.target.value); setError(''); }} maxLength={10} autoFocus
          style={{ width: '100%', padding: '8px 10px', marginBottom: 6, fontSize: 12, fontWeight: 500,
            color: '#1A1A1A', border: error ? '1.5px solid #E53E3E' : '1.5px solid #E8E8EA',
            borderRadius: 8, outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box',
            background: '#F7F7F8' }}
        />

        <input type="password" placeholder="密码" value={password}
          onChange={function(e) { setPassword(e.target.value); setError(''); }}
          style={{ width: '100%', padding: '8px 10px', marginBottom: 6, fontSize: 12, fontWeight: 500,
            color: '#1A1A1A', border: error ? '1.5px solid #E53E3E' : '1.5px solid #E8E8EA',
            borderRadius: 8, outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box',
            background: '#F7F7F8' }}
        />

        {mode === 'register' && (
          <>
            <button onClick={function() { setCityPickerOpen(true); }} style={{
              width: '100%', padding: '8px 10px', marginBottom: 6,
              background: '#F7F7F8', border: '1.5px solid #E8E8EA', borderRadius: 8,
              cursor: 'pointer', fontFamily: 'inherit',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <Icon name="MapPin" size={13} color="#FF6633" />
              <span style={{ flex: 1, textAlign: 'left', fontSize: 12, fontWeight: 500, color: '#1A1A1A' }}>{city || '北京'}</span>
              <Icon name="ChevronRight" size={11} color="#C7C7CC" />
            </button>

            {cityPickerOpen && window.CityPickerFullPage && (
              <window.CityPickerFullPage
                currentCity={city}
                onSelect={function(c) { setCity(c); setCityPickerOpen(false); }}
                onClose={function() { setCityPickerOpen(false); }}
              />
            )}

            {selectedPersona != null && (
              <div style={{
                padding: '5px 7px', marginBottom: 6,
                background: '#FFF9F5', borderRadius: 7, border: '1px solid #FFE4CC',
                textAlign: 'left',
              }}>
                <div style={{ fontSize: 10, color: '#FF6633', fontWeight: 600 }}>
                  已选择「{PERSONAS[selectedPersona].personaName}」画像
                </div>
              </div>
            )}
          </>
        )}

        {error && (
          <div style={{ fontSize: 10, color: '#E53E3E', marginBottom: 4, textAlign: 'left', padding: '0 2px' }}>
            {error}
          </div>
        )}

        <button onClick={handleSubmit} disabled={loading} style={{
          width: '100%', marginTop: 2, padding: '9px',
          background: loading ? '#FFB899' : '#FF6633', color: '#fff',
          border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 700,
          cursor: loading ? 'default' : 'pointer', fontFamily: 'inherit',
          boxShadow: '0 2px 10px rgba(255,102,51,0.2)', transition: 'all 0.2s',
        }}>
          {loading ? '请稍候...' : (mode === 'register' ? '注册并开始使用' : '登录')}
        </button>

        {mode === 'login' && (
          <div style={{ marginTop: 6, fontSize: 9, color: '#C7C7CC' }}>
            画像用户密码均为 1234
          </div>
        )}
      </div>
    </div>
  );
}

function getAuthToken() {
  try { return localStorage.getItem('_authToken'); } catch(e) { return null; }
}
function getAuthUser() {
  try { return JSON.parse(localStorage.getItem('_authUser') || 'null'); } catch(e) { return null; }
}

Object.assign(window, { LoginModal, getAuthToken, getAuthUser, PERSONAS });
