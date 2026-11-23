const fs = require('fs');
const ts = require(__dirname + '/../apps/web/node_modules/typescript');

const src = fs.readFileSync(
  __dirname + '/../apps/web/src/i18n/translations.ts.bak',
  'utf8'
);

const sf = ts.createSourceFile('translations.ts', src, ts.ScriptTarget.Latest, true);

const en = {};
const hi = {};
const te = {};

function stringifyValue(node) {
  // For StringLiteral: return the text without quotes
  if (node.kind === ts.SyntaxKind.StringLiteral) {
    return node.text;
  }
  // For a TemplateLiteral or other: fallback to printing
  const printer = ts.createPrinter();
  const code = printer.formatNode(node);
  // strip surrounding double quotes if present
  if (code.startsWith('"') && code.endsWith('"')) {
    code = code.slice(1, -1);
  }
  // unescape
  return code.replace(/\\"/g, '"').replace(/\\n/g, '\n').replace(/\\'/g, "'");
}

function collectProps(node, acc) {
  if (node.kind === ts.SyntaxKind.ObjectLiteralExpression) {
    for (const elem of node.properties) {
      if (elem.kind === ts.SyntaxKind.PropertyAssignment &&
          elem.name.kind === ts.SyntaxKind.StringLiteral) {
        const k = elem.name.text;
        acc[k] = stringifyValue(elem.initializer);
      }
    }
  } else {
    ts.forEachChild(node, child => collectProps(child, acc));
  }
}

function visit(node) {
  if (node.kind === ts.SyntaxKind.VariableDeclaration) {
    const nameNode = node.name;
    if (nameNode && nameNode.kind === ts.SyntaxKind.Identifier) {
      const name = nameNode.text;
      if (name === 'en' || name === 'hi' || name === 'te') {
        const init = node.initializer;
        if (init && init.kind === ts.SyntaxKind.ObjectLiteralExpression) {
          collectProps(init, name === 'en' ? en : name === 'hi' ? hi : te);
        }
      }
    }
  }
  ts.forEachChild(node, visit);
}
visit(sf);

console.log('AST parsed -> en:' + Object.keys(en).length +
            ' hi:' + Object.keys(hi).length +
            ' te:' + Object.keys(te).length);

// Show a few sample values to verify extraction quality
console.log('en common.brandName:', JSON.stringify(en['common.brandName']));
console.log('en landing.hero.title:', JSON.stringify(en['landing.hero.title']));
console.log('en common.footerText:', JSON.stringify(en['common.footerText']).slice(0, 60));
console.log('hi common.brandTagline:', JSON.stringify(hi['common.brandTagline']));
console.log('hi landing.roles.farmer.name:', JSON.stringify(hi['landing.roles.farmer.name']));

// dedupe en: the AST visit walks in source order; later assignments overwrite earlier
const enKeys = Object.keys(en).sort();
const enDeduped = {};
for (const k of enKeys) enDeduped[k] = en[k];

console.log('en deduped keys:', enKeys.length);

const missingHi = enKeys.filter(k => !(k in hi));
const missingTe = enKeys.filter(k => !(k in te));
console.log('missing in hi:', missingHi.length);
if (missingHi.length) console.log('  ', missingHi.join(', '));
console.log('missing in te:', missingTe.length);
if (missingTe.length) console.log('  ', missingTe.join(', '));

function blockLines(obj, keyList) {
  return keyList.map(k => {
    const v = (k in obj && obj[k] !== undefined) ? obj[k] : enDeduped[k];
    const js = JSON.stringify(v);
    return "  '" + k + "': " + js;
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

const enBlock = "const en = {\n" + blockLines(enDeduped, enKeys) + "\n}\n";
const hiBlock = "const hi: Record<TranslationKey, string> = {\n" + blockLines(hi, enKeys) + "\n}\n";
const teBlock = "const te: Record<TranslationKey, string> = {\n" + blockLines(te, enKeys) + "\n}\n";

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
  return template.replace(/\\{(\\w+)\\}/g, (match, name) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match,
  )
}
`;

const out = header + enBlock + "\n\n" + hiBlock + "\n\n" + teBlock + footer;
const wp = __dirname + '/translations-fixed.ts';
try {
  fs.writeFileSync(wp, out);
  console.log('Wrote', wp, 'size:', out.length, 'actual:', fs.statSync(wp).size);
} catch (e) {
  console.log('WRITE FAILED:', e.message);
}
