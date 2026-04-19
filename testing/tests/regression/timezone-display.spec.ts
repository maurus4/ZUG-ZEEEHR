import { test, expect } from '@playwright/test';

test('Timezone-Regression: Abfahrtszeit zeigt Lokalzeit, nicht UTC-Rohwert', async ({ page }) => {
  // 13:33 UTC = 15:33 CEST — Backend speichert mit Z-Suffix
  const departureUTC = '2026-04-19T13:33:00Z';

  await page.route('**/view-live', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([{
      trip_id: 'IC8_Brig', origin: 'Zürich HB', destination: 'Brig',
      delay: 5, latitude: 47.37, longitude: 8.54,
      departure_time: departureUTC,
    }]),
  }));
  await page.route('**/sync-trains', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ status: 'success', message: 'ok' }),
  }));

  await page.goto('/index_v2.html');
  await page.waitForFunction(
    () => document.getElementById('status-text')?.innerText === 'Daten aktuell',
    { timeout: 10_000 }
  );

  const listText = await page.locator('#train-list').innerText();

  // Muss Lokalzeit (15:33 CEST) zeigen, NICHT UTC-Rohwert (13:33)
  expect(listText).toContain('15:33');
  expect(listText).not.toContain('13:33');
});

test('Timezone-Regression: departure_time null zeigt kein Zeitfeld', async ({ page }) => {
  await page.route('**/view-live', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([{
      trip_id: 'RE_Luzern', origin: 'Bern', destination: 'Luzern',
      delay: 8, latitude: 47.05, longitude: 8.31,
      departure_time: null,
    }]),
  }));
  await page.route('**/sync-trains', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ status: 'success', message: 'ok' }),
  }));

  await page.goto('/index_v2.html');
  await page.waitForFunction(
    () => document.getElementById('status-text')?.innerText === 'Daten aktuell',
    { timeout: 10_000 }
  );

  const listHTML = await page.locator('#train-list').innerHTML();
  // Kein leeres "Ab "-Label rendern
  expect(listHTML).not.toMatch(/Ab\s*<\/span>/);
  expect(listHTML).not.toContain('Invalid Date');
});
