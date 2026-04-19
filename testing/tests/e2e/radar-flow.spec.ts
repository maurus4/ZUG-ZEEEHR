import { test, expect } from '@playwright/test';

const MOCK_TRAIN = {
  trip_id: 'IC8_Brig',
  origin: 'Zürich HB',
  destination: 'Brig',
  delay: 12,
  latitude: 47.3769,
  longitude: 8.5417,
  departure_time: new Date(Date.now() + 300_000).toISOString(),
};

test.describe('E2E: Vollständiger Datenfluss', () => {

  test('AC-E2E-01/02: Sync-Button triggert sync-trains, danach view-live', async ({ page }) => {
    let syncCalled = false;
    let viewLiveCalled = false;

    await page.route('**/sync-trains', async route => {
      syncCalled = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', message: 'Mocked sync' }),
      });
    });
    await page.route('**/view-live', async route => {
      viewLiveCalled = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([MOCK_TRAIN]),
      });
    });

    await page.goto('/index_v2.html');
    await page.click('button:has-text("Radar aktualisieren")');
    await page.waitForFunction(
      () => document.getElementById('status-text')?.innerText === 'Daten aktuell',
      { timeout: 10_000 }
    );

    expect(syncCalled).toBe(true);
    expect(viewLiveCalled).toBe(true);
  });

  test('AC-E2E-03/04: Verspäteter Zug erscheint als Leaflet-Marker', async ({ page }) => {
    await page.route('**/view-live', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([MOCK_TRAIN]),
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

    // Leaflet rendert circleMarker als <path> im SVG-Layer
    const markers = page.locator('path.leaflet-interactive');
    await expect(markers).toHaveCount(1, { timeout: 5_000 });
  });

  test('AC-E2E-05/06: delayed-count == Anzahl Listeneinträge', async ({ page }) => {
    const trains = [
      { ...MOCK_TRAIN, trip_id: 'IC8_Brig',  delay: 12 },
      { ...MOCK_TRAIN, trip_id: 'RE_Chur',   delay: 5, latitude: 46.8, longitude: 9.5 },
      { ...MOCK_TRAIN, trip_id: 'IR_Basel',  delay: 0, latitude: 47.5, longitude: 7.6 }, // pünktlich, soll nicht gezählt werden
    ];

    await page.route('**/view-live', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(trains),
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

    const countText = await page.locator('#delayed-count').innerText();
    const listItems = await page.locator('#train-list li:not([style*="color"])').count();

    expect(parseInt(countText)).toBe(2);       // IR_Basel (delay=0) nicht mitgezählt
    expect(parseInt(countText)).toBe(listItems);
  });

});
