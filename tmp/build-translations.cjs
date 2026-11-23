const fs = require('fs');

// ---- Load canonical en (deduped, one key per entry) ----
const enRaw = fs.readFileSync(__dirname + '/en-canonical.ts', 'utf8');
const en = {};
const enRe = new RegExp("'([^'\\n]+?)'\\s*:\\s*'((?:[^'\\n]|\\')*)'", 'g');
let m;
while ((m = enRe.exec(enRaw))) {
  en[m[1].trim()] = m[2].replace(/\\'/g, "'");
}

// ---- Load the live translations file ----
const src = fs.readFileSync(__dirname + '/../apps/web/src/i18n/translations.ts', 'utf8');

/**
 * Extract the body of a block given its declaration prefix.
 * Uses a string-aware scan so that { } inside string literals don't break depth.
 */
function extractBody(labelEndPos) {
  // labelEndPos points just after the opening '{' of the block.
  const bodyStart = labelEndPos;
  let i = bodyStart;
  let inSingle = false;
  let inDouble = false;
  let depth = 0;
  while (i < src.length) {
    const c = src[i];
    if (inSingle) {
      if (c === '\\' && i + 1 < src.length) { i += 2; continue; }
      if (c === "'") inSingle = false;
      i += 1;
      continue;
    }
    if (inDouble) {
      if (c === '\\' && i + 1 < src.length) { i += 2; continue; }
      if (c === '"') inDouble = false;
      i += 1;
      continue;
    }
    if (c === "'") { inSingle = true; i += 1; continue; }
    if (c === '"') { inDouble = true; i += 1; continue; }
    if (c === '{') { depth += 1; i += 1; continue; }
    if (c === '}') {
      depth -= 1;
      if (depth === 0) break;
      i += 1;
      continue;
    }
    i += 1;
  }
  return src.slice(bodyStart, i);
}

function extractValues(name) {
  // Find declaration: 'const <name> = {' or 'const <name>: ... = {'
  const cand1 = 'const ' + name + ' = {';
  const cand2 = 'const ' + name + ': Record<TranslationKey, string> = {';
  const idx1 = src.indexOf(cand1);
  const idx2 = src.indexOf(cand2);
  const start = (idx1 !== -1 ? idx1 : idx2);
  if (start === -1) return {};
  const labelEndPos = start + (idx1 !== -1 ? cand1.length : cand2.length);
  const body = extractBody(labelEndPos);
  const out = {};
  const keyRe = new RegExp("'([^'\\n]+?)'\\s*:\\s*", 'g');
  let m;
  while ((m = keyRe.exec(body))) {
    const k = m[1].trim();
    if (!k) continue;
    const colonEnd = m.index + m[0].length;
    if (body.charAt(colonEnd) !== "'") continue;
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
    out[k] = val.replace(/\\'/g, "'");
  }
  return out;
}

const hiExisting = extractValues('hi');
const teExisting = extractValues('te');
console.log('extracted hi keys:', Object.keys(hiExisting).length, 'te keys:', Object.keys(teExisting).length);

// ---- Build identical key set ----
const keys = Object.keys(en).sort();
const enOnly = keys.filter(k => !(k in en));
console.log('en-only (should be 0):', enOnly.length);

const missingInHi = keys.filter(k => !(k in hiExisting));
const missingInTe = keys.filter(k => !(k in teExisting));
console.log('missing in hi (fallback en):', missingInHi.length, missingInHi.join(', ') || 'none');
console.log('missing in te (fallback en):', missingInTe.length, missingInTe.join(', ') || 'none');

// ---- Emit ----
function blockLines(existing) {
  return keys.map(k => {
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

const enBlock = "const en = {\n" + blockLines(en) + "\n}\n";
const hiBlock = "const hi: Record<TranslationKey, string> = {\n" + blockLines(hiExisting) + "\n}\n";
const teBlock = "const te: Record<TranslationKey, string> = {\n" + blockLines(teExisting) + "\n}\n";

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

const outPath = __dirname + '/translations-generated.ts';
fs.writeFileSync(outPath, header + enBlock + "\n\n" + hiBlock + "\n\n" + teBlock + footer);
console.log('Wrote', outPath);
