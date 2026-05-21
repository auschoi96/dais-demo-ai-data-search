import { test, expect } from '@playwright/test';
import { writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

const APP_CONFIG = {
  name: 'Yape',
  pages: [
    { navLabel: 'Home', path: '/', expectedTexts: ['Vibe Coding vs AI-Ready Data'] },
    { navLabel: 'Search', path: '/search', expectedTexts: ['Yape Service Search'] },
    { navLabel: 'Benchmark', path: '/benchmark', expectedTexts: ['Search Benchmark'] },
    { navLabel: 'Data Compare', path: '/compare', expectedTexts: ['Raw vs AI-Ready Data'] },
  ],
} as const;

let testArtifactsDir: string;
let consoleLogs: string[] = [];
let consoleErrors: string[] = [];
let pageErrors: string[] = [];
let failedRequests: string[] = [];

test('smoke test - app loads and displays home page', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Vibe Coding vs AI-Ready Data' })).toBeVisible();

  for (const plugin of APP_CONFIG.pages) {
    await expect(page.getByRole('link', { name: plugin.navLabel })).toBeVisible();
  }
});

for (const plugin of APP_CONFIG.pages) {
  test(`smoke test - ${plugin.navLabel} page loads`, async ({ page }) => {
    await page.goto(plugin.path);

    for (const text of plugin.expectedTexts) {
      await expect(page.getByText(text)).toBeVisible();
    }
  });
}

test.beforeEach(async ({ page }) => {
  consoleLogs = [];
  consoleErrors = [];
  pageErrors = [];
  failedRequests = [];

  testArtifactsDir = join(process.cwd(), '.smoke-test');
  mkdirSync(testArtifactsDir, { recursive: true });

  page.on('console', (msg) => {
    const type = msg.type();
    const text = msg.text();
    if (!text.trim() || /^%[osd]$/.test(text.trim())) return;
    const location = msg.location();
    const locationStr = location.url ? ` at ${location.url}:${location.lineNumber}:${location.columnNumber}` : '';
    consoleLogs.push(`[${type}] ${text}${locationStr}`);
    if (type === 'error') consoleErrors.push(`${text}${locationStr}`);
  });

  page.on('pageerror', (error) => {
    pageErrors.push(`Page error: ${error.message}\nStack: ${error.stack || 'No stack trace available'}`);
  });

  page.on('requestfailed', (request) => {
    failedRequests.push(`Failed request: ${request.url()} - ${request.failure()?.errorText}`);
  });
});

test.afterEach(async ({ page }, testInfo) => {
  const testName = testInfo.title.replace(/ /g, '-').toLowerCase();
  const screenshotPath = join(testArtifactsDir, `${testName}-app-screenshot.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });

  const logsPath = join(testArtifactsDir, `${testName}-console-logs.txt`);
  writeFileSync(
    logsPath,
    [
      '=== Console Logs ===',
      ...consoleLogs,
      '\n=== Console Errors ===',
      ...consoleErrors,
      '\n=== Page Errors ===',
      ...pageErrors,
      '\n=== Failed Requests ===',
      ...failedRequests,
    ].join('\n'),
    'utf-8',
  );

  await page.close();
});
