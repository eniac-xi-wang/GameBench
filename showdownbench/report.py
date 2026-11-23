"""Self-contained turn replay plus optional official animated replay."""
import html
import json
from pathlib import Path


STYLE='''body{font:16px system-ui;background:#101820;color:#ecf4f8;max-width:1080px;margin:36px auto;padding:0 24px}a{color:#70d4ef}table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #334352}button{padding:9px 16px;margin:5px;background:#203b4d;color:#fff;border:1px solid #547388;border-radius:6px}pre{white-space:pre-wrap;background:#172630;padding:20px;line-height:1.7}input{width:80%}.arena{display:flex;gap:30px}.card{flex:1;background:#1c303f;padding:22px;border-radius:12px}progress{width:100%;height:24px}.dim{color:#9db0bd}'''


def render(out, records, result):
    folder=out/'replays';folder.mkdir(exist_ok=True)
    template=(Path(__file__).with_name('replay.html')).read_text()
    for r in records:
        public={k:r[k] for k in ('id','opponent','candidate_side','winner','score','turns','termination','log')}
        content=template.replace('__STYLE__',STYLE).replace('__DATA__',json.dumps(public,ensure_ascii=False).replace('<','\\u003c'))
        (folder/(r['id']+'.html')).write_text(content)
        # Same log container as Showdown's own downloadable replays. No upload occurs.
        log='\n'.join(r['log']).replace('/','\\/')
        official='''<!doctype html><meta charset="utf-8"><title>Showdown replay</title>
<div class="wrapper replay-wrapper" style="max-width:1180px;margin:0 auto"><div class="battle"></div><div class="battle-log"></div><div class="replay-controls"></div><div class="replay-controls-2"></div></div>
<script type="text/plain" class="battle-log-data">'''+log+'''</script>
<script src="https://play.pokemonshowdown.com/js/replay-embed.js"></script>'''
        (folder/(r['id']+'-animated.html')).write_text(official)
    rows=''.join(f'<tr><td><a href="replays/{r["id"]}.html">{r["id"]}</a></td><td>{html.escape(r["opponent"])}</td><td>{r["candidate_side"]}</td><td>{r["score"]}</td><td>{r["turns"]}</td><td>{r["termination"]}</td></tr>' for r in records)
    (out/'index.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>Showdown 批量对战</title><style>{STYLE}</style><h1>Showdown · 批量对战</h1><p>{result['games']} 局 · 得分率 {result['score']:.1%} · 95% 区间 {result['score_ci95'][0]:.1%}–{result['score_ci95'][1]:.1%}</p><p class="dim">胜 1、平 0.5、负 0；超时/非法行动判负，未完成局计 0。区间按交换双方位置的比赛块重采样。</p><p>{result['wall_seconds']:.2f} 秒 · {result['games_per_second']:.2f} 局/秒 · 程序失败 {result['failures']} · 回合上限 {result['turn_limits']}</p><table><tr><th>回放</th><th>对手</th><th>候选方</th><th>得分</th><th>回合</th><th>结束原因</th></tr>{rows}</table>''')
