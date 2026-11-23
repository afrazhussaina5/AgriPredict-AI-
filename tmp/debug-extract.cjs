const fs = require('fs');
const src = fs.readFileSync('apps/web/src/i18n/translations.ts', 'utf8');

function extractBlock(name) {
  const candidates = [
    'const ' + name + ' = {',
    'const ' + name + ': Record<TranslationKey, string> = {',
  ];
  let start = -1, matched = null;
  for (const c of candidates) {
    const idx = src.indexOf(c);
    if (idx !== -1) { start = idx; matched = c; break; }
  }
  if (start === -1) return null;
  let depth = 0, i = start + matched.length;
  while (i < src.length) {
    const ch = src[i];
    if (ch === '{') depth += 1;
    else if (ch === '}') {
      depth -= 1;
      if (depth === 0) break;
    }
    i += 1;
  }
  return src.slice(start + matched.length, i);
}

const body = extractBlock('hi');
console.log('body.length', body.length);

const keyRe = new RegExp("'([^'\\n]+?)'\\s*:\\s*", 'g');
const out = {};
let m;
let count = 0;
while ((m = keyRe.exec(body))) {
  const k = m[1].trim();
  if (!k) continue;
  const colonEnd = m.index + m[0].length;
  const opening = body.charAt(colonEnd);
  if (opening !== "'") {
    console.log('SKIP no quote after key "' + k + '" at', colonEnd, 'got:', JSON.stringify(opening));
    continue;
  }
  let j = colonEnd + 1;
  let val = '';
  while (j < body.length) {
    const c = body.charAt(j);
    if (c === '\\' && j + 1 < body.length) {
      val += c + body.charAt(j + 1);
      j += 2;
      continue;
    }
    if (c === "'") break;
    val += c;
    j += 1;
  }
  out[k] = val;
  count++;
  if (count <= 4) console.log('OK', count, 'key:', k, '| val:', val.slice(0, 50));
}
console.log('parsed count:', Object.keys(out).length);
console.log('landing.roles.farmer.name ->', JSON.stringify(out['landing.roles.farmer.name']));
console.log('landing.hero.title ->', JSON.stringify(out['landing.hero.title']));
console.log('common.brandTagline ->', JSON.stringify(out['common.brandTagline']));
