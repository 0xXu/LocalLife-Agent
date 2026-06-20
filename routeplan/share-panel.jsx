// Share panel — bottom sheet with WeChat/QQ share options.
// WeChat Mini Program style.

function SharePanel({ open, onClose, route }) {
  if (!open) return null;
  if (!route) return null;

  var shareText = (route.route_name || '路线推荐') + ' — ' + (route.total_time || '') + ' · ¥' + (route.total_avg || 0) + '/人';

  return (
    <div onClick={onClose} style={{
      position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.45)',
      zIndex: 200, display: 'flex', alignItems: 'flex-end', justifyContent: 'center'
    }}>
      <div onClick={function(e) { e.stopPropagation(); }} style={{
        width: '100%', maxWidth: 420,
        background: '#F2F2F7', borderRadius: '20px 20px 0 0',
        overflow: 'hidden',
        animation: 'sheetUp 0.24s ease-out',
        boxShadow: '0 -8px 32px rgba(40, 30, 20, 0.18)',
      }}>
        {/* grabber */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '8px 0 4px' }}>
          <div style={{ width: 36, height: 4, borderRadius: 999, background: '#C8C8CC' }} />
        </div>

        {/* header */}
        <div style={{
          padding: '10px 20px 16px', textAlign: 'center',
        }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: '#1a1a1a', marginBottom: 4 }}>
            分享路线
          </div>
          <div style={{ fontSize: 12.5, color: '#8e8e93', lineHeight: 1.5 }}>
            {shareText}
          </div>
        </div>

        {/* share options */}
        <div style={{
          padding: '0 20px 16px',
          display: 'flex', justifyContent: 'center', gap: 40,
        }}>
          {/* WeChat */}
          <button onClick={function() { onClose(); window.showToast && window.showToast('已复制链接，打开微信粘贴即可分享'); }} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
            background: 'transparent', border: 'none', cursor: 'pointer',
            fontFamily: 'inherit', padding: 0,
          }}>
            <div style={{
              width: 56, height: 56, borderRadius: 16,
              background: '#07C160',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(7, 193, 96, 0.3)',
            }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
              </svg>
            </div>
            <span style={{ fontSize: 11.5, color: '#1a1a1a', fontWeight: 500 }}>微信好友</span>
          </button>

          {/* QQ */}
          <button onClick={function() { onClose(); window.showToast && window.showToast('已复制链接，打开QQ粘贴即可分享'); }} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
            background: 'transparent', border: 'none', cursor: 'pointer',
            fontFamily: 'inherit', padding: 0,
          }}>
            <div style={{
              width: 56, height: 56, borderRadius: 16,
              background: '#12B7F5',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(18, 183, 245, 0.3)',
            }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M8 14s1.5 2 4 2 4-2 4-2" />
                <line x1="9" y1="9" x2="9.01" y2="9" />
                <line x1="15" y1="9" x2="15.01" y2="9" />
              </svg>
            </div>
            <span style={{ fontSize: 11.5, color: '#1a1a1a', fontWeight: 500 }}>QQ好友</span>
          </button>
        </div>

        {/* cancel */}
        <button onClick={onClose} style={{
          width: '100%', padding: '14px',
          background: '#fff', border: 'none',
          fontSize: 15, color: '#1a1a1a', fontWeight: 500,
          cursor: 'pointer', fontFamily: 'inherit',
          borderTop: '1px solid #EDEDEF',
        }}>
          取消
        </button>

        {/* safe area */}
        <div style={{ height: 20, background: '#fff' }} />
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

Object.assign(window, { SharePanel });
