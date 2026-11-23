"""Minimal official SDK adapter. Keep native profile, tools and generation defaults."""
import importlib.metadata, json, os, sys
from dataclasses import asdict
from pathlib import Path

def main():
    from deepseek_harness import DeepSeekHarness
    work=Path(sys.argv[1]);instruction=Path(sys.argv[2]);state=work.parent/'native-harness'
    state.mkdir()
    options={'cwd':str(work),'dsh_home':str(state),'api_key':os.environ['DEEPSEEK_API_KEY'],
             'model':os.environ['GAMEBENCH_SYSTEM_MODEL']}
    if os.environ.get('DEEPSEEK_BASE_URL'):options['base_url']=os.environ['DEEPSEEK_BASE_URL']
    with DeepSeekHarness(**options) as h:
        metadata={'sdk_version':importlib.metadata.version('deepseek-harness-sdk'),
                  'profile':h.config.profile,'patches':h.config.patches,'max_tokens':h.config.max_tokens,
                  'benchmark_generation_overrides':{},'benchmark_tool_overrides':{}}
        (state/'config.json').write_text(json.dumps(metadata,indent=2))
        session=h.start_session()
        def notification(event):
            with (state/'events.jsonl').open('a') as f:f.write(json.dumps(asdict(event),ensure_ascii=False)+'\n')
        result=session.run(instruction.read_text(),on_notification=notification)
        (state/'final.txt').write_text(result.final_response or '')
        (state/'termination.json').write_text(json.dumps({'finish_reason':result.finish_reason}))

if __name__=='__main__':main()
