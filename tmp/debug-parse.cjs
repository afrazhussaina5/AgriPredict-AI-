const fs = require('fs');
const src = fs.readFileSync('apps/web/src/i18n/translations.ts', 'utf8');

function extractBlock(name) {
  const BS = String.fromCharCode(92);
  const c1 = 'const ' + name + ' = {';
  const c2 = 'const ' + name + ': Record<TranslationKey, string> = {';
  const i1 = src.indexOf(c1);
  const i2 = src.indexOf(c2);
  const start = i1 !== -1 ? i1 : i2;
  if (start === -1) return null;
  const labelEnd = start + (i1 !== -1 ? c1.length : c2.length);
  let i = labelEnd, inS = false, inD = false, depth = 0;
  while (i < src.length) {
    const c = src[i];
    if (inS) {
      if (c === BS + '\\' && i + 1 < src.length) { i += 2; continue; }
      if (c === "'") inS = false;
      i += 1; continue;
    }
    if (inD) {
      if (c === BS + '\\' && i + 1 < src.length) { i += 2; continue; }
      if (c === '"') inD = false;
      i += 1; continue;
    }
    if (c === "'") { inS = true; i += 1; continue; }
    if (c === '"') { inD = true; i += 1; continue; }
    if (c === '{') { depth += 1; i += 1; continue; }
    if (c === '}') {
      depth -= 1;
      if (depth === 0) break;
      i += 1; continue;
    }
    i += 1;
  }
  const body = src.slice(labelEnd, i);
  return body;
}

const body = extractBlock('en');
console.log('body length:', body.length);
console.log('first 200:', JSON.stringify(body.slice(0, 200)));

const BS = String.fromCharCode(92);
const keyRe = new RegExp("'([^'" + BS + "n]+?)'" + BS + "s*:" + BS + "s*", 'g');
let m;
let count = 0;
while ((m = keyRe.exec(body))) {
  count++;
  if (count <= 3) console.log('match', count, 'key:', m[1].trim(), 'end:', m.index + m[0].length, 'char:', JSON.stringify(body.charAt(m.index + m[0].length)));
}
console.log('total keyRe matches:', count);
