'use strict';
// Runs in a separate OS-restricted process. It has no live Battle object or seed.
const readline = require('node:readline');
const write = process.stdout.write.bind(process.stdout);
console.log = (...args) => console.error(...args);
const policy = require(process.argv[2]);
const choose = policy.chooseAction || policy;
if (typeof choose !== 'function') throw Error('Export chooseAction(observation)');
const input = readline.createInterface({input: process.stdin});
(async () => {
  for await (const line of input) {
    const {id, observation} = JSON.parse(line);
    const action = await choose(observation);
    write(JSON.stringify({id, action}) + '\n');
  }
})();
