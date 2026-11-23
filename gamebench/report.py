from html import escape
from .common import ROOT, read, save

def page(title,body):
    return '<!doctype html><meta charset="utf-8"><title>'+escape(title)+'</title><style>body{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 20px;line-height:1.6}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}a{color:#1769aa}small{color:#666}</style><h1>'+escape(title)+'</h1>'+body

def render(root,report):
    rows=''
    for r in report['rows']:
        link='<a href="'+escape(r['replay'])+'">回放</a>' if r['replay'] else '—'
        rows+='<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in (r['system'],r['task_id'],r['repeat'],r['baseline'],r['score'],r['status'],r['execution']['termination']))+'<td>'+link+'</td></tr>'
    body='<p><b>本地开发验收，不进入正式排名。</b> 本页只验证统一工作流；本轮使用已保存提交或原始 baseline。</p>' if all(r['execution']['termination']=='manual_snapshot' for r in report['rows']) else '<p><b>本地开发结果，不进入正式排名。</b></p>'
    body+='<p>各任务独立评分；不合成跨游戏总分。所有预登记运行都保留。<a href="report.json">完整结果</a> · <a href="cohort.json">条件与系统配置</a></p><table><tr><th>系统</th><th>任务</th><th>重复</th><th>Baseline</th><th>提交</th><th>提交状态</th><th>结束原因</th><th>证据</th></tr>'+rows+'</table>'
    (root/'index.html').write_text(page('GameBench · 统一评测',body))
