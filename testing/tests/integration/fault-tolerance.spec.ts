import { test, expect } from '@playwright/test';

const FRONTEND = '/index_v2.html';

test('AC-FT-01: HTTP 500 auf view-live → Fehlertext sichtbar, kein JS-Crash', async ({ page }) => {
  const jsErrors: string[] = [];
  page.on('pageerror', e => jsErrors.push(e.message));

  await page.route('**/view-live', route => route.fulfill({ status: 500, body: 'Internal Server Error' }));
  await page.route('**/sync-trains', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ status: 'success', message: 'ok' }),
  }));

  await page.goto(FRONTEND);
  await page.waitForFunction(
    () => document.getElementById('status-text')?.innerText.toLowerCase().includes('fehler'),
    { timeout: 8_000 }
  );

  const listHTML = await page.locator('#train-list').innerHTML();
  // Frontend zeigt "Backend Verbindung fehlgeschlagen." — enthält "verbindung" oder "fehler"
  expect(listHTML.toLowerCase()).toMatch(/fehler|verbindung|fehlgeschlagen/);
  // Keine unbehandelten JS-Exceptions (favicon-Fehler ignorieren)
  expect(jsErrors.filter(e => !e.includes('favicon'))).toHaveLength(0);
});

test('AC-FT-02: HTTP 503 auf sync-trains → Status zeigt Fehlerstatus', async ({ page }) => {
  await page.route('**/sync-trains', route => route.fulfill({ status: 503, body: 'Service Unavailable' }));
  await page.route('**/view-live', route => route.fulfill({
    status: 200, contentType: 'application/json', body: '[]',
  }));

  await page.goto(FRONTEND);
  await page.click('button:has-text("Radar aktualisieren")');

  await page.waitForFunction(
    () => {
      const t = document.getElementById('status-text')?.innerText.toLowerCase() ?? '';
      return t.includes('fehler') || t.includes('fehlgeschlagen');
    },
    { timeout: 8_000 }
  );

  const statusText = await page.locator('#status-text').innerText();
  expect(statusText.toLowerCase()).toMatch(/fehler|fehlgeschlagen/);
});

test('AC-FT-03: Netzwerkabbruch (abort) → Map bleibt gerendert', async ({ page }) => {
  await page.route('**/view-live', route => route.abort('failed'));
  await page.route('**/sync-trains', route => route.abort('failed'));

  await page.goto(FRONTEND);
  await page.waitForTimeout(3_000);

  const mapBox = await page.locator('#map').boundingBox();
  expect(mapBox?.height).toBeGreaterThan(0);
});

test('AC-FT-04: Recovery — zweiter Aufruf nach Fehler lädt Daten korrekt', async ({ page }) => {
  let callCount = 0;

  await page.route('**/view-live', async route => {
    callCount++;
    if (callCount === 1) {
      return route.fulfill({ status: 500, body: 'error' });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{
        trip_id: 'IC_Bern', origin: 'Zürich HB', destination: 'Bern',
        delay: 8, latitude: 46.9, longitude: 7.4,
        departure_time: new Date(Date.now() + 300_000).toISOString(),
      }]),
    });
  });
  await page.route('**/sync-trains', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ status: 'success', message: 'ok' }),
  }));

  await page.goto(FRONTEND);
  await page.waitForFunction(
    () => document.getElementById('status-text')?.innerText.toLowerCase().includes('fehler'),
    { timeout: 8_000 }
  );

  // Zweiten Sync manuell triggern → Recovery
  await page.click('button:has-text("Radar aktualisieren")');
  await page.waitForFunction(
    () => document.getElementById('status-text')?.innerText === 'Daten aktuell',
    { timeout: 8_000 }
  );

  const count = await page.locator('#train-list li').count();
  expect(count).toBeGreaterThan(0);
});
