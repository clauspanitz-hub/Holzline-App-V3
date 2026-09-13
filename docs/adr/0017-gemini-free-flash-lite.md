# Gemini Free-Tier und Flash-Lite

Das Free-Kontingent stärkerer Flash-Modelle (wenige Requests/Tag) war durch periodischen Shopify-Poll plus Vorschläge schnell erschöpft; Google drängte auf Abrechnung. Entscheidung: **Free bleiben**, Default-Modell **`gemini-3.1-flash-lite`** (höheres Free-Tageskontingent), Shopify nur auf Knopfdruck (ADR `0013`). Schlechtere Zuordnungsvorschläge sind bewusst akzeptiert — Gemini bleibt nur Vorschlag, Mensch bestätigt (ADR `0014`). `GEMINI_MODEL` ist die API-ID; AI-Studio-Anzeigenamen mit Leerzeichen werden beim Start normalisiert.

**Status:** accepted

**Considered Options:** Billing (Paid) aktivieren; bei `gemini-3.8-flash` bleiben; Hintergrund-Poll behalten und nur das Modell wechseln
