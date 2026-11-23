const fs = require('fs');
const src = fs.readFileSync('apps/web/src/i18n/translations.ts', 'utf8');

function keysIn(name) {
  const start = src.indexOf('const ' + name + ' = {');
  if (start === -1) return [];
  let d = 0, i = start + ('const ' + name + ' = {').length;
  while (i < src.length) {
    const ch = src[i];
    if (ch === '{') d++;
    else if (ch === '}') {
      d--;
      if (d === 0) break;
    }
    i++;
  }
  const body = src.slice(start + ('const ' + name + ' = {').length, i);
  const out = [];
  const re = new RegExp("'\\s*([^']+?)\\s*':\\s*'((?:[^'\\\\]|\\\\.)*)'", 'g');
  let m;
  while ((m = re.exec(body))) out.push(m[1].trim());
  return out;
}

const en = keysIn('en');
const hi = keysIn('hi');
const te = keysIn('te');
console.log('raw key counts -> en:' + en.length + ' hi:' + hi.length + ' te:' + te.length);

const setEn = new Set(en);
const setHi = new Set(hi);
const setTe = new Set(te);
const union = [...new Set([...setEn, ...setHi, ...setTe])].sort();
console.log('union:', union.length);

const missEn = union.filter(k => !setEn.has(k));
const missHi = union.filter(k => !setHi.has(k));
const missTe = union.filter(k => !setTe.has(k));

console.log('MISSING_IN_EN (' + missEn.length + '):');
missEn.forEach(k => console.log('  ' + k));
console.log('MISSING_IN_HI (' + missHi.length + '):', missHi.join(', ') || 'none');
console.log('MISSING_IN_TE (' + missTe.length + '):', missTe.join(', ') || 'none');

// Verify canonical en file
const canon = fs.readFileSync('tmp/en-canonical.ts', 'utf8');
const canonRe = new RegExp("'\\s*([^']+?)\\s*':\\s*'((?:[^'\\]|\\.)*)'", 'g');
const canonKeys = [];
while ((m = canonRe.exec(canon))) canonKeys.push(m[1].trim());
console.log('canonical en keys:', canonKeys.length, 'missing from canonical vs union:', union.filter(k => !canonKeys.includes(k)).join(', ') || 'none');
console.log('union missing from canonical:', canonKeys.filter(k => !union.includes(k)).join(', ') || 'none');
