'use strict';
const fs=require('node:fs'),{simulate}=require('./engine.cjs');
const payload=JSON.parse(fs.readFileSync(0,'utf8'));
const results=payload.cases.map(({task,blueprint})=>{
 try{return simulate(task,blueprint,{replay:payload.replay!==false});}
 catch(e){return {task_id:task.id,valid:false,score:0,error:e.message};}
});
process.stdout.write(JSON.stringify(results));
