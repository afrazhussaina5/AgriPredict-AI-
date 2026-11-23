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
  return { body: src.slice(start + matched.length, i), end: i };
}

for (const name of ['en', 'hi', 'te']) {
  const r = extractBlock(name);
  console.log('==== ' + name + ' (body length ' + (r ? r.body.length : -1) + ') ====')
  if (r) console.log(r.body.slice(0, 600));
  console.log('');
}
