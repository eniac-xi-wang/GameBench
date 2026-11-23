from html import escape
import difflib
import json
from pathlib import Path
from . import core

STYLE='body{font:16px/1.7 system-ui,sans-serif;background:#faf8ef;color:#493f35;max-width:1100px;margin:32px auto;padding:0 24px 60px}h1{font-size:30px}h2{font-size:22px;margin-top:32px}table{border-collapse:collapse;background:white;width:100%;margin:16px 0}th,td{padding:10px 14px;border-bottom:1px solid #ddd4ca;text-align:left}th{background:#eee4da}a{color:#22658b}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eee4da;padding:16px}td{overflow-wrap:anywhere}'
def page(title,body):return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>'+STYLE+'</style><h1>'+escape(title)+'</h1>'+body+'</html>'
def table(headers,rows):return '<table><tr>'+''.join('<th>'+escape(str(x))+'</th>' for x in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</table>'
def render_batch(out,records,result):
    out=Path(out);replays=out/'replays';replays.mkdir(exist_ok=True)
    template=(core.PACKAGE/'replay.html').read_text()
    for r in records:
        data={k:v for k,v in r.items() if k!='key'}
        (replays/(r['id']+'.html')).write_text(template.replace('__RECORD__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c')))
    lo,hi=result['score_ci95']
    body=f'<p>平均得分 <b>{result["score"]:,.1f}</b>；95% 区间 [{lo:,.1f}, {hi:,.1f}]；{len(records)} 局，{result["failures"]} 次策略失败。</p>'
    body+='<p>最大 2000 次有效行动；达到 2048 后继续。无效行动或资源超限计零分，行动上限保留实际得分。</p>'
    body+=table(['比赛','计分','最大方块','行动数','结束'],[[f'<a href="replays/{r["id"]}.html">{r["id"]}</a>',r['score'],r['max_tile'],r['moves'],escape(r['termination'])] for r in records])
    (out/'index.html').write_text(page('2048 · 批量评测与回放',body))
