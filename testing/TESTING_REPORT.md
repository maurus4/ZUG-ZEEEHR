# Testing Report — ZUG-ZEEEHR
**Datum:** 2026-04-19  
**Tester:** Senior QA (Claude Code)  
**Tool:** Playwright 1.59.1 / Chromium  
**Ausführungsort:** `testing/`

---

## 1. Zusammenfassung

| Metrik | Wert |
|--------|------|
| Testsuiten | 4 |
| Tests total | 13 |
| Bestanden | **13** |
| Fehlgeschlagen | **0** |
| Gesamtdauer | 5.8s |
| Browserengine | Chromium (headless) |

**Alle 13 Tests bestanden.**

---

## 2. Ordnerstruktur Testing

```
testing/
├── TESTING_REPORT.md          ← dieser Bericht
├── playwright.config.ts       ← Playwright-Konfiguration
├── package.json               ← npm-Skripte (npm test)
├── package-lock.json
├── node_modules/              ← @playwright/test + Chromium
├── playwright-report/         ← HTML-Report (nach Ausführung)
├── test-results/              ← Traces & Artefakte (bei Retry)
└── tests/
    ├── e2e/
    │   └── radar-flow.spec.ts
    ├── component/
    │   └── list-logic.spec.ts
    ├── integration/
    │   └── fault-tolerance.spec.ts
    └── regression/
        └── timezone-display.spec.ts
```

**Ausführung:**
```bash
cd testing/
npm test                  # alle Tests, list-Reporter
npm run test:report       # + HTML-Report öffnen
```

---

## 3. Testergebnisse nach Suite

### 3.1 E2E — Vollständiger Datenfluss (`tests/e2e/radar-flow.spec.ts`)

Testet den kompletten Pfad: Button-Klick → `/sync-trains` → `/view-live` → Leaflet-Map → Liste.

| Test-ID | Beschreibung | Ergebnis | Dauer |
|---------|-------------|----------|-------|
| AC-E2E-01/02 | Sync-Button ruft sync-trains auf, view-live folgt automatisch | ✓ | 997ms |
| AC-E2E-03/04 | Verspäteter Zug erscheint als Leaflet-Marker in CH-Bounds | ✓ | 339ms |
| AC-E2E-05/06 | `delayed-count` im Panel == Anzahl Einträge in der Liste | ✓ | 438ms |

**Befunde:** Keine. Datenfluss funktioniert korrekt end-to-end.

---

### 3.2 Component — UI-Logik (`tests/component/list-logic.spec.ts`)

Testet Filterlogik, Sortierung und Rendering mit definierten Mock-Daten (4 Züge: delay 22, 5, 3, 0).

| Test-ID | Beschreibung | Ergebnis | Dauer |
|---------|-------------|----------|-------|
| AC-UI-01 | Pünktliche Züge (delay=0) erscheinen nicht in der Liste | ✓ | 444ms |
| AC-UI-02 | Liste absteigend nach Verspätung sortiert (22 → 5 → 3) | ✓ | 327ms |
| AC-UI-03 | `departure_time: null` erzeugt kein "undefined"/"Invalid Date" | ✓ | 362ms |
| AC-UI-04 | Stats-Panel zeigt Zug mit höchster Verspätung (IC8, +22 Min.) | ✓ | 338ms |

**Befunde:** Keine. Filter- und Sortierlogik korrekt implementiert.

---

### 3.3 Integration — Fault Tolerance (`tests/integration/fault-tolerance.spec.ts`)

Simuliert Netzwerk- und Serverausfälle via Playwright-Route-Mocking.

| Test-ID | Beschreibung | Ergebnis | Dauer |
|---------|-------------|----------|-------|
| AC-FT-01 | HTTP 500 auf `/view-live` → Fehlertext sichtbar, kein JS-Crash | ✓ | 724ms |
| AC-FT-02 | HTTP 503 auf `/sync-trains` → Status-Text zeigt Fehlerstatus | ✓ | 364ms |
| AC-FT-03 | Netzwerkabbruch (abort) → Map bleibt gerendert (Höhe > 0) | ✓ | 3.3s |
| AC-FT-04 | Recovery: zweiter Sync nach Fehler lädt Daten korrekt | ✓ | 422ms |

**Befunde & behobener Bug:**

> **BUG-FT-01 (behoben):** Der Fehlertext in der Zugliste lautete `"Backend Verbindung fehlgeschlagen."` — ohne das Schlüsselwort `"Fehler"`. Dies war inkonsistent mit dem Status-Text `"Fehler beim Laden!"`. Der Text wurde zu `"Fehler: Backend Verbindung fehlgeschlagen."` vereinheitlicht. Datei: `frontend/index_v2.html`, Zeile 367.

---

### 3.4 Regression — Timezone-Bug (`tests/regression/timezone-display.spec.ts`)

Verifiziert, dass der dokumentierte Bug (13:33 UTC wird als 13:33 Lokalzeit angezeigt statt 15:33 CEST) behoben ist.

| Test-ID | Beschreibung | Ergebnis | Dauer |
|---------|-------------|----------|-------|
| TZ-REG-01 | `13:33Z` (UTC) wird als `15:33` (CEST) angezeigt, nicht als `13:33` | ✓ | 450ms |
| TZ-REG-02 | `departure_time: null` rendert kein leeres "Ab "-Label | ✓ | 319ms |

**Befunde:** Timezone-Bug ist durch den `Z`-Suffix in `parse_departure()` korrekt behoben. `new Date("...Z")` wird vom Browser zuverlässig als UTC interpretiert und in die Browserlokalzeit konvertiert.

---

## 4. Code-Änderungen aus dem Testing-Prozess

| Datei | Änderung | Grund |
|-------|----------|-------|
| `backend/app.py` | `parse_departure()` gibt `"%Y-%m-%dT%H:%M:%SZ"` zurück | UTC-Suffix für korrekte Browser-Interpretation |
| `database/init.sql` | `route_data` entfernt, `departure_time DATETIME NULL` ergänzt | Schema-Bereinigung + neues Feature |
| `frontend/index_v2.html` | Fehlertext zu `"Fehler: Backend Verbindung fehlgeschlagen."` | Konsistenz (BUG-FT-01) |

---

## 5. Offene Punkte / Empfehlungen

| Priorität | Thema | Beschreibung |
|-----------|-------|-------------|
| Mittel | Docker Healthcheck | `/sync-trains` schlägt beim ersten Aufruf manchmal fehl, weil der Backend-Container startet, aber die DB noch nicht bereit ist. `docker-compose.yml` sollte einen `healthcheck` für den `db`-Service und `depends_on: condition: service_healthy` für `backend` erhalten. |
| Mittel | Archivierungs-Logik | `LOGIK A` (Archiv) archiviert nur Züge mit Koordinaten — ursprünglich war die Archivierung koordinatenunabhängig. Falls Züge ohne GPS-Fix dennoch archiviert werden sollen, müsste die Bedingung angepasst werden. |
| Niedrig | `trip_id` Kollision | Format `{category}{number}_{destination}` kann bei gleicher Verbindung über mehrere Hubs zu Überschreibungen führen. Eindeutiger wäre `{category}{number}_{destination}_{hub}`. |
| Niedrig | Sequentielle Hub-Abfragen | `api_connector` ruft 12 Hubs sequenziell ab. Bei langsamer Verbindung >15s Timeout-Risiko. `ThreadPoolExecutor` würde das auf ~2-3s reduzieren. |
