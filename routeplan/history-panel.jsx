// History panel — slide-up sheet listing past route generations.
// Each entry = one carousel batch (initial generation, or chip-adjusted regeneration).

const { useEffect: useEffectHP } = React;

function HistoryPanel({ open, history, onClose, onReplay, onNewConversation }) {
  // Lock body scroll while open
  useEffectHP(() => {
    if (!open) return;
  }, [open]);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'absolute', inset: 0,
          background: open ? 'rgba(20, 16, 12, 0.32)' : 'transparent',
          backdropFilter: open ? 'blur(2px)' : 'none',
          WebkitBackdropFilter: open ? 'blur(2px)' : 'none',
          pointerEvents: open ? 'auto' : 'none',
          opacity: open ? 1 : 0,
          transition: 'opacity 0.25s, backdrop-filter 0.25s',
          zIndex: 90,
        }}
      />

      {/* Sheet */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        height: '78%',
        background: '#F7F7F8',
        borderRadius: '20px 20px 0 0',
        transform: open ? 'translateY(0)' : 'translateY(100%)',
        transition: 'transform 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
        zIndex: 100,
        display: 'flex', flexDirection: 'column',
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
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 17, fontWeight: 700, color: '#1a1a1a', letterSpacing: -0.2 }}>
              你的路线
            </div>
            <div style={{ fontSize: 11.5, color: '#8e8e93', marginTop: 2 }}>
              {history.length > 0
                ? `生成过 ${history.length} 次，点击恢复`
                : '开启一次新的规划，或查看过往'}
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

        {/* list */}
        <div className="frame-scroll" style={{
          flex: 1, overflowY: 'auto',
          padding: '14px 16px 28px',
        }}>
          {/* New conversation — the primary action, sits above history */}
          <button
            onClick={onNewConversation}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              gap: 12, width: '100%',
              padding: '14px 16px',
              background: '#FF6633', color: '#fff',
              border: 'none', borderRadius: 14,
              cursor: 'pointer', fontFamily: 'inherit',
              marginBottom: history.length > 0 ? 18 : 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{
                width: 28, height: 28, borderRadius: 999,
                background: 'rgba(255,255,255,0.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name="Plus" size={16} color="#fff" strokeWidth={2.5} />
              </span>
              <div style={{ textAlign: 'left' }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>开始新对话</div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)', marginTop: 1 }}>
                  重新选一个场景或输入需求
                </div>
              </div>
            </div>
            <Icon name="ArrowRight" size={16} color="#fff" />
          </button>

          {history.length > 0 && (
            <div style={{
              fontSize: 10.5, color: '#8e8e93', fontWeight: 600,
              letterSpacing: 1.2, textTransform: 'uppercase',
              padding: '0 4px 10px',
            }}>
              过往记录
            </div>
          )}

          {history.length === 0 && (
            <div style={{
              padding: '36px 20px', textAlign: 'center',
              color: '#8e8e93', fontSize: 12.5, lineHeight: 1.7,
            }}>
              你生成过的路线会出现在这里<br />
              方便你回头对比、调整
            </div>
          )}
          {history.length > 0 && [...history].reverse().map((h, i) => {
            const realIdx = history.length - 1 - i;
            const displayNum = i + 1; // newest = #1, oldest = #N
            const isNewest = i === 0;
            return (
              <button
                key={realIdx}
                onClick={() => onReplay(realIdx)}
                style={{
                  display: 'flex', alignItems: 'stretch', gap: 0,
                  width: '100%', textAlign: 'left',
                  padding: 0,
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  fontFamily: 'inherit',
                  marginBottom: 10,
                }}
              >
                {/* index column */}
                <div style={{
                  width: 36, flexShrink: 0,
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  paddingTop: 14,
                }}>
                  <span className="num" style={{
                    width: 22, height: 22, borderRadius: 999,
                    background: isNewest ? '#FF6633' : '#fff',
                    color: isNewest ? '#fff' : '#48484A',
                    border: isNewest ? 'none' : '1px solid #E5E5E7',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10.5, fontWeight: 700,
                  }}>{displayNum}</span>
                  {i < history.length - 1 && (
                    <div style={{ width: 1, flex: 1, background: '#E5E5E7', marginTop: 4 }} />
                  )}
                </div>
                {/* card */}
                <div style={{
                  flex: 1, minWidth: 0,
                  background: '#fff', borderRadius: 14,
                  border: '1px solid #E8E8EA',
                  padding: '12px 14px',
                  marginBottom: 4,
                }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    marginBottom: 6, gap: 8,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                      <span style={{
                        fontSize: 10.5, color: '#8e8e93', fontWeight: 600,
                        letterSpacing: 0.8, textTransform: 'uppercase',
                      }}>
                        对话
                      </span>
                      <span style={{
                        fontSize: 13, fontWeight: 600, color: '#1a1a1a',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>{h.scene || '未指定'}</span>
                    </div>
                    <span style={{
                      fontSize: 10.5, color: '#C7C7CC', flexShrink: 0,
                    }}>{h.timeLabel || '刚刚'}</span>
                  </div>

                  <div style={{ fontSize: 12.5, color: '#48484A', lineHeight: 1.5, marginBottom: 8 }}>
                    {h.firstQuery
                      ? (h.firstQuery.length > 32 ? h.firstQuery.slice(0, 32) + '…' : h.firstQuery)
                      : '场景模式 · 选条件生成'}
                  </div>

                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    paddingTop: 8, borderTop: '1px dashed #E8E8EA',
                    fontSize: 11, color: '#8e8e93',
                  }}>
                    <span>{h.turnCount || 1} 轮对话 · {routesCount(h)} 条路线</span>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 3,
                      color: '#1a1a1a', fontWeight: 500,
                    }}>
                      恢复 <Icon name="ChevronRight" size={11} color="#1a1a1a" />
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}

// ─── Helpers ───────────────────────────────────────────────────
function routesCount(h) {
  if (h.routes && h.routes.length) return h.routes.length;
  return 0;
}

Object.assign(window, { HistoryPanel });
