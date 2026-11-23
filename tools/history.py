"""Render the public tables, optionally re-extract allowlisted fields from the original archive."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'results'
SYSTEMS = {'baseline':'原始启发式', 'sol':'GPT-6.1 Sol / Codex', 'deepseek':'DeepSeek Flash / 官方 SDK',
           'deepseek_claude':'DeepSeek Flash / Claude Code', 'qwen_claude':'Qwen3.8-Max / Claude Code',
           'qwen_code':'Qwen3.8-Max / Qwen Code'}


def extract(archive):
    sources = {}
    sections = []
    def load(file):
        raw = (archive/file).read_bytes()
        sources[file] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)
    def section(title, columns, files, note):
        rows = []
        sections.append(dict(title=title, columns=columns, rows=rows, sources=files, note=note))
        return rows
    path = 'experiments/showdown-deepseek-claude-v1/summary.json'
    d = load(path)
    rows = section('Pokémon Showdown · 同批独立测试', ['系统','场数','得分率','相对 baseline（百分点）','策略失败','达回合上限'], [path],
        '6 个分层、5 个公开对手、96 对队伍。每个程序 1,920 场，每个 Agent 系统一次研究。胜 1，平 0.5，负 0。')
    for k, name in SYSTEMS.items():
        v = d['overall'][k]
        rows.append([name,v['games'],v['score'],100*(v['score']-d['overall']['baseline']['score']),v['failures'],v['turn_limits']])
    rows = section('Showdown · 同一提交按分层拆分', ['分层']+list(SYSTEMS.values()), [path], '每个分层 320 场，同一系统的六行来自同一个程序。')
    for v in d['profiles']:
        rows.append([v['profile']]+[v['scores'][k] for k in SYSTEMS])
    rows = section('Showdown · 配对差值', ['对照','差值（百分点）','95% 下界','95% 上界'], [path],
        '同队伍对在各分层内重采样。区间描述这批对战带来的不确定性；系统间重复研究的方差未知。')
    for k,v in d['comparisons'].items():
        rows.append(['DeepSeek / Claude Code 相对 '+SYSTEMS[k.removeprefix('deepseek_claude_vs_')],100*v['delta'],*[100*x for x in v['conditional_pair_bootstrap_ci95']]])
    early = ['experiments/showdown-pilot-v1/private/summary.json','experiments/showdown-generalization-v2/private/final/comparison.json',
             'experiments/showdown-neutral-v3/private/final/comparison.json','research/showdown-effect-v1/comparison.json']
    rows = section('Showdown · 早期协议与迁移', ['协议','场数','起点得分率','冻结程序得分率','启发式得分率'], early,
        '每行是自己的配对测试。首轮开发集的 91.67% 与该行独立测试使用不同队伍和种子。')
    for i,f in enumerate(early[:3]):
        v=load(f)
        if i==0:v=v['heldout']
        rows.append([['固定开发集','轮换训练阵容','中性提示'][i],v['selected']['games'],v['initial']['score'],v['selected']['score'],v.get('heuristic',v['initial'])['score']])
    v=load(early[3])['overall_descriptive_only']
    rows.append(['旧提交迁移到扩充分布',v['games_per_program'],v['baseline'],v['optimized'],v['baseline']])
    files=[f'experiments/showdown-{n}/summary.json' for n in ('native-expanded-v1','sol-native-v1','qwen-native-v1','qwen-claude-v1')]
    rows=section('Showdown · 扩充分布的历次抽样', ['实验批次','程序','场数','得分率'], files,
        '各批次使用当时的独立抽样或已冻结对照。相同程序可出现多次，这些行不计为新的 Agent 研究重复。')
    for i,f in enumerate(files):
        v=load(f)
        if i==0:
            scores={'baseline':v['overall']['baseline'],'deepseek':v['overall']['optimized']}
            games=v['overall']['games_per_program']
        elif i==1:
            scores={'baseline':v['sol_vs_baseline']['baseline'],'sol':v['sol_vs_baseline']['optimized'],
                    'deepseek':v['deepseek_vs_baseline']['optimized']}
            games=v['sol_vs_baseline']['games_per_program']
        else:
            scores={k:x['score'] for k,x in v['overall'].items()}
            games=v['overall']['baseline']['games']
        for k,score in scores.items():rows.append([f.split('/')[1],SYSTEMS[k],games,score])
    files=['runs/showdown-baselines-v1/summary.json','runs/showdown-baselines-v2/summary.json']
    rows=section('Showdown · 简单策略对照', ['批次','策略','场数','得分率'],files,'旧对手池和队伍配置的校准数据。')
    for f in files:
        for v in load(f):rows.append([f.split('/')[1],v['policy'],v['games'],v['score']])
    cel = ['runs/celeste-100m-demo/trial-0001/result.json','runs/celeste-100m-demo/summary.json',
           'experiments/celeste-100m/deepseek-research-008/private/summary.json','experiments/celeste-suite-v2/results.json',
           'experiments/celeste-suite-dev-v3/results.json']
    rows = section('Celeste Classic · 固定入口', ['关卡','系统或对照','起点（帧）','最终（帧）'], cel,
        '帧数越低越好。100m 宿主删除搜索用了 120 次试跑。其余四关的起点取自上游输入记录，最优性未知。')
    rows.append(['100m','宿主删除搜索',load(cel[0])['completion_frames'],load(cel[1])['best_frames']])
    v=load(cel[2]);rows.append(['100m','DeepSeek / research-008',v['baseline_frames'],v['best_frames']])
    for f,label in zip(cel[3:], ['受限环境 v2','开发环境 v3']):
        for v in load(f)['rooms']:
            rows.append([str(v['altitude_m'])+'m','DeepSeek / '+label,v['baseline_frames'],v['verified_best_frames']])
    f='experiments/2048-neutral-v1/private/final/comparison.json'
    v=load(f)
    rows=section('2048 · 独立测试', ['策略','局数','平均得分','失败局数'], [f], '每局最多 2,000 步，相同随机流。')
    for key,name in [('initial','贪心 baseline'),('selected','DeepSeek 冻结程序')]:
        rows.append([name,v[key]['games'],v[key]['score'],v[key]['failures']])
    f='runs/2048-baselines-v1/comparison.json'
    rows=section('2048 · 简单策略对照',['策略','局数','平均得分','失败局数'],[f],'同一次基线校准的随机、固定优先级和贪心策略。')
    for k,v in load(f).items():rows.append([k,v['games'],v['score'],v['failures']])
    f='research/2048-upstream-comparison/stable-rerun/comparison.json'
    rows=section('2048 · 同批预算复测', ['策略','局数','平均得分','失败局数'], [f],
        '人工参考使用 C++ 封装；原 Agent 接口只公开支持 JavaScript。超限局记零。阈值参考 126/128 局触及步数上限。')
    for k,v in load(f)['results'].items():
        rows.append([k,v['games'],v['score'],v['failures']])
    files=[f'experiments/shapez-{tag}/private/summary.json' for tag in ('neutral-v1','neutral-v2','extended-v1','native-v1')]
    rows=section('shapez · 固定地图', ['运行','切割','染色','堆叠'], files,
        '每格为 60 秒正确交付数。延长预算沿用前轮工作；官方 Harness 轮从原 baseline 重启。未提交方案不计分。')
    for i,f in enumerate(files):
        v=load(f)
        for key in (['initial','final'] if i==0 else ['final']):
            scores={t['task_id']:t['score'] for t in v[key]['tasks']}
            rows.append([('原始 baseline' if key=='initial' else f.split('/')[1]),*[scores[k] for k in ('cut_rotate','paint','stack')]])
    files=['research/shapez-unsubmitted-v1/result.json','research/shapez-optimality-check-v1/evaluation/result.json',
           'research/shapez-unsubmitted-v2/result.json','research/shapez-stack-audit-v1/counterfactual/result.json']
    rows=section('shapez · 未提交方案与人工对照',['产物','任务','复评交付数'],files,'这些复评说明已发现的可行解；正式提交仍按上表计分。')
    for f,label,task in zip(files,['早期未提交切割','宿主缩短切割路径','后续未提交切割','未提交堆叠布局'],
                            ['cut_rotate','cut_rotate','cut_rotate','stack']):
        d=load(f)
        score=next(t['score'] for t in d['tasks'] if t['task_id']==task) if 'tasks' in d else d['score']
        rows.append([label,task,score])
    f='research/mindustry-replay-fix-v2/reevaluation/summary.json'
    rows=section('Mindustry · 基础生产 v2', ['产品','地图数','原始 baseline','DeepSeek 冻结蓝图'], [f],
        '回放修复后用原提交重评，每种蓝图每图独立重评五次，按四图平均。')
    v=load(f)
    for k,item in v['families'].items():
        rows.append([k,sum(t['family']==k for t in v['tasks']),item['baseline_mean'],item['final_mean']])
    rows=section('Mindustry · 基础生产逐图复评',['地图','产品','原始 baseline','DeepSeek 冻结蓝图'],[f],'对应上一表的 12 张地图。')
    for item in v['tasks']:
        rows.append([item['task_id'],item['family'],item['baseline']['score'],item['final']['score']])
    f='runs/mindustry-qwen-claude-v2/execution-audit.json';v=load(f)
    rows=section('Mindustry · 中断运行', ['系统','地图数','提交与起点逐字节相同','独立最终评测数'], [f],
        '用户报告额度用尽，日志没有记录明确的额度错误。这一轮单列。')
    rows.append(['Qwen3.8-Max / Claude Code',v['task_count'],v['all_submissions_byte_identical_to_original_baseline'],v['independent_final_evaluations']])
    f='research/mindustry-complex-production-v3/acceptance/acceptance.json'
    rows=section('Mindustry · 复杂生产 v3', ['任务','原始 baseline','人工双线布局'], [f],
        '复杂链只完成人工可行性验收。每个布局三次改变 JSON 排列顺序，并逐次核对回放，模型调用为零。')
    for t in load(f)['tasks']:
        rows.append([t['id'],t['baseline']['score'],t['witness']['score']])
    return {'schema':1,'scope':'historical experiments and controls','sources_sha256':sources,'tables':sections}


def render(data):
    lines=['# 历史实验结果','',
        '数值取自原始实验与冻结提交复评。以下各节保留各自协议、场数与计分单位。JSON 保存未舍入数值和原汇总的 SHA-256。 [数据与出处](historical.json)','']
    for table in data['tables']:
        lines += ['## '+table['title'],'',table['note'],'','| '+' | '.join(table['columns'])+' |','| '+' | '.join(['---']*len(table['columns']))+' |']
        for row in table['rows']:
            cells=[]
            for i,val in enumerate(row):
                if (('得分率' in table['columns'][i]) or (table['title'].endswith('按分层拆分') and i>0)):
                    val=f'{100*val:.2f}%'
                elif isinstance(val,bool):val='是' if val else '否'
                elif isinstance(val,float):val=f'{val:,.2f}'
                cells.append(str(val))
            lines.append('| '+' | '.join(cells)+' |')
        lines += ['','原汇总：'+ '、'.join('`'+f+'`' for f in table['sources'])+'。','']
    return '\n'.join(lines)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,help='original private research workspace; writes only selected numeric fields and source hashes')
    p.add_argument('--check',action='store_true',help='compare in memory, leave files unchanged')
    args=p.parse_args()
    path=FOLDER/'historical.json'
    data=extract(args.archive) if args.archive else json.loads(path.read_text())
    outputs={FOLDER/'RESULTS.md':render(data)}
    if args.archive:
        outputs[path]=json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
    for dest,content in outputs.items():
        if args.check:
            if dest.read_text()!=content:p.exit(1,f'Stale: {dest}\n')
        else:
            dest.parent.mkdir(exist_ok=True)
            dest.write_text(content)
