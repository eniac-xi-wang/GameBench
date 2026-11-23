'use strict';
const readline=require('node:readline'), write=process.stdout.write.bind(process.stdout);
console.log=(...args)=>console.error(...args);
const policy=require(process.argv[2]), choose=policy.chooseAction || policy;
if (typeof choose!=='function') throw Error('Export chooseAction(observation)');
(async()=>{
  for await (const line of readline.createInterface({input:process.stdin})) {
    const {id,observation}=JSON.parse(line);
    write(JSON.stringify({id,action:await choose(observation)})+'\n');
  }
})().catch(e=>{console.error(e.stack);process.exit(1);});
