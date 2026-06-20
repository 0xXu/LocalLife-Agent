// Favorites panel — bottom sheet showing saved routes with search.
// Accessible from the bookmark icon in the top bar.

const { useState: useStateFav, useEffect: useEffectFav, useMemo: useMemoFav } = React;

function FavoritesPanel({ open, onClose, onOpenDetail }) {
  const [favorites, setFavorites] = useStateFav([]);
  const [loading, setLoading] = useStateFav(false);
  const [search, setSearch] = useStateFav('');

  useEffectFav(function() {
    if (!open) return;
    setSearch('');
    setLoading(true);
    window.getFavorites().then(function(data) {
      var list = data || [];
      // Sort newest first by createdAt (server should already do this, but enforce locally too)
      list.sort(function(a, b) {
        var ta = a.createdAt ? new Date(a.createdAt).getTime() : 0;
        var tb = b.createdAt ? new Date(b.createdAt).getTime() : 0;
        return tb - ta;
      });
      setFavorites(list);
      setLoading(false);
    }).catch(function() {
      setFavorites([]);
      setLoading(false);
    });
  }, [open]);

  // Filter by search keyword — matches route name, scene, and POI names inside routeJson
  var filteredFavorites = useMemoFav(function() {
    if (!search.trim()) return favorites;
    var kw = search.trim().toLowerCase();
    return favorites.filter(function(f) {
      // Match route name
      if (f.routeName && f.routeName.toLowerCase().indexOf(kw) !== -1) return true;
      // Match scene
      if (f.scene && f.scene.toLowerCase().indexOf(kw) !== -1) return true;
      // Match POI names inside routeJson
      try {
        var routeData = JSON.parse(f.routeJson || '{}');
        var pois = routeData.pois || routeData._raw && routeData._raw.segments || [];
        for (var i = 0; i < pois.length; i++) {
          var poi = pois[i].poi || pois[i];
          var name = poi.name || poi.short || '';
          if (name.toLowerCase().indexOf(kw) !== -1) return true;
        }
      } catch(e) {}
      return false;
    });
  }, [favorites, search]);

  if (!open) return null;

  return (
    <div onClick={onClose} className="fade-up" style={{
      position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.45)',
      zIndex: 160, display: 'flex', alignItems: 'flex-end', justifyContent: 'center'
    }}>
      <div onClick={function(e) { e.stopPropagation(); }} style={{
        width: '100%', maxWidth: 420, height: '78%',
        background: '#F7F7F8', borderRadius: '20px 20px 0 0',
        overflow: 'hidden', display: 'flex', flexDirection: 'column',
        animation: 'sheetUp 0.24s ease-out',
        boxShadow: '0 -8px 32px rgba(40, 30, 20, 0.18)',
      }}>
        {/* grabber */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '8px 0 4px' }}>
          <div style={{ width: 36, height: 4, borderRadius: 999, background: '#C8C8CC' }} />
        </div>

        {/* header */}
        <div style={{
          padding: '6px 18px 14px',
          borderBottom: '1px solid #EDEDEF',
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          gap: 10,
        }}>
          <div>
            <div style={{ fontSize: 17, fontWeight: 700, color: '#1a1a1a', letterSpacing: -0.2 }}>
              我的收藏
            </div>
            <div style={{ fontSize: 11.5, color: '#8e8e93', marginTop: 2 }}>
              {favorites.length > 0
                ? '已收藏 ' + favorites.length + ' 条路线'
                : '收藏喜欢的路线，方便随时查看'}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: '#fff', border: '1px solid #EDEDEF',
            borderRadius: 999, padding: 6, cursor: 'pointer', lineHeight: 0,
            flexShrink: 0,
          }}>
            <Icon name="X" size={16} color="#1d1d1f" />
          </button>
        </div>

        {/* search bar */}
        {favorites.length > 0 && (
          <div style={{ padding: '10px 16px' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: '#fff', borderRadius: 12,
              border: '1px solid #E8E8EA',
              padding: '0 12px',
            }}>
              <Icon name="Search" size={15} color="#8E8E93" />
              <input
                type="text"
                placeholder="搜索收藏的路线、店铺或景点..."
                value={search}
                onChange={function(e) { setSearch(e.target.value); }}
                style={{
                  flex: 1, padding: '11px 0', fontSize: 14, fontWeight: 500,
                  color: '#1A1A1A', border: 'none', outline: 'none',
                  fontFamily: 'inherit', background: 'transparent',
                }}
              />
              {search && (
                <button onClick={function() { setSearch(''); }} style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: 4,
                }}>
                  <Icon name="XCircle" size={15} color="#C7C7CC" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* list */}
        <div className="frame-scroll" style={{
          flex: 1, overflowY: 'auto',
          padding: '14px 16px 28px',
        }}>
          {loading && (
            <div style={{
              padding: '48px 20px', textAlign: 'center',
              color: '#8e8e93', fontSize: 13,
            }}>
              <LoadingDots />
              <div style={{ marginTop: 12 }}>加载中…</div>
            </div>
          )}

          {!loading && filteredFavorites.length === 0 && !search && (
            <div style={{
              padding: '48px 20px', textAlign: 'center',
              color: '#8e8e93', fontSize: 13, lineHeight: 1.7,
            }}>
              <div style={{
                width: 56, height: 56, borderRadius: 999,
                background: '#EDEDEF', margin: '0 auto 16px',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name="Bookmark" size={24} color="#C7C7CC" />
              </div>
              还没有收藏路线<br />
              在路线卡片上点亮收藏即可保存
            </div>
          )}

          {!loading && filteredFavorites.length === 0 && search && (
            <div style={{
              padding: '48px 20px', textAlign: 'center',
              color: '#8e8e93', fontSize: 13, lineHeight: 1.7,
            }}>
              没有找到包含「{search}」的收藏
            </div>
          )}

          {!loading && filteredFavorites.map(function(f) {
            var routeData = null;
            try { routeData = JSON.parse(f.routeJson || '{}'); } catch(e) { routeData = {}; }
            return (
              <button
                key={f.id}
                onClick={function() {
                  if (onOpenDetail && routeData && routeData.id) {
                    onClose();
                    onOpenDetail(routeData);
                  }
                }}
                style={{
                  display: 'block', width: '100%', textAlign: 'left',
                  background: '#fff', borderRadius: 14,
                  border: '1px solid #E8E8EA',
                  padding: '14px 14px',
                  marginBottom: 10,
                  cursor: 'pointer', fontFamily: 'inherit',
                }}
              >
                {/* top row */}
                <div style={{
                  display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
                  marginBottom: 8, gap: 8,
                }}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{
                      fontSize: 14, fontWeight: 600, color: '#1a1a1a',
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
                      {f.routeName || '未命名路线'}
                    </div>
                    <div style={{ fontSize: 11.5, color: '#8e8e93', marginTop: 3 }}>
                      {f.scene || ''}{f.poiCount ? ' · ' + f.poiCount + ' 个地点' : ''}
                    </div>
                  </div>
                  <button
                    onClick={function(e) {
                      e.stopPropagation();
                      window.deleteFavorite(f.id).then(function() {
                        setFavorites(function(prev) { return prev.filter(function(x) { return x.id !== f.id; }); });
                        window.showToast && window.showToast('已取消收藏');
                      }).catch(function() {
                        setFavorites(function(prev) { return prev.filter(function(x) { return x.id !== f.id; }); });
                      });
                    }}
                    style={{
                      width: 28, height: 28, borderRadius: 999,
                      background: '#FFF1E5', border: 'none',
                      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0, padding: 0,
                    }}
                  >
                    <Icon name="Bookmark" size={14} color="#FF6633" fill="#FF6633" />
                  </button>
                </div>

                {/* stats row */}
                <div style={{
                  display: 'flex', gap: 16,
                  fontSize: 12, color: '#48484A',
                }}>
                  {f.totalTime && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Icon name="Clock" size={11} color="#8e8e93" />
                      {f.totalTime}
                    </span>
                  )}
                  {f.totalCost > 0 && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Icon name="Wallet" size={11} color="#8e8e93" />
                      人均 ¥{f.totalCost}
                    </span>
                  )}
                  <span style={{
                    fontSize: 10.5, color: '#C7C7CC', marginLeft: 'auto',
                  }}>
                    {formatFavTime(f.createdAt)}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        <style>{`
          @keyframes sheetUp {
            from { transform: translateY(100%); }
            to { transform: translateY(0); }
          }
        `}</style>
      </div>
    </div>
  );
}

function formatFavTime(ts) {
  if (!ts) return '';
  var d = new Date(ts);
  var now = new Date();
  var diff = now - d;
  if (diff < 3600000) return '刚刚';
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前';
  if (diff < 604800000) return Math.floor(diff / 86400000) + ' 天前';
  return (d.getMonth() + 1) + '/' + d.getDate();
}

Object.assign(window, { FavoritesPanel });
