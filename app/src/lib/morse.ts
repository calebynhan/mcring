/** ITU Morse encoder — port of python/mcring_core/mcring_core/morse.py (byte-identical output). */

export const CODES: Record<string, string> = {
  A: '.-', B: '-...', C: '-.-.', D: '-..', E: '.', F: '..-.', G: '--.', H: '....', I: '..', J: '.---',
  K: '-.-', L: '.-..', M: '--', N: '-.', O: '---', P: '.--.', Q: '--.-', R: '.-.', S: '...', T: '-',
  U: '..-', V: '...-', W: '.--', X: '-..-', Y: '-.--', Z: '--..',
  '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....', '6': '-....',
  '7': '--...', '8': '---..', '9': '----.',
  '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.', '!': '-.-.--', '/': '-..-.', '(': '-.--.',
  ')': '-.--.-', '&': '.-...', ':': '---...', ';': '-.-.-.', '=': '-...-', '+': '.-.-.', '-': '-....-',
  _: '..--.-', '"': '.-..-.', $: '...-..-', '@': '.--.-.',
};

export interface Spacing {
  dot: number;
  dash: number;
  intraGap: number;
  charGap: number;
  wordGap: number;
}

export const STANDARD: Spacing = { dot: 1, dash: 3, intraGap: 1, charGap: 3, wordGap: 7 };

/** Farnsworth spacing (ARRL formula), same rounding as the C and Python implementations. */
export function farnsworth(charWpm: number, overallWpm: number): Spacing {
  if (charWpm <= 0 || overallWpm <= 0 || overallWpm >= charWpm) return { ...STANDARD };
  const c = charWpm, o = overallWpm;
  const unitS = 1.2 / c;
  const extraS = (60.0 * c - 37.2 * o) / (o * c);
  const extraUnits = extraS / unitS;
  const f = 1.0 + extraUnits / 19.0;
  const cg = Math.floor(3.0 * f + 0.5);
  const wg = Math.floor(7.0 * f + 0.5);
  return { ...STANDARD, charGap: Math.min(255, Math.max(3, cg)), wordGap: Math.min(255, Math.max(7, wg)) };
}

export function unitMs(wpm: number): number {
  return wpm ? Math.floor(1200 / wpm) : 80;
}

export function foldAscii(text: string): string {
  return text.normalize('NFKD').replace(/[^\x00-\x7F]/g, '');
}

export function encode(text: string, sp: Spacing = STANDARD, maxOut = 65535): { units: number[]; truncated: boolean } {
  const out: number[] = [];
  let haveChar = false;
  let pendingWordGap = false;
  let truncated = false;
  for (const ch of foldAscii(text)) {
    if (/\s/.test(ch)) {
      if (haveChar) pendingWordGap = true;
      continue;
    }
    const code = CODES[ch.toUpperCase()];
    if (!code) continue;
    const need = (haveChar ? 1 : 0) + code.length + (code.length - 1);
    if (out.length + need > maxOut) {
      truncated = true;
      break;
    }
    if (haveChar) out.push(pendingWordGap ? sp.wordGap : sp.charGap);
    pendingWordGap = false;
    for (let i = 0; i < code.length; i++) {
      if (i) out.push(sp.intraGap);
      out.push(code[i] === '-' ? sp.dash : sp.dot);
    }
    haveChar = true;
  }
  return { units: out, truncated };
}

export function totalUnits(units: number[]): number {
  return units.reduce((a, b) => a + b, 0);
}

export function durationMs(units: number[], wpm: number): number {
  return totalUnits(units) * unitMs(wpm);
}

/** Upper-case, A-Z 0-9 space ? only, ≤ maxChars, cut on word boundaries. */
export function shortenForMorse(text: string, maxChars = 32): string {
  const t = foldAscii(text).toUpperCase();
  let keep = '';
  for (const ch of t) {
    if (/[A-Z0-9 ?]/.test(ch)) keep += ch;
    else if ('-_/,.;:'.includes(ch)) keep += ' ';
  }
  const s = keep.split(/\s+/).filter(Boolean).join(' ');
  if (s.length <= maxChars) return s;
  const out: string[] = [];
  for (const w of s.split(' ')) {
    const cand = [...out, w].join(' ');
    if (cand.length > maxChars) break;
    out.push(w);
  }
  return out.length ? out.join(' ') : s.slice(0, maxChars).trimEnd();
}
