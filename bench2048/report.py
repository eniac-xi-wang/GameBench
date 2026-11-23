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

def render_experiment(root):
    root=Path(root);private=root/'private';summary=json.loads((private/'summary.json').read_text());state=json.loads((private/'state.json').read_text())
    manifest=json.loads((root/'manifest.json').read_text())
    if manifest['source_fingerprints']!=core.fingerprints():raise ValueError('evaluator changed')
    for name,sha in manifest['initial_task_files'].items():
        if core.digest((root/name).read_bytes())!=sha:raise ValueError('task input changed')
    readlines=lambda p:[json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
    messages=readlines(private/'harness/host-messages.jsonl');events=readlines(private/'harness/events.jsonl');delivered=[]
    for event in events:
        e=event.get('payload',{}).get('event',{})
        if e.get('type')=='agent/inbox/spliced':
            for item in e.get('data',{}).get('inserted',[]):
                value='\n'.join(c.get('text','') for c in item.get('content',[]) if c.get('type')=='text')
                if value:delivered.append(value)
    if delivered!=[x['text'] for x in messages]:raise ValueError('unexpected host message')
    from .contract import PROMPT,CONTINUATION
    if delivered and (not delivered[0].startswith(PROMPT+'\nInitial training result: ') or any(not t.startswith(CONTINUATION) for t in delivered[1:])):raise ValueError('nonstandard prompt')
    audit={'task_inputs_unchanged':True,'host_messages':len(delivered),'unexpected_host_messages':0,
           'baseline_sha256':core.spec()['baseline_sha256'],'budgets':core.spec()['budgets'],
           'message_sha256':[core.digest(t.encode()) for t in delivered],'model_run':bool(delivered)}
    core.save(root/'prompt-audit.json',audit)
    batches=[]
    for base in (private/'evaluator',private/'final'):
        for p in sorted(base.rglob('result.json')):
            v=p.parent/'verification.json'
            if not v.exists():raise ValueError('missing replay verification: '+str(p))
            checked=json.loads(v.read_text());result=json.loads(p.read_text())
            if not checked['valid'] or checked['checked']!=result['games']:raise ValueError('verification failed')
            batches.append({'path':str(p.parent.relative_to(root)),**checked})
    core.save(root/'verification-audit.json',{'valid':True,'batches':len(batches),'games':sum(x['checked'] for x in batches),'results':batches})
    history=readlines(private/'history.jsonl');changes=[]
    a=private/'initial-candidate';b=private/'final/candidate'
    for name in sorted(set(core.bundle_hashes(a))|set(core.bundle_hashes(b))):
        x=(a/name).read_text() if (a/name).exists() else '';y=(b/name).read_text() if (b/name).exists() else ''
        changes.extend(difflib.unified_diff(x.splitlines(True),y.splitlines(True),fromfile='initial/'+name,tofile='selected/'+name))
    (root/'selected.diff').write_text(''.join(changes))
    local=[]
    for p in (root/'agent/work').rglob('result.json'):
        try:r=json.loads(p.read_text())
        except (ValueError,OSError):continue
        if r.get('protocol')==core.spec()['protocol'] and 'games' in r:local.append({'path':str(p.parent.relative_to(root)),**core.public(r)})
    train={s['key'] for p in (private/'evaluator/trials').glob('*/scenarios.json') for s in json.loads(p.read_text())}
    validation={s['key'] for s in json.loads((private/'validation-scenarios.json').read_text())}
    test={s['key'] for s in json.loads((private/'final/test-scenarios.json').read_text())}
    if train&validation or train&test or validation&test:raise ValueError('split overlap')
    for item in local:
        keys={s['key'] for s in json.loads((root/item['path']/'scenarios.json').read_text())}
        if keys&(validation|test):raise ValueError('local/hidden overlap')
    research_seconds=json.loads((private/'final/freeze.json').read_text())['frozen_at']-state['started_at']
    core.save(root/'analysis.json',{'summary':summary,'local_runs':local,'history':history,'prompt_audit':audit,
        'research_seconds':research_seconds,'disjoint_random_keys':True,'verified_batches':batches})
    test_result=summary['test'];initial=test_result['initial'];selected=test_result['selected'];delta=test_result['difference']
    title='2048 · 中性 Agent 程序优化'
    body='<p>完整源码与开发工具 · 固定原始 greedy 起点 · 固定预算 · Agent 自选方法</p>'
    body+=table(['程序','验证均分','新测试均分','2048 达成率','4096 达成率','测试失败'],[
        ['起始 greedy',f'{summary["initial_validation"]["score"]:,.1f}',f'{initial["score"]:,.1f}',f'{initial["tile_rates"]["2048"]:.1%}',f'{initial["tile_rates"]["4096"]:.1%}',initial['failures']],
        ['选定程序',f'{state["validation_results"][summary["selected_trial"]]["score"]:,.1f}',f'{selected["score"]:,.1f}',f'{selected["tile_rates"]["2048"]:.1%}',f'{selected["tile_rates"]["4096"]:.1%}',selected['failures']]])
    lo,hi=delta['paired_ci95'];body+=f'<p>同批 {initial["games"]} 局测试配对提升：{delta["score_delta"]:+,.1f} 分；95% 区间 [{lo:+,.1f}, {hi:+,.1f}]。</p>'
    body+='<p>主指标是每局最多 2000 步下的原始得分均值；达到 2048 后继续。程序失败计零分，行动上限保留分数。测试随机流仅在冻结后生成，私有 HMAC 随机源与策略进程分离。相同随机流不代表不同策略获得相同落子位置。</p>'
    body+=f'<p>实际研究 {research_seconds/60:.1f} 分钟；{summary.get("successful_model_requests",0)} 次模型请求；{state["executions"]} 次开发命令。结束原因 {escape(summary["stop_reason"])}；版本 {escape(summary["selected_trial"])}；主动提交 {summary["agent_submitted"]}。未提交时按验证最高分自动选定，同分取较早版本。</p>'
    body+='<h2>正式迭代记录</h2>'+table(['版本','阶段','均分','同批 baseline','配对提升'],[[h['trial_id'],h['phase'],f'{h["score"]:,.1f}',f'{h["baseline"]["score"]:,.1f}',f'{h["vs_baseline"]["score_delta"]:+,.1f}'] for h in history])
    body+=f'<h2>审计</h2><p>实际宿主消息 {len(delivered)} 条，与中性任务模板相符。任务材料与评测指纹未变；训练、验证、测试随机键互不重复。全部 {len(batches)} 个正式批次、{sum(x["checked"] for x in batches)} 局重放通过。</p>'
    body+='<pre>'+escape(PROMPT)+'</pre><h2>已记录本地实验</h2>'+table(['批次','局数','均分','失败'],[[escape(x['path']),x['games'],f'{x["score"]:,.1f}',x['failures']] for x in local])
    body+='<p><a href="private/final/selected/index.html">选定程序测试回放</a> · <a href="private/final/initial/index.html">基线测试回放</a> · <a href="selected.diff">全部程序差异</a> · <a href="agent/task/instructions.md">任务契约</a> · <a href="prompt-audit.json">提示审计</a> · <a href="analysis.json">分析记录</a></p>'
    (root/'index.html').write_text(page(title,body))
