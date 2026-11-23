const fs = require('fs');
const s = fs.readFileSync('tmp/translations-generated.ts', 'utf8');

function keysOf(name) {
  const i = s.indexOf('const ' + name);
  const j = s.indexOf('{', i);
  let d = 0, p = j + 1;
  while (p < s.length) {
    const c = s.charAt(p);
    if (c === '{') d++;
    else if (c === '}') { d--; if (d === 0) break; }
    p++;
  }
  const body = s.slice(j + 1, p);
  const re = new RegExp("'([^'\\n]+?)'\\s*:", 'g');
  const out = [];
  let m;
  while ((m = re.exec(body))) out.push(m[1].trim());
  return out;
}

const en = keysOf('en');
const hi = keysOf('hi');
const te = keysOf('te');
const setEn = new Set(en), setHi = new Set(hi), setTe = new Set(te);
console.log('counts -> en:' + en.length + ' hi:' + hi.length + ' te:' + te.length);
const union = [...new Set(en.concat(hi).concat(te))].sort();
console.log('union:', union.length);
const missHi = union.filter(k => !setHi.has(k));
const missTe = union.filter(k => !setTe.has(k));
console.log('MISSING hi (' + missHi.length + '):', missHi.join(', ') || 'none');
console.log('MISSING te (' + missTe.length + '):', missTe.join(', ') || 'none');

// Which missing-in-hi keys are referenced in pages?
const pg = fs.readFileSync('apps/web/src/pages/LandingPage.tsx', 'utf8');
const usedInLanding = union.filter(k => new RegExp("'" + k.replace(/\./g, '\\.') + "'").test(pg));
console.log('union keys used in LandingPage.tsx (' + usedInLanding.length + '):');
usedInLanding.forEach(k => console.log('   ', k, ' -> hi missing:', !setHi.has(k), 'te missing:', !setTe.has(k)));
