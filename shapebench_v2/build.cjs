'use strict';
// Bundle the pinned upstream simulation for Node, without browser presentation.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const esbuild=require('../tools/node_modules/esbuild');
const root=path.resolve(__dirname,'..'), upstream=path.join(root,'shapez/src/js');
const stubs={
 'core/loader.js': 'export const Loader={getSprite:()=>null};',
 'core/logging.js': 'export const createLogger=()=>({log(){},warn(){},debug(){},error(...x){console.error(...x)}});',
 'translations.js': 'export const T=new Proxy(function(){},{get:()=>T,apply:()=>""});',
 'platform/sound.js': 'export const SOUNDS={};',
};
const inputs={};
(async()=>{
 const result=await esbuild.build({entryPoints:[path.join(__dirname,'upstream-entry.js')],bundle:true,platform:'node',format:'cjs',target:'node24',write:false,metafile:true,
  define:{G_IS_DEV:'false',G_IS_STANDALONE:'false',G_IS_BROWSER:'false',G_IS_STEAM_DEMO:'false'},
  banner:{js:'const assert=(x,m)=>{if(!x)throw Error(m||"upstream assertion")}; const assertAlways=assert;'},
  plugins:[{name:'headless-presentation',setup(build){
   build.onResolve({filter:/^@nastyox\/rando\.js$/},()=>({path:'random',namespace:'headless'}));
   build.onResolve({filter:/^\.\/config\.local$/},()=>({path:'debug',namespace:'headless'}));
   build.onLoad({filter:/.*/,namespace:'headless'},({path:p})=>({contents:p==='debug'?'export default {};':'export function rando(){throw Error("Unexpected random call in fixed factory task")}'}));
   build.onLoad({filter:/\.js$/},async({path:file})=>{
    let source=fs.readFileSync(file,'utf8');
    if(file.startsWith(upstream+path.sep)){
     const rel=path.relative(upstream,file);inputs[rel]=crypto.createHash('sha256').update(source).digest('hex');
     if(stubs[rel])source=stubs[rel];
    }
    source=source.replace(/\/\* typehints:start \*\/[\s\S]*?\/\* typehints:end \*\//g,'');
    // TypeScript parsing removes imports referenced only by JSDoc, as the
    // upstream production pipeline does. Simulation bodies are not rewritten.
    return {contents:source,loader:'ts'};
   });
  }}]});
 const out=path.join(__dirname,'vendor');fs.mkdirSync(out,{recursive:true});
 const data=result.outputFiles[0].contents;fs.writeFileSync(path.join(out,'engine.cjs'),data);
 fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify({upstream_commit:'8a79de5255fb6756f3a1d26579b1e9bc36e0c811',esbuild:esbuild.version,inputs:Object.fromEntries(Object.entries(inputs).sort()),presentation_stubs:stubs,engine_sha256:crypto.createHash('sha256').update(data).digest('hex')},null,2)+'\n');
 console.log(JSON.stringify({modules:Object.keys(inputs).length,bytes:data.length}));
})().catch(e=>{console.error(e);process.exitCode=1});
