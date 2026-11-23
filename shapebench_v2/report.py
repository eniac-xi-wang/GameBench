from html import escape
import json
from pathlib import Path

def page(title,body):
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>'+escape(title)+'</title><style>body{font:16px/1.7 system-ui;max-width:1100px;margin:35px auto;padding:0 24px;background:#f4f6f8;color:#253341}table{border-collapse:collapse;background:white;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}a{color:#1766a5}</style><h1>'+escape(title)+'</h1>'+body+'</html>'
def render(out,definitions,records,result):
    out=Path(out);(out/'replays').mkdir(exist_ok=True)
    template=(Path(__file__).parent/'replay.html').read_text()
    rows=[]
    for task,r in zip(definitions,records,strict=True):
        if r['valid']:
            payload=json.dumps({'task':task,'record':r},ensure_ascii=False).replace('<','\\u003c')
            (out/'replays'/(task['id']+'.html')).write_text(template.replace('__PAYLOAD__',payload))
            link='<a href="replays/'+task['id']+'.html">'+escape(task['name'])+'</a>'
        else:link=escape(task['name'])
        rows.append('<tr><td>'+link+'</td><td>'+str(r['score'])+'</td><td>'+str(r.get('build_cost','—'))+'</td><td>'+escape(r.get('error','有效'))+'</td></tr>')
    body='<p>固定地图蓝图优化，使用原版 shapez 运输、加工、形状规则。每关 60 秒模拟时间；成绩为目标产品交付量，三关取均值。同分比较总建造成本。此任务不衡量未知地图泛化。</p>'
    body+='<p>均分 <strong>'+f'{result["score"]:.3f}'+'</strong> · 无效蓝图 '+str(result['failures'])+' · 总成本 '+str(result['total_cost'])+'</p>'
    body+='<table><tr><th>任务与回放</th><th>正确交付</th><th>建造成本</th><th>有效性</th></tr>'+''.join(rows)+'</table>'
    body+='<p><a href="result.json">完整结果与校验值</a> · <a href="tasks.json">固定任务</a></p>'
    (out/'index.html').write_text(page('shapez 工厂优化',body))
