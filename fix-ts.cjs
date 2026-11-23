const fs = require('fs');
const path = require('path');
const ts = require('./apps/web/node_modules/typescript');

const projectRoot = path.resolve(__dirname);
const srcPath = path.join(projectRoot, 'apps/web/src/i18n/translations.ts.bak');
const outPath = path.join(projectRoot, 'tmp/translations-fixed.ts');

const src = fs.readFileSync(srcPath, 'utf8');
const sf = ts.createSourceFile('translations.ts', src, ts.ScriptTarget.Latest, true);

const en = {};
const hi = {};
const te = {};

function stringifyValue(node) {
  if (node.kind === ts.SyntaxKind.StringLiteral) {
    return node.text;
  }
  const printer = ts.createPrinter();
  const code = printer.formatNode(node);
  if (code.startsWith('"') && code.endsWith('"')) {
    code = code.slice(1, -1);
  }
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

const enKeys = Object.keys(en).sort();
const enDeduped = {};
for (const k of enKeys) enDeduped[k] = en[k];

const missingHi = enKeys.filter(k => !(k in hi));
const missingTe = enKeys.filter(k => !(k in te));

function blockLines(obj, keyList) {
  return keyList.map(k => {
    const v = (k in obj && obj[k] !== undefined) ? obj[k] : enDeduped[k];
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

const enBlock = "const en = {\n" + blockLines(enDeduped, enKeys) + "\n}\n";
const hiBlock = "const hi: Record<TranslationKey, string> = {\n" + blockLines(hi, enKeys) + "\n}\n";
const teBlock = "const te: Record<TranslationKey, string> = {\n" + blockLines(te, enKeys) + "\n}\n";

const footer = `
export type TranslationKey = keyof typeof en

export const translations: Record<Locale, Record<TranslationKey, string>> = { en, hi, te }

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
fs.writeFileSync(outPath, out);

console.log('en:', enKeys.length, 'hi:', Object.keys(hi).length, 'te:', Object.keys(te).length);
console.log('missingInHi:', missingHi.length, 'missingInTe:', missingTe.length);
console.log('outPath:', outPath, 'bytes:', out.length, 'fsSize:', fs.statSync(outPath).size);
