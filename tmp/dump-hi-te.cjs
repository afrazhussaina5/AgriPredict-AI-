const fs = require('fs');
const src = fs.readFileSync('apps/web/src/i18n/translations.ts', 'utf8');

function extractBlock(name) {
  const candidates = [
    'const ' + name + ' = {',
    'const ' + name + ': Record<TranslationKey, string> = {',
  ];
  let start = -1;
  for (const cand of candidates) {
    const idx = src.indexOf(cand);
    if (idx !== -1) { start = idx; break; }
  }
  if (start === -1) return null;
  if (start === -1) return null;
  let depth = 0;
  // Use the ACTUAL matched candidate length so the body slicing is correct.
  const matched = candidates.find(c => src.indexOf(c) === start) ?? candidates[0];
  let i = start + matched.length;
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

function parseKeyValueBody(body) {
  const out = {};
  // Match: 'key' : 'value'
  // Value is a single-quoted string literal possibly containing escaped quotes.
  // We'll scan for occurrences of 'key' : and then capture the quoted value.
  const keyRe = /'([^'\\n]+?)'\s*:\s*/g;
  let m;
  let lastIdx = 0;
  while ((m = keyRe.exec(body))) {
    const k = m[1].trim();
    if (!k) continue;
    // find the opening quote of the value
    const colonEnd = m.index + m[0].length;
    if (body.charAt(colonEnd) !== "'") continue;
    // capture until the closing unescaped quote
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
    lastIdx = j;
  }
  return out;
}

const hiBody = extractBlock('hi');
const teBody = extractBlock('te');
const hi = hiBody ? parseKeyValueBody(hiBody) : {};
const te = teBody ? parseKeyValueBody(teBody) : {};

console.log('hi keys:', Object.keys(hi).length);
console.log('te keys:', Object.keys(te).length);

fs.writeFileSync(__dirname + '/hi-values.json', JSON.stringify(hi, null, 2));
fs.writeFileSync(__dirname + '/te-values.json', JSON.stringify(te, null, 2));

// show a few keys that we know exist (farmer.name etc.)
['landing.roles.farmer.name', 'landing.roles.buyer.name', 'landing.roles.transport.name', 'landing.roles.storage.name', 'landing.roles.admin.name'].forEach(k => {
  console.log(k);
  console.log('  hi:', JSON.stringify(hi[k]));
  console.log('  te:', JSON.stringify(te[k]));
});
