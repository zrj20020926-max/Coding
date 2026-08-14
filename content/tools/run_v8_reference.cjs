'use strict';

const fs = require('fs');
const vm = require('vm');

if (process.argv.length !== 3) {
  process.stderr.write('usage: node run_v8_reference.cjs <source>\n');
  process.exit(2);
}

const input = fs.readFileSync(0, 'utf8').replace(/\r\n?/g, '\n').split('\n');
if (input.length && input[input.length - 1] === '') input.pop();
let cursor = 0;
const sandbox = Object.create(null);
const readline = () => (cursor < input.length ? input[cursor++] : undefined);
const print = (...values) => fs.writeSync(1, `${values.map(String).join(' ')}\n`);
Object.setPrototypeOf(readline, null);
Object.setPrototypeOf(print, null);
Object.freeze(readline);
Object.freeze(print);
Object.defineProperties(sandbox, {
  readline: { value: readline, writable: false, configurable: false },
  print: { value: print, writable: false, configurable: false },
});
const context = vm.createContext(sandbox, {
  name: 'javascript-v8-acm-reference-validation',
  codeGeneration: { strings: false, wasm: false },
});

try {
  const source = fs.readFileSync(process.argv[2], 'utf8');
  new vm.Script(source, { filename: 'solution-v8.js' }).runInContext(context);
} catch (error) {
  process.stderr.write(`reference execution failed: ${String(error.message || '')}\n`);
  process.exitCode = 1;
}
