import { test, expect } from '@playwright/test';

const MOCK_TRAINS = [
  {
    trip_id: 'RE_Chur',  origin: 'Zürich HB', destination: 'Chur',
    delay: 5,  latitude: 47.0, longitude: 9.0,
    departure_time: new Date(Date.now() + 120_000).toISOString(),
  },
  {
    trip_id: 'IC8_Brig', origin: 'Bern', destination: 'Brig',
    delay: 22, latitude: 46.9, longitude: 7.4,
    departure_time: null,
  },
  {
    trip_id: 'IR_Basel', origin: 'Olten', destination: 'Basel',
    delay: 0,  latitude: 47.5, longitude: 7.6,
    departure_time: new Date(Date.now() + 60_000).toISOString(),
  },
  {
    trip_id: 'S8_Uster', origin: 'Zürich HB', destination: 'Uster',
    delay: 3,  latitude: 47.3, longitude: 8.7,
    departure_time: new Date(Date.now() + 900_000).toISOString(),
  },
];

test.beforeEach(async ({ page }) => {
  await page.route('**/view-live', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(MOCK_TRAINS),
  }));
  await page.route('**/sync-trains', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ status: 'success', message: 'Mocked sync' }),
  }));

  await page.goto('/index_v2.html');
  await page.waitForFunction(
    () => document.getElementById('status-text')?.innerText === 'Daten aktuell',
    { timeout: 10_000 }
  );
});

test('AC-UI-01: Pünktliche Züge (delay=0) erscheinen nicht in der Liste', async ({ page }) => {
  const items = await page.locator('#train-list li').allInnerTexts();
  const hasBasel = items.some(t => t.includes('IR') || t.includes('Basel'));
  expect(hasBasel).toBe(false);
});

test('AC-UI-02: Liste ist absteigend nach Verspätung sortiert', async ({ page }) => {
  const badges = await page.locator('#train-list .list-delay').allInnerTexts();
  const delays = badges.map(t => parseInt(t.replace(/\D/g, '')));
  const sorted = [...delays].sort((a, b) => b - a);
  expect(delays).toEqual(sorted);
});

test('AC-UI-03: departure_time null ergibt kein "undefined" / "Invalid Date"', async ({ page }) => {
  const listHTML = await page.locator('#train-list').innerHTML();
  expect(listHTML).not.toContain('undefined');
  expect(listHTML).not.toContain('Invalid Date');
  expect(listHTML).not.toContain('NaN');
});

test('AC-UI-04: worst-connection zeigt Zug mit höchster Verspätung', async ({ page }) => {
  const worstText = await page.locator('#worst-connection').innerText();
  // IC8_Brig hat delay=22 — höchste Verspätung
  expect(worstText).toContain('IC8');
  expect(worstText).toContain('22');
});
