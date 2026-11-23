from html import escape
from .common import ROOT, read, save

def page(title,body):
    return '<!doctype html><meta charset="utf-8"><title>'+escape(title)+'</title><style>body{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 20px;line-height:1.6}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}a{color:#1769aa}small{color:#666}</style><h1>'+escape(title)+'</h1>'+body

def render(root,report):
    rows=''
    for r in report['rows']:
        link='<a href="'+escape(r['replay'])+'">回放</a>' if r['replay'] else '—'
        rows+='<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in (r['system'],r['task_id'],r['repeat'],r['baseline'],r['score'],r['status']))+'<td>'+link+'</td></tr>'
    body='<p><b>本地开发验收，不进入正式排名。</b> 本页只验证统一工作流；没有执行新的模型研究。</p>' if all(r['execution']['termination']=='manual_snapshot' for r in report['rows']) else '<p><b>本地开发结果，不进入正式排名。</b></p>'
    body+='<p>各任务独立评分；不合成跨游戏总分。所有预登记运行都保留。<a href="report.json">完整结果</a> · <a href="cohort.json">条件与系统配置</a></p><table><tr><th>系统</th><th>任务</th><th>重复</th><th>Baseline</th><th>提交</th><th>状态</th><th>证据</th></tr>'+rows+'</table>'
    (root/'index.html').write_text(page('GameBench · 统一评测',body))

def history(out):
    """An inventory, deliberately not a leaderboard or recalculated score."""
    out.mkdir(parents=True,exist_ok=True);items=[]
    for p in sorted((ROOT/'experiments').iterdir()):
        if not p.is_dir() or p.resolve()==out.resolve():continue
        markers=[str(x.relative_to(ROOT)) for name in ('manifest.json','private/summary.json','acceptance.json','index.html') if (x:=p/name).exists()]
        if not markers:continue
        items.append({'experiment':p.name,'category':'historical exploratory / acceptance',
                      'ranking_eligible':False,'artifacts':markers,
                      'reason':'not registered under the common system protocol; budgets, prompts, harness or selection may differ'})
    save(out/'history.json',items)
    import os
    rows=''.join('<tr><td>'+escape(x['experiment'])+'</td><td>历史探索 / 验收</td><td>'+ ' · '.join('<a href="'+escape(os.path.relpath(ROOT/a,out))+'">'+escape(a.split('/')[-1])+'</a>' for a in x['artifacts'])+'</td></tr>' for x in items)
    (out/'index.html').write_text(page('GameBench · 历史实验索引','<p>这些结果保留为研究材料，不与新协议结果混排。配置差异必须查各自原始记录。</p><table>'+rows+'</table>'))
    return {'experiments':len(items),'index':str(out/'index.html')}
