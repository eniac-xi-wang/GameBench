"""Create an offline original-client 2048 replay from a single recorded game."""
import argparse
import base64
from html import escape
import json
from pathlib import Path
import re


def export(game, record_file, output):
    record = json.loads(record_file.read_text())
    public = {k:record[k] for k in ('id','initial','steps','raw_score','score')}
    data = json.dumps(public,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    css = (game/'style/main.css').read_text()
    fonts = []
    for name,weight in [('Light',300),('Regular',400),('Bold',700)]:
        font = game/'style/fonts'/f'ClearSans-{name}-webfont.woff'
        encoded = base64.b64encode(font.read_bytes()).decode()
        fonts.append(f"@font-face{{font-family:'Clear Sans';font-weight:{weight};src:url(data:font/woff;base64,{encoded}) format('woff')}}")
    css = re.sub(r'@import\s+url\(fonts/clear-sans\.css\);','\n'.join(fonts),css)
    upstream = (game/'index.html').read_text()
    board = upstream[upstream.index('<div class="game-container">'):upstream.index('<p class="game-explanation">')]
    scripts = [(game/'js'/n).read_text() for n in ('tile.js','grid.js','game_manager.js','html_actuator.js')]
    scripts.append(Path(__file__).with_name('replay_2048.js').read_text())
    license_text = escape((game/'LICENSE.txt').read_text())
    html = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>2048 · 原版回放</title>
<style>{css}
body{{margin:28px 0}} .game-container{{margin-top:16px}} .controls{{margin:16px 0;display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
.controls button{{font:inherit;cursor:pointer}} #step{{flex:1;min-width:90px}} details{{margin-top:24px;font-size:12px}} pre{{white-space:pre-wrap}}
</style><main class="container"><div class="heading"><h1 class="title">2048</h1><div class="scores-container">
<div class="score-container">0</div><div class="best-container" title="该局达到的游戏得分">0</div></div></div>
<p id="status" aria-live="off"></p>{board}<div class="controls"><button id="prev">上一步</button><button id="play">播放</button>
<button id="next">下一步</button><input id="step" type="range" min="0" value="0" aria-label="回放步数"></div>
<details><summary>2048 · Gabriele Cirulli</summary><pre>{license_text}</pre></details></main>
<script id="record" type="application/json">{data}</script><script>{chr(10).join(scripts)}</script></html>'''
    with output.open('x',encoding='utf-8') as stream:
        stream.write(html)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record',type=Path,help='one engine/games/game-*.json file')
    parser.add_argument('output',type=Path,help='a new HTML file')
    parser.add_argument('--game-dir',type=Path,default=Path(__file__).resolve().parents[1]/'2048')
    args=parser.parse_args()
    try:export(args.game_dir,args.record,args.output)
    except (ValueError, KeyError, OSError) as e:parser.exit(1,str(e)+'\n')
