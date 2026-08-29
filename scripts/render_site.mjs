import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { encode as referenceEncode } from '../site/codec.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, 'site', 'exports');
await mkdir(output, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
await page.goto(`file://${path.join(root, 'site', 'index.html')}`, { waitUntil: 'networkidle' });
await page.waitForFunction(() => document.querySelector('#wire-output')?.value?.startsWith('AVP1|'));
const browserWire = await page.locator('#wire-output').inputValue();
const fixture = JSON.parse(await readFile(path.join(root, 'examples', 'governed_mission.json'), 'utf8'));
if (browserWire !== referenceEncode(fixture)) throw new Error('browser and module AVP1 wires diverged');
await page.screenshot({ path: path.join(output, 'anvil-public-alpha-desktop.png'), fullPage: true });
await page.screenshot({ path: path.join(output, 'anvil-public-alpha-first-view.png') });

await page.locator('#wrong-context').click();
await page.waitForFunction(() => document.querySelector('#status')?.textContent?.includes('profile mismatch'));
const wrongContextStatus = await page.locator('#status').textContent();
if (!wrongContextStatus?.includes('profile mismatch')) throw new Error('wrong-context demo did not fail closed');
await page.locator('#reset').click();
await page.waitForFunction(() => document.querySelector('#status')?.textContent?.includes('Exact semantic and authority'));
const exactStatus = await page.locator('#status').textContent();
if (!exactStatus?.includes('Exact semantic and authority')) throw new Error('reset did not restore exact round trip');

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`file://${path.join(root, 'site', 'index.html')}`, { waitUntil: 'networkidle' });
await page.screenshot({ path: path.join(output, 'anvil-public-alpha-mobile.png'), fullPage: true });
await page.screenshot({ path: path.join(output, 'anvil-public-alpha-mobile-first-view.png') });

await browser.close();
console.log(JSON.stringify({ output, parity: 'exact', wrongContextStatus, exactStatus }));
