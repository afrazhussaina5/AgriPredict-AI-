const fs = require('fs');

const src = fs.readFileSync(
  __dirname + '/../apps/web/src/i18n/translations.ts',
  'utf8'
);

// ---- string-aware block extractor ----
function extractBlock(name) {
  const c1 = 'const ' + name + ' = {';
  const c2 = 'const ' + name + ': Record<TranslationKey, string> = {';
  const i1 = src.indexOf(c1);
  const i2 = src.indexOf(c2);
  const start = i1 !== -1 ? i1 : i2;
  if (start === -1) return null;
  const labelEnd = start + (i1 !== -1 ? c1.length : c2.length);
  let i = labelEnd, inS = false, inD = false, depth = 1; // we are already inside the opening {
  while (i < src.length) {
    const c = src[i];
    if (inS) {
      if (c === '\\' && i + 1 < src.length) { i += 2; continue; }
      if (c === "'") inS = false;
      i += 1; continue;
    }
    if (inD) {
      if (c === '\\' && i + 1 < src.length) { i += 2; continue; }
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

function parseBody(body) {
  const out = {};
  // match 'key' :
  const BS = String.fromCharCode(92);
  const BS2 = String.fromCharCode(92);
  const keyRe = /'([^'\n]+?)'\s*:\s*/g;
  let m;
  let cnt = 0;
  while ((m = keyRe.exec(body))) {
    cnt++;
    if (cnt <= 2) console.log('MATCH', cnt, 'key=', m[1].trim(), 'charAtE=', JSON.stringify(body.charAt(m.index + m[0].length)));
    const k = m[1].trim();
    if (!k) continue;
    const e = m.index + m[0].length;
    const opener = body.charAt(e);
    if (opener !== "'" && opener !== '"') { if (cnt <= 2) console.log('  SKIP no quote at e'); continue; }
    let j = e + 1, val = '';
    const closer = opener;
    let hitClose = false;
    while (j < body.length) {
      const c = body.charAt(j);
      if (c === BS2 + '\\' && j + 1 < body.length) { val += c + body.charAt(j + 1); j += 2; continue; }
      if (c === closer) { hitClose = true; break; }
      val += c; j += 1;
    }
    if (cnt <= 3) console.log('  key=', JSON.stringify(k), 'opener=', JSON.stringify(opener), 'val=', JSON.stringify(val.slice(0, 30)), 'hitClose=', hitClose, 'valLen=', val.length);
    out[k] = val;
  }
  if (cnt === 0) console.log('NO MATCHES. body[0:80]=', JSON.stringify(body.slice(0, 80)));
  console.log('parseBody returning, out keys=', Object.keys(out).length);
  return out;
}

const enRaw = parseBody(extractBlock('en'));
const hiRaw = parseBody(extractBlock('hi'));
const teRaw = parseBody(extractBlock('te'));

console.log('extracted -> en:' + Object.keys(enRaw).length +
            ' hi:' + Object.keys(hiRaw).length +
            ' te:' + Object.keys(teRaw).length);

// ---- canonical en = deduped, sorted, every key once ----
const enKeys = Object.keys(enRaw).sort();
const en = {};
enKeys.forEach(k => { en[k] = enRaw[k]; });
console.log('canonical en keys:', enKeys.length);

// ---- ensure hi/te have every en key (fallback to en) ----
const missingInHi = enKeys.filter(k => !(k in hiRaw));
const missingInTe = enKeys.filter(k => !(k in teRaw));
console.log('missing in hi (fallback en):', missingInHi.length, '(' + missingInHi.join(', ') + ')');
console.log('missing in te (fallback en):', missingInTe.length, '(' + missingInTe.join(', ') + ')');

function blockLines(existing) {
  return enKeys.map(k => {
    const v = (k in existing && existing[k] !== undefined) ? existing[k] : en[k];
    return "  '" + k + "': " + JSON.stringify(v);
  }).join(",\n");
}

const header = `import type { Locale } from '../appInfo'

/* Translation resources for English, Hindi and Telugu.
   Rules:
   - Flat dot-separated keys; \`en\` is the source of truth for the key set.
   - \`hi\` and \`te\` are typed against \`en\`, so a missing key is a TYPE ERROR.
   - No string here may present fake prices, fake buyers, fake forecasts or
     fake statistics. Placeholders are labelled as placeholders.
   - {placeholders} are substituted by \`t(key, params)\`. */

`;

const enBlock = "const en = {\n" + blockLines(enRaw) + "\n}\n";
const hiBlock = "const hi: Record<TranslationKey, string> = {\n" + blockLines(hiRaw) + "\n}\n";
const teBlock = "const te: Record<TranslationKey, string> = {\n" + blockLines(teRaw) + "\n}\n";

const footer = `
export type TranslationKey = keyof typeof en

const translations: Record<Locale, Record<TranslationKey, string>> = { en, hi, te }

export const TRANSLATION_KEYS = Object.keys(en) as TranslationKey[]

/** Substitute {placeholders} in a template string. */
export function formatTranslation(
  template: string,
  params?: Record<string, string | number>,
): string {
  if (!params) return template
  return template.replace(/\\{(\\w+)\\}/g, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match,
  )
}
`;

const out = header + enBlock + "\n\n" + hiBlock + "\n\n" + teBlock + footer;
const outPath = __dirname + '/translations-fixed.ts';
fs.writeFileSync(outPath, out);
console.log('Wrote', outPath);
console.log('enKeys count:', enKeys.length);
