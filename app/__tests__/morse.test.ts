import { encode, farnsworth, STANDARD, shortenForMorse, unitMs } from '../src/lib/morse';
import fixtures from './fixtures/morse_fixtures.json';

test('SOS standard', () => {
  expect(encode('SOS').units).toEqual([1, 1, 1, 1, 1, 3, 3, 1, 3, 1, 3, 3, 1, 1, 1, 1, 1]);
});

test('word gap, whitespace, unknown chars, accents', () => {
  expect(encode('e e').units).toEqual([1, 7, 1]);
  expect(encode('  E   E ').units).toEqual([1, 7, 1]);
  expect(encode('E#E').units).toEqual([1, 3, 1]);
  expect(encode('é').units).toEqual(encode('E').units);
  expect(encode('日本').units).toEqual([]);
});

test('truncation stops on whole characters', () => {
  const r = encode('SOS', STANDARD, 8);
  expect(r.truncated).toBe(true);
  expect(r.units).toEqual([1, 1, 1, 1, 1]);
});

test('farnsworth and unit length', () => {
  const sp = farnsworth(15, 8);
  expect(sp.charGap).toBeGreaterThan(3);
  expect(farnsworth(10, 15)).toEqual(STANDARD);
  expect(unitMs(15)).toBe(80);
});

test('shortenForMorse', () => {
  expect(shortenForMorse('This is a Foxglove, toxic!')).toBe('THIS IS A FOXGLOVE TOXIC');
  expect(shortenForMorse('Digitalis purpurea (foxglove) - toxic', 20)).toBe('DIGITALIS PURPUREA');
});

describe('matches the Python reference implementation', () => {
  for (const f of fixtures) {
    test(`${JSON.stringify(f.text)} @ ${f.char_wpm}/${f.overall_wpm}`, () => {
      const sp = f.overall_wpm ? farnsworth(f.char_wpm, f.overall_wpm) : STANDARD;
      expect(encode(f.text, sp).units).toEqual(f.units);
    });
  }
});
