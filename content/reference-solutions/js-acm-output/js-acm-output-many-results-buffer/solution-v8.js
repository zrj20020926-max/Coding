const lines = [];
for (let line = readline(); line !== undefined; line = readline()) {
  lines.push(line);
}
const input = lines.join('\n');
const tokens = input.trim() === '' ? [] : input.trim().split(/\s+/);
function decimalParts(text) {
  const match = String(text).trim().match(/^([+-]?)(\d+)(?:\.(\d*))?$/);
  if (!match) throw new Error('invalid decimal input');
  return { negative: match[1] === '-', whole: match[2], fraction: match[3] ?? '' };
}
function fixedDecimal(text, digits) {
  const parts = decimalParts(text);
  const scale = 10n ** BigInt(digits);
  const padded = parts.fraction.padEnd(digits + 1, '0');
  let units = BigInt(parts.whole) * scale + BigInt(padded.slice(0, digits) || '0');
  if (padded[digits] >= '5') units += 1n;
  const sign = parts.negative && units !== 0n ? '-' : '';
  if (digits === 0) return sign + units.toString();
  const rendered = units.toString().padStart(digits + 1, '0');
  return `${sign}${rendered.slice(0, -digits)}.${rendered.slice(-digits)}`;
}
function addDecimalsFixed(left, right, digits) {
  const a = decimalParts(left);
  const b = decimalParts(right);
  const scaleDigits = Math.max(a.fraction.length, b.fraction.length, digits + 1);
  const scale = 10n ** BigInt(scaleDigits);
  const scaled = value => {
    const magnitude = BigInt(value.whole) * scale
      + BigInt(value.fraction.padEnd(scaleDigits, '0') || '0');
    return value.negative ? -magnitude : magnitude;
  };
  const total = scaled(a) + scaled(b);
  const sign = total < 0n ? '-' : '';
  const rendered = (total < 0n ? -total : total).toString().padStart(scaleDigits + 1, '0');
  const decimal = `${sign}${rendered.slice(0, -scaleDigits)}.${rendered.slice(-scaleDigits)}`;
  return fixedDecimal(decimal, digits);
}
let output = '';
const t = Number(lines[0] ?? 0); const out = []; for (let i = 0; i < t; i += 1) out.push(String(Number(lines[i + 1] ?? 0) * 2)); output = out.join('\n');
print(String(output));
