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

def render_experiment(root,summary):
    root=Path(root);initial=summary['initial'];final=summary['final'];rows=[]
    for a,b in zip(initial['tasks'],final['tasks'],strict=True):
        name=b['task_id'];rows.append('<tr><td><a href="private/final/selected/replays/'+name+'.html">'+escape(name)+'</a></td><td>'+str(a['score'])+'</td><td>'+str(b['score'])+'</td><td>'+str(b.get('build_cost','—'))+'</td></tr>')
    body='<p>Agent 自主优化三个固定工厂蓝图，使用中性任务说明、完整源码与开发工具。生成器语言不限，正式裁判只接收蓝图数据。这是固定实例优化，不是未知地图泛化实验。</p>'
    body+='<p>起点均分 <strong>'+str(initial['score'])+'</strong> → 最终 <strong>'+str(final['score'])+'</strong>；选定 '+escape(summary['selected_trial'])+'；最终结构失败 '+str(final['failures'])+'。</p>'
    body+='<table><tr><th>任务与回放</th><th>起点交付量</th><th>最终交付量</th><th>最终成本</th></tr>'+''.join(rows)+'</table>'
    body+='<p>模型成功请求 '+str(summary['successful_model_requests'])+' 次；正式评测 '+str(summary['status']['evaluations'])+' 次。全部 '+str(len(summary['verified_trials']))+' 个已完成快照均从空库存独立重新模拟核对。</p>'
    body+='<p>结束原因：'+escape(summary['stop_reason'])+'；模型主动提交：'+('是' if summary['agent_submitted'] else '否，按预设规则选择最佳有效已评测快照')+'；结束时剩余时间 '+str(summary['status']['remaining_seconds'])+' 秒、请求 '+str(summary['status'].get('provider_requests_remaining','—'))+' 次。续接不刷新预算，也没有单独次数上限。</p>'
    body+='<p><a href="private/summary.json">完整结果</a> · <a href="agent/task/instructions.md">模型所见任务说明</a> · <a href="private/final/selected/index.html">最终评分与回放</a></p>'
    (root/'index.html').write_text(page('shapez · Agent 多轮工厂优化',body))
