const fs = require('fs');
const src = fs.readFileSync('apps/web/src/i18n/translations.ts', 'utf8');
const BS = String.fromCharCode(92);

function extractBlock(name, debug) {
  const c1 = 'const ' + name + ' = {';
  const c2 = 'const ' + name + ': Record<TranslationKey, string> = {';
  const i1 = src.indexOf(c1);
  const i2 = src.indexOf(c2);
  const start = i1 !== -1 ? i1 : i2;
  if (start === -1) return null;
  const labelEnd = start + (i1 !== -1 ? c1.length : c2.length);
  let i = labelEnd, inS = false, inD = false, depth = 1; // already inside opening {
  let steps = 0;
  while (i < src.length) {
    const c = src[i];
    if (debug && steps < 5) console.log('step', steps, 'i=' + i, 'c=' + JSON.stringify(c), 'inS=' + inS, 'inD=' + inD, 'depth=' + depth);
    steps++;
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
      if (debug && depth === 0) console.log('CLOSING } at i=' + i + ' depth now 0');
      if (depth === 0) break;
      i += 1; continue;
    }
    i += 1;
  }
  if (debug) console.log('final i=' + i + ' totalLen=' + src.length + ' bodyLen=' + (i - labelEnd));
  return src.slice(labelEnd, i);
}

console.log('--- en block ---');
const enBody = extractBlock('en', true);
console.log('en body len:', enBody.length);
console.log('--- hi block ---');
const hiBody = extractBlock('hi', false);
console.log('hi body len:', hiBody.length);
