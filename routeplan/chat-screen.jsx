// Chat home screen — welcome, user input, requirement card, route card.

const { useState: useStateChat, useEffect: useEffectChat, useRef: useRefChat } = React;

// ─── Top bar (redesigned: icon-forward, minimal text) ──────────
function ChatTopBar({ onMenuClick, onNewChat, title }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '10px 14px', background: '#FBFBFD',
    }}>
      <button onClick={onMenuClick} style={{
        width: 36, height: 36, borderRadius: 10,
        background: 'transparent', border: 'none', cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 0,
      }}>
        <Icon name="Menu" size={22} color="#1A1A1A" />
      </button>
      <div style={{ fontWeight: 700, fontSize: 17, color: '#1A1A1A', flex: 1 }}>
        {title || '路线助手'}
      </div>
      <button onClick={onNewChat} style={{
        width: 34, height: 34, borderRadius: 17,
        background: 'transparent', border: '1.5px solid #E0E0E0', cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 0,
      }}>
        <Icon name="Plus" size={17} color="#48484A" strokeWidth={2} />
      </button>
    </div>);
}

// ─── Sidebar ────────────────────────────────────────────────────
function Sidebar({ open, onClose, currentUser, onLogout, history, onReplayHistory, favorites, onOpenDetail, city, onCityChange }) {
  var [favList, setFavList] = useStateChat([]);
  var [favFilter, setFavFilter] = useStateChat('');
  var [histFilter, setHistFilter] = useStateChat('');
  var [cityPickerOpen, setCityPickerOpen] = useStateChat(false);

  useEffectChat(function() {
    if (open && window.getFavorites) {
      window.getFavorites().then(function(f) { setFavList(f || []); }).catch(function() {});
    }
  }, [open]);

  if (!open) return null;

  var filteredFavs = favList.filter(function(f) {
    if (!favFilter) return true;
    var q = favFilter;
    if ((f.routeName || '').indexOf(q) >= 0) return true;
    try {
      var r = typeof f.routeJson === 'string' ? JSON.parse(f.routeJson) : f.routeJson;
      if (r && r.segments) {
        for (var s = 0; s < r.segments.length; s++) {
          var p = r.segments[s].poi;
          if (p && ((p.name || '').indexOf(q) >= 0)) return true;
        }
      }
    } catch(e) {}
    return false;
  });
  var filteredHist = (history || []).filter(function(h) {
    if (!histFilter) return true;
    var q = histFilter;
    if ((h.scene || '').indexOf(q) >= 0) return true;
    if ((h.firstQuery || '').indexOf(q) >= 0) return true;
    // Also search in route POI names from stored routes
    if (h.routes) {
      for (var ri = 0; ri < h.routes.length; ri++) {
        var r = h.routes[ri];
        if (r.pois) {
          for (var pi = 0; pi < r.pois.length; pi++) {
            if ((r.pois[pi].short || '').indexOf(q) >= 0) return true;
          }
        }
      }
    }
    return false;
  });

  return (
    <div>
      <div onClick={onClose} style={{
        position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 100,
      }} />
      <div style={{
        position: 'absolute', top: 0, left: 0, bottom: 0,
        width: 285, background: '#FFF', zIndex: 101,
        display: 'flex', flexDirection: 'column',
        boxShadow: '8px 0 40px rgba(0,0,0,0.06)',
        animation: 'slideInLeft 0.22s ease-out',
      }}>
        {/* User profile */}
        <div style={{ padding: '24px 18px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 44, height: 44, borderRadius: 16,
              background: 'linear-gradient(135deg, #FFE4D0, #FFC8AA)',
              color: '#E94A1A', fontSize: 20, fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, boxShadow: '0 2px 8px rgba(233,74,26,0.12)',
            }}>
              {currentUser ? currentUser.name.charAt(0) : '?'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#1A1A1A' }}>{currentUser ? currentUser.name : '未登录'}</div>
              <div style={{ fontSize: 12, color: '#8E8E93', marginTop: 2 }}>{currentUser && currentUser.profileName ? currentUser.profileName : city}</div>
            </div>
          </div>
        </div>

        {/* New chat */}
        <div style={{ padding: '0 18px 10px' }}>
          <button onClick={onClose} style={{
            width: '100%', padding: '11px 0', borderRadius: 14,
            background: '#FF6633', color: '#fff', border: 'none',
            fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            boxShadow: '0 2px 12px rgba(255,102,51,0.25)',
          }}>
            <Icon name="Plus" size={16} color="#fff" /> 新对话
          </button>
        </div>

        {/* City box */}
        <div style={{ padding: '0 18px 14px' }}>
          <button onClick={function() { setCityPickerOpen(true); }} style={{
            width: '100%', padding: '10px 14px', borderRadius: 12,
            background: '#F7F7F8', border: '1px solid #EDEDEF',
            cursor: 'pointer', fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <Icon name="MapPin" size={16} color="#FF6633" />
            <span style={{ flex: 1, textAlign: 'left', fontSize: 14, fontWeight: 600, color: '#1A1A1A' }}>{city || '北京'}</span>
            <Icon name="ChevronRight" size={14} color="#C7C7CC" />
          </button>
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: '#F0F0F3', margin: '0 18px' }} />

        {/* Fixed sections */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', paddingTop: 14 }}>
          {/* Favorites section */}
          <div style={{ padding: '0 18px', marginBottom: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#48484A' }}>
                <Icon name="Bookmark" size={14} color="#48484A" style={{ marginRight: 5 }} />收藏
              </div>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 4,
                background: '#F2F2F7', borderRadius: 8, padding: '4px 8px',
              }}>
                <Icon name="Search" size={11} color="#8E8E93" />
                <input placeholder="搜索" value={favFilter} onChange={function(e) { setFavFilter(e.target.value); }}
                  style={{
                    width: 60, border: 'none', outline: 'none', background: 'transparent',
                    fontSize: 11, color: '#1A1A1A', fontFamily: 'inherit',
                  }} />
              </div>
            </div>
            <div style={{
              maxHeight: favList.length > 0 ? 160 : 0,
              overflowY: 'auto', borderRadius: 12,
              background: '#F9F9FB', border: favList.length > 0 ? '1px solid #F0F0F3' : 'none',
              padding: favList.length > 0 ? '6px' : 0,
            }}>
              {filteredFavs.slice(0, 15).map(function(f) { return (
                <div key={f.id} onClick={function() {
                  try { var route = JSON.parse(f.routeJson); if (onOpenDetail) onOpenDetail(route); onClose(); } catch(e) {}
                }} style={{
                  padding: '10px 12px', cursor: 'pointer', borderRadius: 8,
                  background: '#fff', marginBottom: 4, border: '1px solid #F0F0F3',
                }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#1A1A1A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.routeName || '路线'}</div>
                  <div style={{ fontSize: 10, color: '#8E8E93', marginTop: 2 }}>{f.totalTime || ''} · ¥{f.totalCost || 0}</div>
                </div>
              );})}
              {favList.length === 0 && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: '#C7C7CC' }}>暂无收藏</div>}
            </div>
          </div>

          {/* History section */}
          <div style={{ padding: '0 18px', flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#48484A' }}>
                <Icon name="Clock" size={14} color="#48484A" style={{ marginRight: 5 }} />历史对话
              </div>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 4,
                background: '#F2F2F7', borderRadius: 8, padding: '4px 8px',
              }}>
                <Icon name="Search" size={11} color="#8E8E93" />
                <input placeholder="搜索" value={histFilter} onChange={function(e) { setHistFilter(e.target.value); }}
                  style={{
                    width: 60, border: 'none', outline: 'none', background: 'transparent',
                    fontSize: 11, color: '#1A1A1A', fontFamily: 'inherit',
                  }} />
              </div>
            </div>
            <div style={{
              flex: 1, overflowY: 'auto', borderRadius: 12,
              background: '#F9F9FB', border: (history || []).length > 0 ? '1px solid #F0F0F3' : 'none',
              padding: (history || []).length > 0 ? '6px' : 0, minHeight: 60,
            }}>
              {filteredHist.slice(0, 20).map(function(h, i) { return (
                <div key={i} onClick={function() { if (onReplayHistory) onReplayHistory(i); onClose(); }} style={{
                  padding: '10px 12px', cursor: 'pointer', borderRadius: 8,
                  background: '#fff', marginBottom: 4, border: '1px solid #F0F0F3',
                }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#1A1A1A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.scene || '对话'}</div>
                  <div style={{ fontSize: 10, color: '#8E8E93', marginTop: 2 }}>{h.firstQuery ? h.firstQuery.substring(0, 24) : h.timeLabel}</div>
                </div>
              );})}
              {(!history || history.length === 0) && <div style={{ padding: 20, textAlign: 'center', fontSize: 12, color: '#C7C7CC' }}>暂无历史</div>}
            </div>
          </div>
        </div>

        {/* Logout */}
        <div style={{ padding: '12px 18px 18px' }}>
          <button onClick={function() { if (onLogout) onLogout(); onClose(); }} style={{
            width: '100%', padding: '11px 0', borderRadius: 14,
            background: '#FFF', border: '1.5px solid #EDEDEF',
            fontSize: 13, fontWeight: 600, color: '#8E8E93',
            cursor: 'pointer', fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          }}>
            <Icon name="LogOut" size={14} color="#8E8E93" /> 退出登录
          </button>
        </div>
      </div>

      {/* Full-page city picker */}
      {cityPickerOpen && (
        <CityPickerFullPage
          currentCity={city}
          onSelect={function(c) { if (onCityChange) onCityChange(c); setCityPickerOpen(false); }}
          onClose={function() { setCityPickerOpen(false); }}
        />
      )}

      <style>{`
        @keyframes slideInLeft {
          from { transform: translateX(-100%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}

// ─── City picker bottom sheet ──────────────────────────────────
const CITIES = [
  { name: '北京', district: '朝阳·海淀·东城' },
  { name: '上海', district: '黄浦·浦东·静安' },
];

// ─── Full-page city picker ──────────────────────────────────────
var ALL_CITIES = [
  '北京','上海','广州','深圳','成都','杭州','武汉','西安','南京','重庆',
  '长沙','天津','苏州','郑州','青岛','大连','厦门','昆明','贵阳','南宁',
  '合肥','济南','沈阳','哈尔滨','长春','福州','南昌','太原','石家庄','兰州',
  '海口','三亚','珠海','佛山','东莞','宁波','温州','无锡','常州','南通',
  '徐州','扬州','绍兴','嘉兴','金华','台州','泉州','漳州','烟台','威海',
  '洛阳','开封','桂林','丽江','大理','拉萨','乌鲁木齐','呼和浩特','银川','西宁',
  '香港','澳门','台北','高雄','台中'
];

function CityPickerFullPage({ currentCity, onSelect, onClose }) {
  var [search, setSearch] = useStateChat('');
  var POPULAR = ['北京','上海','香港','成都','西安','杭州','广州','深圳','重庆','南京','武汉','长沙'];

  var filtered = search.trim()
    ? ALL_CITIES.filter(function(c) { return c.indexOf(search) >= 0 || c.toLowerCase().indexOf(search.toLowerCase()) >= 0; })
    : ALL_CITIES;

  // A-Z index
  var letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
  var cityMap = {};
  ALL_CITIES.forEach(function(c) {
    var py = c.charAt(0);
    // Simple pinyin mapping for common characters
    var letterMap = { '北':'B','上':'S','广':'G','深':'S','成':'C','杭':'H','武':'W','西':'X','南':'N','重':'C','长':'C','天':'T','苏':'S','郑':'Z','青':'Q','大':'D','厦':'X','昆':'K','贵':'G','南':'N','合':'H','济':'J','沈':'S','哈':'H','长':'C','福':'F','南':'N','太':'T','石':'S','兰':'L','海':'H','三':'S','珠':'Z','佛':'F','东':'D','宁':'N','温':'W','无':'W','常':'C','南':'N','徐':'X','扬':'Y','绍':'S','嘉':'J','金':'J','台':'T','泉':'Q','漳':'Z','烟':'Y','威':'W','洛':'L','开':'K','桂':'G','丽':'L','大':'D','拉':'L','乌':'W','呼':'H','银':'Y','西':'X','香':'X','澳':'A','台':'T','高':'G' };
    var letter = letterMap[py] || py;
    if (!cityMap[letter]) cityMap[letter] = [];
    cityMap[letter].push(c);
  });
  if (search.trim()) {
    cityMap = { '结果': filtered };
    letters = ['结果'];
  }

  function scrollToLetter(letter) {
    var el = document.getElementById('city-section-' + letter);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  }

  return (
    <div style={{
      position: 'absolute', inset: 0, background: '#FBFBFD', zIndex: 200,
      display: 'flex', flexDirection: 'column',
      animation: 'slideInLeft 0.22s ease-out',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '12px 14px', background: '#fff', borderBottom: '1px solid #EDEDEF' }}>
        <button onClick={onClose} style={{ width: 36, height: 36, borderRadius: 10, background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon name="ChevronLeft" size={22} color="#1A1A1A" />
        </button>
        <div style={{ flex: 1, textAlign: 'center', fontSize: 17, fontWeight: 700, color: '#1A1A1A' }}>选择城市</div>
        <div style={{ width: 36 }} />
      </div>

      {/* Search bar */}
      <div style={{ padding: '12px 14px', background: '#fff' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: '#F2F2F7', borderRadius: 12, padding: '10px 14px',
        }}>
          <Icon name="Search" size={16} color="#8E8E93" />
          <input value={search} onChange={function(e) { setSearch(e.target.value); }}
            placeholder="搜索目的地" autoFocus
            style={{
              flex: 1, border: 'none', outline: 'none', background: 'transparent',
              fontSize: 15, color: '#1A1A1A', fontFamily: 'inherit',
            }} />
          {search && (
            <button onClick={function() { setSearch(''); }} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
              <Icon name="X" size={14} color="#8E8E93" />
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', position: 'relative' }}>
        {!search.trim() && (
          <>
            {/* Current city */}
            <div style={{ padding: '14px 16px 8px' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#8E8E93', marginBottom: 8 }}>当前城市</div>
              <button onClick={function() { onSelect(currentCity || '北京'); }} style={{
                width: '100%', padding: '12px 14px', borderRadius: 12,
                background: '#FFF5F0', border: '1.5px solid #FFC8AA',
                cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: '#FF6633' }}>{currentCity || '北京'}</div>
                  <div style={{ fontSize: 11, color: '#8E8E93', marginTop: 2 }}>当前定位城市</div>
                </div>
                <div style={{
                  width: 22, height: 22, borderRadius: 11, background: '#FF6633',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Icon name="Check" size={12} color="#fff" />
                </div>
              </button>
            </div>

            {/* Popular cities */}
            <div style={{ padding: '8px 16px' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#8E8E93', marginBottom: 10 }}>热门目的地</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                {POPULAR.map(function(c) { return (
                  <button key={c} onClick={function() { onSelect(c); }} style={{
                    padding: '12px 8px', borderRadius: 12,
                    background: currentCity === c ? '#FFF5F0' : '#F7F7F8',
                    border: currentCity === c ? '1.5px solid #FFC8AA' : '1px solid transparent',
                    cursor: 'pointer', fontFamily: 'inherit', fontSize: 14, fontWeight: 600,
                    color: currentCity === c ? '#FF6633' : '#1A1A1A', textAlign: 'center',
                  }}>{c}</button>
                );})}
              </div>
            </div>
          </>
        )}

        {/* All cities by letter */}
        {Object.keys(cityMap).sort().map(function(letter) { return (
          <div key={letter} id={'city-section-' + letter} style={{ padding: '0 16px 8px' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#8E8E93', padding: '10px 0 8px', position: 'sticky', top: 0, background: '#FBFBFD' }}>{letter}</div>
            {cityMap[letter].map(function(c) { return (
              <button key={c} onClick={function() { onSelect(c); }} style={{
                width: '100%', padding: '13px 8px', borderRadius: 10,
                background: currentCity === c ? '#F7F7F8' : 'transparent',
                border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                fontSize: 14, fontWeight: 500, color: currentCity === c ? '#FF6633' : '#1A1A1A',
                textAlign: 'left', borderBottom: '1px solid #F0F0F3',
              }}>{c}</button>
            );})}
          </div>
        );})}
      </div>

      {/* A-Z index bar */}
      {!search.trim() && (
        <div style={{
          position: 'absolute', right: 2, top: '50%', transform: 'translateY(-50%)',
          display: 'flex', flexDirection: 'column', gap: 1,
          zIndex: 10, padding: '4px 2px',
        }}>
          {letters.map(function(l) { return (
            <button key={l} onClick={function() { scrollToLetter(l); }} style={{
              width: 20, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'transparent', border: 'none', cursor: 'pointer',
              fontSize: 10, fontWeight: 600, color: '#8E8E93', fontFamily: 'inherit',
              padding: 0,
            }}>{l}</button>
          );})}
        </div>
      )}
    </div>
  );
}

function CityPickerSheet({ open, currentCity, onSelect, onClose }) {
  if (!open) return null;
  return (
    <div onClick={onClose} className="fade-up" style={{
      position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.45)',
      zIndex: 160, display: 'flex', alignItems: 'flex-end', justifyContent: 'center'
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: '100%', maxWidth: 420, maxHeight: '50%',
        background: '#fff', borderRadius: '20px 20px 0 0',
        overflow: 'hidden', display: 'flex', flexDirection: 'column',
        animation: 'sheetUp 0.24s ease-out'
      }}>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0 6px' }}>
          <div style={{ width: 36, height: 4, borderRadius: 999, background: '#D1D1D6' }} />
        </div>
        <div style={{ padding: '6px 20px 12px', fontSize: 16, fontWeight: 700, color: '#1a1a1a' }}>
          选择城市
        </div>
        <div style={{ padding: '0 16px 20px', overflowY: 'auto' }}>
          {CITIES.map((c) => (
            <button key={c.name} onClick={() => { onSelect(c.name); onClose(); }} style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '14px 12px', marginBottom: 8,
              background: currentCity === c.name ? '#FFF1E5' : '#F7F7F8',
              border: currentCity === c.name ? '1.5px solid #FFC8AA' : '1px solid #EDEDEF',
              borderRadius: 12, cursor: 'pointer',
            }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', textAlign: 'left' }}>{c.name}</div>
                <div style={{ fontSize: 12, color: '#8e8e93', textAlign: 'left', marginTop: 2 }}>{c.district}</div>
              </div>
              {currentCity === c.name && <Icon name="Check" size={18} color="#FF6633" />}
            </button>
          ))}
        </div>
      </div>
      <style>{`
        @keyframes sheetUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

// ─── Welcome panel (initial state) ─────────────────────────────
const QUICK_CARDS = [
{ label: '朋友聚会', icon: 'Users', hint: '好吃好聊', bg: '#FFF1E5', fg: '#E94A1A' },
{ label: '情侣约会', icon: 'Heart', hint: '安静出片', bg: '#FDE8E8', fg: '#C53030' },
{ label: '一个人放松', icon: 'Coffee', hint: '咖啡书店', bg: '#E8F4E8', fg: '#2F855A' },
{ label: '亲子遛娃', icon: 'Baby', hint: '遛娃乐园', bg: '#FEF3E2', fg: '#C05621' },
{ label: '下班回血', icon: 'Soup', hint: '快吃暖胃', bg: '#E6EEF8', fg: '#2456a6' },
{ label: '临时救场', icon: 'Zap', hint: '附近立刻', bg: '#F3E5F5', fg: '#7B1FA2' }];


// Card tint mapping — peach / green / blue cycle, matches the home mock.
const CARD_TINTS = [
{ bg: '#FFF1E5', fg: '#E94A1A' },
{ bg: '#EAF6EC', fg: '#2c7a44' },
{ bg: '#E6EEF8', fg: '#2456a6' }];

// Expose to other scripts (need-completion.jsx, etc.)
window.CARD_TINTS = CARD_TINTS;


// Demo entry points removed — the composer carries the typed path now.

function WelcomeBlock({ onPickScene }) {
  return (
    <div className="fade-up" style={{ padding: '20px 18px 0' }}>
      {/* Hero — simplified */}
      <div style={{ marginBottom: 32, textAlign: 'center' }}>
        <h1 style={{
          margin: 0, fontSize: 26, fontWeight: 800, color: '#1A1A1A',
          letterSpacing: -1, lineHeight: 1.1, marginBottom: 8,
        }}>今天去哪？</h1>
        <p style={{
          margin: 0, fontSize: 14, color: '#8E8E93', lineHeight: 1.5,
        }}>
          选一个场景，或直接说出你的需求
        </p>
      </div>

      {/* Scene grid — large icon cards */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10,
      }}>
        {QUICK_CARDS.map(function(c) {
          return (
            <button key={c.label} onClick={function() { onPickScene(c.label); }} style={{
              background: '#fff', border: '1px solid #EDEDEF', borderRadius: 16,
              padding: '20px 16px', textAlign: 'center', cursor: 'pointer',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
              transition: 'all 0.15s', fontFamily: 'inherit',
              boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
            }}>
              <div style={{
                width: 56, height: 56, borderRadius: 16,
                background: c.bg,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name={c.icon} size={28} color={c.fg} />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16, color: '#1A1A1A', marginBottom: 2 }}>
                  {c.label}
                </div>
                <div style={{ fontSize: 12, color: '#8E8E93' }}>{c.hint}</div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── User bubble ───────────────────────────────────────────────
function UserBubble({ text }) {
  return (
    <div className="fade-up" style={{
      display: 'flex', justifyContent: 'flex-end', padding: '0 16px', marginBottom: 14
    }}>
      <div style={{
        background: '#FF6633',
        color: '#fff', fontSize: 14.5, lineHeight: 1.55,
        padding: '11px 14px', borderRadius: '16px 4px 16px 16px',
        maxWidth: '78%'
      }}>{text}</div>
    </div>);

}

// ─── Assistant message wrapper ─────────────────────────────────
function AssistantMsg({ children, label }) {
  return (
    <div className="fade-up" style={{ display: 'flex', gap: 10, padding: '0 16px', marginBottom: 14 }}>
      <AssistantAvatar size={32} />
      <div style={{ flex: 1, minWidth: 0 }}>
        {label && <div style={{ fontSize: 11.5, color: '#8e8e93', marginBottom: 4 }}>{label}</div>}
        {children}
      </div>
    </div>);

}

// ─── Loading bubble ───────────────────────────────────────────
function LoadingMsg({ text }) {
  return (
    <AssistantMsg label="路线助手 · 处理中">
      <div style={{
        background: '#fff', border: '1px solid #EDEDEF',
        borderRadius: '4px 16px 16px 16px', padding: '12px 14px',
        fontSize: 14, color: '#1d1d1f', lineHeight: 1.55,
        display: 'flex', alignItems: 'center', gap: 10
      }}>
        <LoadingDots />
        <span>{text}</span>
      </div>
    </AssistantMsg>);

}

// ─── Requirement understanding card ────────────────────────────
function RequirementCard({ onConfirm, onAddMore }) {
  return (
    <AssistantMsg label="路线助手 · 需求整理">
      <div style={{
        background: '#fff', border: '1px solid #EDEDEF', borderRadius: 16,
        padding: '14px 14px 12px', boxShadow: '0 1px 0 rgba(0,0,0,0.02)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <Icon name="ListChecks" size={15} color="#FF6633" />
          <span style={{ fontSize: 14, fontWeight: 600 }}>我先帮你整理一下需求</span>
        </div>
        <div style={{ fontSize: 12, color: '#8e8e93', marginBottom: 12 }}>
          有「<span style={{ color: '#1d63b8' }}>可改</span>」标记的字段你可以点开调整
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {REQUIREMENTS.map((r) =>
          <div key={r.label} style={{
            display: 'flex', alignItems: 'flex-start', gap: 10,
            padding: '9px 11px',
            background: '#F7F7F8', borderRadius: 10
          }}>
              <div style={{
              width: 22, height: 22, borderRadius: 6,
              background: '#fff', border: '1px solid #EDEDEF',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, marginTop: 1
            }}>
                <Icon name={r.icon} size={12} color="#6E6E73" />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11.5, color: '#8e8e93', marginBottom: 2 }}>{r.label}</div>
                <div style={{ fontSize: 13.5, color: '#1a1a1a', lineHeight: 1.4 }}>{r.value}</div>
              </div>
              {r.status === 'inferred' &&
            <span style={{
              fontSize: 11, color: '#1d63b8', background: '#E6EEF8',
              padding: '2px 7px', borderRadius: 999, fontWeight: 500,
              display: 'inline-flex', alignItems: 'center', gap: 3, flexShrink: 0
            }}>
                  <Icon name="Pencil" size={10} />
                  可改
                </span>
            }
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
          <SecondaryBtn onClick={onAddMore} icon="Plus" size="md">我再补充一下</SecondaryBtn>
          <div style={{ flex: 1 }}>
            <PrimaryBtn onClick={onConfirm} icon="Sparkles" full size="md">确认，生成路线</PrimaryBtn>
          </div>
        </div>
      </div>
    </AssistantMsg>);

}

// ─── Route summary card (main push) ────────────────────────────
function RouteCard({ onOpenDetail, onNav, onAdjust, onChip }) {
  const r = MOCK_ROUTE;
  return (
    <AssistantMsg label="路线助手 · 为你定制">
      <div style={{
        background: '#fff', border: '1px solid #EDEDEF', borderRadius: 16,
        overflow: 'hidden',
        boxShadow: '0 4px 14px rgba(180, 100, 40, 0.06)'
      }}>
        {/* header strip */}
        <div style={{
          padding: '12px 14px 10px',
          background: 'linear-gradient(180deg, #FFF6EC 0%, #FFFFFF 100%)',
          borderBottom: '1px solid #EDEDEF'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Icon name="Sparkles" size={14} color="#FF6633" />
            <span style={{ fontSize: 12.5, color: '#E94A1A', fontWeight: 600, letterSpacing: 0.3 }}>
              为你生成一条主推路线
            </span>
          </div>
          <div style={{ fontSize: 17, fontWeight: 700, color: '#1a1a1a', marginBottom: 8 }}>
            {r.route_name}
          </div>

          {/* sequence */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
            {(window.MOCK_PLACES || MOCK_PLACES).map((p, i) =>
            <React.Fragment key={p.id}>
                <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 5,
                background: '#fff', border: '1px solid #EDEDEF',
                padding: '4px 9px 4px 4px', borderRadius: 999
              }}>
                  <span style={{
                  width: 17, height: 17, borderRadius: 999,
                  background: '#FF6633', color: '#fff',
                  fontSize: 10.5, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }} className="num">{i + 1}</span>
                  <span style={{ fontSize: 12, color: '#1a1a1a', fontWeight: 500 }}>{p.short}</span>
                </div>
                {i < (window.MOCK_PLACES || MOCK_PLACES).length - 1 &&
              <Icon name="ArrowRight" size={12} color="#c5beb1" />
              }
              </React.Fragment>
            )}
          </div>
        </div>

        {/* stats grid */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1,
          background: '#EDEDEF'
        }}>
          {[
          { l: '预计耗时', v: r.total_time, icon: 'Clock' },
          { l: '人均预算', v: r.total_budget, icon: 'Wallet' },
          { l: '总步行', v: r.total_distance, icon: 'Footprints' },
          { l: '交通方式', v: '地铁 10 号线', icon: 'TrainFront' }].
          map((s, i) =>
          <div key={i} style={{
            background: '#fff', padding: '9px 12px',
            display: 'flex', flexDirection: 'column', gap: 2
          }}>
              <div style={{
              fontSize: 11, color: '#8e8e93',
              display: 'flex', alignItems: 'center', gap: 4
            }}>
                <Icon name={s.icon} size={11} color="#8e8e93" />
                {s.l}
              </div>
              <div className={s.l !== '交通方式' ? 'num' : ''} style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a' }}>{s.v}</div>
            </div>
          )}
        </div>

        {/* risk row */}
        <div style={{
          padding: '10px 14px',
          display: 'flex', alignItems: 'flex-start', gap: 6,
          fontSize: 12.5, color: '#D14600',
          background: '#FFFBF4',
          borderTop: '1px solid #EDEDEF',
          borderBottom: '1px solid #EDEDEF',
          lineHeight: 1.45
        }}>
          <Icon name="AlertTriangle" size={13} color="#D14600" style={{ marginTop: 2 }} />
          <span><strong style={{ fontWeight: 600 }}>留意：</strong>{r.risk_summary}</span>
        </div>

        {/* reasoning */}
        <div style={{ padding: '12px 14px' }}>
          <div style={{
            fontSize: 12, color: '#6E6E73', marginBottom: 6,
            display: 'flex', alignItems: 'center', gap: 4
          }}>
            <Icon name="MessageCircleHeart" size={12} color="#6E6E73" />
            我为什么选这条
          </div>
          <div style={{ fontSize: 13.5, lineHeight: 1.6, color: '#1d1d1f' }}>
            {r.recommendation_reason}
          </div>
        </div>

        {/* actions */}
        <div style={{
          display: 'flex', gap: 8, padding: '0 14px 14px'
        }}>
          <div style={{ flex: 1.4 }}>
            <PrimaryBtn onClick={onOpenDetail} icon="Map" full size="md">查看路线详情</PrimaryBtn>
          </div>
          <SecondaryBtn onClick={onNav} icon="Navigation">导航第一站</SecondaryBtn>
        </div>
        <button onClick={onAdjust} style={{
          width: '100%', padding: '10px', background: '#F7F7F8',
          border: 'none', borderTop: '1px solid #EDEDEF',
          fontSize: 13, color: '#1d1d1f', fontWeight: 500,
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5
        }}>
          <Icon name="Wand2" size={13} color="#1d1d1f" />
          帮我调整这条路线
        </button>
      </div>

      {/* quick-edit chips */}
      <div style={{ marginTop: 10, marginBottom: 2 }}>
        <div style={{ fontSize: 11.5, color: '#8e8e93', marginBottom: 6 }}>快捷调整 ↓</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {['更便宜一点', '少走路', '不想排队', '换个口味', '更适合拍照', '改成地铁优先', '加一个咖啡店'].map((c) =>
          <Chip key={c} onClick={() => onChip(c)}>{c}</Chip>
          )}
        </div>
      </div>
    </AssistantMsg>);

}

// ─── Composer ──────────────────────────────────────────────────
function Composer({ value, onChange, onSend, placeholder }) {
  const [voiceMode, setVoiceMode] = useStateChat(false);
  const [recording, setRecording] = useStateChat(false);

  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      background: 'linear-gradient(180deg, rgba(247,247,248,0) 0%, #F7F7F8 22%)',
      padding: '12px 10px 22px', zIndex: 20
    }}>
      {voiceMode ? (
        /* Voice mode */
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button onClick={function() { setVoiceMode(false); }} style={{
            width: 44, height: 44, borderRadius: 22,
            background: '#fff', border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0, boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
          }}>
            <Icon name="Keyboard" size={20} color="#48484A" />
          </button>
          <button
            onMouseDown={function() { setRecording(true); }}
            onMouseUp={function() { setRecording(false); window.showToast && window.showToast('语音识别开发中'); }}
            onMouseLeave={function() { setRecording(false); }}
            style={{
              flex: 1, padding: '16px', borderRadius: 22,
              background: recording ? '#FF6633' : '#fff',
              border: 'none', cursor: 'pointer',
              fontSize: 15, fontWeight: 600, color: recording ? '#fff' : '#8E8E93',
              fontFamily: 'inherit', textAlign: 'center',
              boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
              transition: 'all 0.15s',
            }}>
            {recording ? '松开结束' : '按住说话'}
          </button>
        </div>
      ) : (
        /* Keyboard mode — borderless floating */
        <div style={{
          background: '#fff', borderRadius: 24,
          padding: '8px 8px 6px 14px',
          boxShadow: '0 2px 20px rgba(0,0,0,0.06)',
        }}>
          <textarea value={value}
            onChange={function(e) { onChange(e.target.value); }}
            placeholder={placeholder || '告诉我你想去哪、和谁、预算多少…'}
            rows={1}
            style={{
              width: '100%', border: 'none', outline: 'none', resize: 'none',
              fontSize: 14, lineHeight: 1.5, fontFamily: 'inherit',
              padding: '6px 0 4px', maxHeight: 80, background: 'transparent',
              color: '#1a1a1a', boxSizing: 'border-box',
            }} />
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            paddingTop: 4,
          }}>
            <button onClick={function() { setVoiceMode(true); }} style={{
              width: 36, height: 36, borderRadius: 20,
              background: '#fff', border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: 0, boxShadow: '0 1px 6px rgba(0,0,0,0.08)',
              marginLeft: -2,
            }}>
              <Icon name="Mic" size={17} color="#8E8E93" />
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <button onClick={function() { window.showToast && window.showToast('上传/拍照功能开发中'); }} style={{
                width: 36, height: 36, borderRadius: 20,
                background: '#fff', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 0, boxShadow: '0 1px 6px rgba(0,0,0,0.08)',
              }}>
                <Icon name="PlusCircle" size={18} color="#8E8E93" />
              </button>
              <button onClick={onSend} disabled={!value.trim()} style={{
                width: 36, height: 36, borderRadius: 20,
                background: value.trim() ? '#FF6633' : '#F2F2F7',
                border: 'none', cursor: value.trim() ? 'pointer' : 'default',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0, transition: 'all 0.15s',
                boxShadow: value.trim() ? '0 2px 10px rgba(255,102,51,0.3)' : 'none',
              }}>
                <Icon name="ArrowUp" size={16} color={value.trim() ? '#fff' : '#C7C7CC'} strokeWidth={2.5} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>);
}

// ─── Branch-aware summary node above the route output ──────────
function buildSummaryNode(s) {
  if (s.activeChip) {
    return <ChipAdjustmentSummary chip={s.activeChip} />;
  }
  if (!s.nl) return null; // scene-tap → fall back to ParsingSummary
  if (s.nl.branch === 'complete') {
    return <CompleteSummary scene={s.scene} extracted={s.nl.extracted} />;
  }
  if (s.nl.branch === 'assumption') {
    return <AssumptionBanner scene={s.scene} extracted={s.nl.extracted} assumed={s.nl.assumed} />;
  }
  if (s.nl.branch === 'conflict') {
    return <ConflictSummary scene={s.scene} priority={s.conflictPriority} />;
  }
  if (s.nl.branch === 'followup') {
    return <FollowupSummary scene={s.scene} raw={s.nl.raw} answers={s.answers} />;
  }
  return null;
}

// ─── Loading text per branch ───────────────────────────────────
function loadingTextFor(s) {
  if (s.nl) return window.nlLoadingText(s.nl.branch);
  if (s.defaulted) return '按默认设定为你挑路线，马上好…';
  return '正在结合店铺信息、大家的真实评价和交通情况，为你生成路线…';
}

// ─── Main chat screen ──────────────────────────────────────────
function ChatScreen({
  chatState, toast,
  onSend, onPickScene, onAnswer, onSkipCompletion, onEditAnswer, onResetScene,
  onNLFollowupAnswer, onConflictPriority,
  onAddMore, onOpenDetail, onNav, onAdjust, onSwap, onChip,
  history, historyOpen, onOpenHistory, onCloseHistory, onReplayHistory, onNewConversation,
  city, onCityChange,
  currentUser, onUserChange, onLogout,
}) {
  const [input, setInput] = useStateChat('');
  const [sidebarOpen, setSidebarOpen] = useStateChat(false);
  const [cityPickerOpen, setCityPickerOpen] = useStateChat(false);
  const [favoritesOpen, setFavoritesOpen] = useStateChat(false);
  const [shareOpen, setShareOpen] = useStateChat(false);
  const [shareRoute, setShareRoute] = useStateChat(null);
  const [compareOpen, setCompareOpen] = useStateChat(false);
  const [compareRoutes, setCompareRoutes] = useStateChat(null);
  const scrollRef = useRefChat(null);

  // Wire up shared state for cross-component SharePanel access
  useEffectChat(() => {
    window._setShareOpen = function(open) {
      setShareOpen(open);
      if (!open) {
        window._shareRoute = null;
      } else {
        setShareRoute(window._shareRoute);
      }
    };
    return () => { delete window._setShareOpen; };
  }, []);

  // Scroll to top when new routes appear (not on adjustment loading)
  var prevStage = useRefChat(chatState.stage);
  var wasRouteBeforeGenerating = useRefChat(false);
  useEffectChat(() => {
    var was = prevStage.current;
    prevStage.current = chatState.stage;

    // Track whether we were in 'route' stage before entering 'generating'
    // This distinguishes "first route generation" from "adjustment regeneration"
    if (was === 'route' && chatState.stage === 'generating') {
      wasRouteBeforeGenerating.current = true;
    }

    var toRoute = chatState.stage === 'route';
    if (toRoute && scrollRef.current) {
      if (wasRouteBeforeGenerating.current) {
        // Adjustment: scroll to bottom to show the new route result
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        wasRouteBeforeGenerating.current = false;
      } else if (was !== 'route') {
        // First route generation: scroll to top
        scrollRef.current.scrollTop = 0;
      }
    }
    if (chatState.stage !== 'generating' && chatState.stage !== 'route') {
      wasRouteBeforeGenerating.current = false;
    }
  }, [chatState.stage]);

  const handleSendInput = () => {
    if (!input.trim()) return;
    onSend(input.trim());
    setInput('');
  };

  const handleTag = (t) => setInput((v) => v ? v + ' ' + t : t);

  // Whether the conversation is on the NL (typed) path
  const isNLPath = !!chatState.userText;
  const stage = chatState.stage;
  const convoMessages = chatState.conversationMessages || [];

  // Full-page compare view — replaces the entire main screen
  if (compareOpen && window.RouteComparePanel) {
    return (
      <div style={{ height: '100%', position: 'relative', background: '#F7F7F8', overflow: 'hidden' }}>
        <window.RouteComparePanel
          routes={compareRoutes || []}
          onBack={function() { setCompareOpen(false); }}
          onSelectRoute={function(route) {
            setCompareOpen(false);
            if (onOpenDetail) onOpenDetail(route);
          }}
        />
      </div>
    );
  }

  return (
    <div style={{ height: '100%', position: 'relative', background: '#F7F7F8', overflow: 'hidden' }}>
      {/* Sidebar — always rendered behind main content */}
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        currentUser={currentUser}
        onLogout={onLogout}
        history={history}
        onReplayHistory={onReplayHistory}
        favorites={null}
        onOpenDetail={onOpenDetail}
        city={city}
        onCityChange={onCityChange}
      />

      {/* Main content — slides right when sidebar opens */}
      <div style={{
        height: '100%', display: 'flex', flexDirection: 'column',
        background: '#F7F7F8',
        transform: sidebarOpen ? 'translateX(275px)' : 'translateX(0)',
        borderRadius: sidebarOpen ? 20 : 0,
        boxShadow: sidebarOpen ? '-8px 0 40px rgba(0,0,0,0.15)' : 'none',
        transition: 'all 0.28s cubic-bezier(0.4, 0, 0.2, 1)',
        position: 'relative', zIndex: 2,
        overflow: 'hidden',
      }}>
        <ChatTopBar
          onMenuClick={() => setSidebarOpen(true)}
          onNewChat={onNewConversation || (function() { window.location.reload(); })}
        />

      <CityPickerSheet
        open={cityPickerOpen}
        currentCity={city || '北京'}
        onSelect={(c) => { onCityChange && onCityChange(c); }}
        onClose={() => setCityPickerOpen(false)}
      />

      <div ref={scrollRef} className="frame-scroll" style={{
        flex: 1, overflowY: 'auto', overflowX: 'hidden',
        paddingBottom: 180,
      }}>
        {/* ── Conversation message list (all past messages) ── */}
        {convoMessages.length > 0 && (
          <div style={{ padding: '12px 0 6px' }}>
            {convoMessages.map(function(msg, idx) {
              if (msg.type === 'user') {
                return <UserBubble key={msg._key || idx} text={msg.text} />;
              }
              if (msg.type === 'route') {
                return (
                  <div key={msg._key || idx} style={{ marginBottom: 14 }}>
                    {msg.chipLabel && (
                      <div style={{ padding: '4px 20px 6px', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{
                          width: 28, height: 28, borderRadius: 999,
                          background: '#FF6633', color: '#fff',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <Icon name="SlidersHorizontal" size={14} color="#fff" />
                        </div>
                        <span style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a' }}>
                          已按「{msg.chipLabel}」调整
                        </span>
                      </div>
                    )}
                    <RouteOptionsCard
                      scene={msg.scene || '朋友聚会'}
                      answers={msg.answers || {}}
                      defaulted={!!msg.defaulted}
                      routes={msg.routes || []}
                      onOpenDetail={onOpenDetail}
                      onSwap={null}
                      onChip={null}
                      readOnly={true}
                      city={city}
                    />
                  </div>
                );
              }
              return null;
            })}
          </div>
        )}

        {/* ── Welcome (only when no conversation history) ── */}
        {stage === 'welcome' && convoMessages.length === 0 && (
          <WelcomeBlock onPickScene={onPickScene} />
        )}

        {/* ── Scene-tap completing ── */}
        {stage === 'completing' && (
          <>
            <div style={{ height: 6 }} />
            <SystemPromptCard scene={chatState.scene} onChangeScene={onResetScene} />
            <div style={{ height: 4 }} />
            <NeedCompletionCard
              scene={chatState.scene}
              answers={chatState.answers}
              onAnswer={onAnswer}
              onSkip={onSkipCompletion}
              onEditAnswer={onEditAnswer}
            />
            <div style={{ height: 40 }} />
          </>
        )}

        {/* ── NL: followup questions ── */}
        {isNLPath && stage === 'nl_followup' && (
          <FollowupCard
            rawText={chatState.userText}
            questions={chatState.nl.questions}
            answers={chatState.answers}
            onAnswer={onNLFollowupAnswer}
          />
        )}

        {/* ── NL: conflict resolution ── */}
        {isNLPath && stage === 'nl_conflict' && (
          <ConflictCard
            scene={chatState.scene}
            conditions={chatState.nl.conditions}
            onPickPriority={onConflictPriority}
          />
        )}

        {/* ── Generating (both paths) ── */}
        {stage === 'generating' && (
          <>
            {!isNLPath && convoMessages.length === 0 && (
              <>
                <div style={{ height: 8 }} />
                <SystemPromptCard scene={chatState.scene} onChangeScene={onResetScene} />
                <div style={{ height: 8 }} />
              </>
            )}
            {!isNLPath && convoMessages.length > 0 && <div style={{ height: 8 }} />}
            <LoadingMsg text={loadingTextFor(chatState)} />
          </>
        )}

        {/* ── Route result (both paths) ── */}
        {stage === 'route' && (
          <>
            {!isNLPath && convoMessages.length === 0 && (
              <>
                <div style={{ height: 8 }} />
                <SystemPromptCard scene={chatState.scene} onChangeScene={onResetScene} />
              </>
            )}
            {/* Budget ceiling / constraint warning */}
            {chatState.routeWarning && (
              <div style={{
                margin: '0 16px 10px', padding: '10px 14px',
                background: '#FFFBF4', border: '1px solid #FFE4C4',
                borderRadius: 10, fontSize: 12.5, color: '#D14600',
                display: 'flex', alignItems: 'flex-start', gap: 8,
                lineHeight: 1.5,
              }}>
                <span style={{ flexShrink: 0, marginTop: 1 }}>⚠️</span>
                <span>{chatState.routeWarning}</span>
              </div>
            )}
            <RouteOptionsCard
              scene={chatState.scene || '朋友聚会'}
              answers={chatState.answers}
              defaulted={chatState.defaulted}
              summaryNode={buildSummaryNode(chatState)}
              routes={chatState.routes}
              onOpenDetail={onOpenDetail}
              onSwap={onSwap}
              onChip={onChip}
              city={city}
              onCompare={function(routes) { setCompareRoutes(routes); setCompareOpen(true); }}
            />
          </>
        )}

        <div style={{ height: 20 }} />
      </div>

      <Composer
        value={input}
        onChange={setInput}
        onSend={handleSendInput}
        onTag={handleTag}
        showTags={stage !== 'welcome'}
      />

      <Toast message={toast} />
      <HistoryPanel
        open={!!historyOpen}
        history={history || []}
        onClose={onCloseHistory}
        onReplay={onReplayHistory}
        onNewConversation={onNewConversation}
      />
      {window.FavoritesPanel && (
        <window.FavoritesPanel
          open={favoritesOpen}
          onClose={() => setFavoritesOpen(false)}
          onOpenDetail={onOpenDetail}
        />
      )}
      {window.SharePanel && (
        <window.SharePanel
          open={shareOpen}
          onClose={() => { setShareOpen(false); window._shareRoute = null; }}
          route={shareRoute}
        />
      )}
    </div>
      </div>
  );
}

// ─── User picker bottom sheet (visual card style) ──────────────
function UserPickerSheet({ open, currentUser, onSelect, onClose, onAddUser }) {
  const [profiles, setProfiles] = useStateChat([]);

  var customColors = [
    { bg: '#E8EAF6', fg: '#3F51B5' },
    { bg: '#F3E5F5', fg: '#7B1FA2' },
    { bg: '#E0F2F1', fg: '#00695C' },
  ];

  useEffectChat(() => {
    if (open) {
      // Load mock profiles + custom users
      var p1 = window.getUserProfiles ? window.getUserProfiles() : Promise.resolve([]);
      Promise.resolve(p1).then(function(mock) {
        var custom = [];
        try { custom = JSON.parse(localStorage.getItem('_customUsers') || '[]'); } catch(e) {}
        setProfiles([].concat(mock || [], custom));
      });
    }
  }, [open]);

  if (!open) return null;

  function getAvatarStyle(p) {
    if (p.isCustom) {
      var ci = (p.avatarIdx || 0) % customColors.length;
      return customColors[ci];
    }
    if (p.userId === 'user_001') return { bg: '#FDE8E8', fg: '#C53030', label: '约会' };
    if (p.userId === 'user_002') return { bg: '#E8F4E8', fg: '#2F855A', label: '效率' };
    if (p.userId === 'user_003') return { bg: '#FEF3E2', fg: '#C05621', label: '探店' };
    return { bg: '#EDEDEF', fg: '#8E8E93', label: '' };
  }

  return (
    <div onClick={onClose} className="fade-up" style={{
      position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.45)',
      zIndex: 160, display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
    }}>
      <div onClick={function(e) { e.stopPropagation(); }} style={{
        width: '100%', maxWidth: 420, background: '#fff',
        borderRadius: '20px 20px 0 0', overflow: 'hidden',
        animation: 'slideUp 0.28s ease-out', paddingBottom: 34,
      }}>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0 8px' }}>
          <div style={{ width: 32, height: 4, borderRadius: 999, background: '#D1D1D6' }} />
        </div>
        <div style={{ fontSize: 17, fontWeight: 700, textAlign: 'center', padding: '8px 0 16px', color: '#1A1A1A' }}>
          切换用户
        </div>

        {/* Cards grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, padding: '0 16px' }}>
          {/* Profile cards */}
          {profiles.map(function(p) {
            var av = getAvatarStyle(p);
            var isActive = currentUser && currentUser.userId === p.userId;
            return (
              <div key={p.userId} onClick={function() { onSelect(p); }} style={{
                padding: '16px 12px', borderRadius: 14,
                background: isActive ? '#FFF7F0' : '#F7F7F8',
                border: isActive ? '2px solid #FFC8AA' : '2px solid transparent',
                cursor: 'pointer', textAlign: 'center',
                position: 'relative',
              }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 14,
                  background: av.bg, color: av.fg,
                  fontSize: 20, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto 8px',
                }}>{p.name.charAt(0)}</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#1A1A1A' }}>{p.name}</div>
                {av.label && (
                  <span style={{
                    display: 'inline-block', marginTop: 4,
                    fontSize: 10, fontWeight: 500, color: av.fg,
                    background: av.bg, padding: '2px 6px', borderRadius: 6,
                  }}>{av.label}</span>
                )}
              </div>
            );
          })}
        </div>

        {/* Add account */}
        <button onClick={function() { onAddUser ? onAddUser() : onSelect(null); }} style={{
          margin: '16px 16px 0', width: 'calc(100% - 32px)',
          padding: '12px', borderRadius: 12,
          background: '#FF6633', color: '#fff', border: 'none',
          fontSize: 15, fontWeight: 600, cursor: 'pointer',
          fontFamily: 'inherit',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
        }}>
          <Icon name="UserPlus" size={18} color="#fff" />
          创建新用户
        </button>
      </div>
    </div>
  );
}

Object.assign(window, { ChatScreen, ChatTopBar, CityPickerSheet, CityPickerFullPage, Sidebar, CITIES });