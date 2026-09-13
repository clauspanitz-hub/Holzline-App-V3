# Deployment-Leitfaden (Proxmox LXC)

Ziel: Holzlinge Inventar in einem **Debian/Ubuntu-LXC** mit **Docker Compose**, erreichbar unter `http://<LXC-IP>:8000`.

---

## A) Was ich (Cursor) steuern kann — und was nicht

**Ohne Proxmox-MCP:** Ich kann nur Anleitungen geben; du klickst/tippst im Proxmox-UI bzw. per SSH.

**Mit Proxmox-MCP:** Ich kann LXC anlegen, starten, Docker vorbereiten und (mit Host-SSH) Befehle im Container ausführen.

Benötigt:

1. MCP **`cursor-proxmox-mcp`** (PyPI) — empfohlen  
2. Optional: Skill-Wissen `npx skills add bldg-7/proxmox-mcp@proxmox-mcp-tools` (nur Doku/Workflows, **kein** API-Zugriff)

---

## B) MCP einrichten (einmalig — damit ich übernehmen kann)

### B1. Proxmox API-Token

1. Proxmox-UI → **Datacenter → Permissions → API Tokens → Add**
2. User z. B. `root@pam` oder besser eigener User `mcp@pve`
3. Token-ID z. B. `cursor`
4. **Privilege Separation: Yes** belassen und dem Token passende Rechte geben (mind. VM/LXC anlegen/starten, Storage lesen; für Docker-LXC oft `PVEVMAdmin` + Datastore)
5. Token-Secret **sofort notieren** (nur einmal sichtbar)

### B2. `uv` installieren (Windows)

```powershell
winget install astral-sh.uv
```

Cursor danach neu starten.

### B3. Config-Datei (ohne Repo — Secrets lokal!)

Datei z. B. `C:\Users\<DU>\proxmox-config\config.json`:

```json
{
  "proxmox": {
    "host": "192.168.x.x",
    "port": 8006,
    "verify_ssl": false,
    "service": "PVE"
  },
  "auth": {
    "user": "root@pam",
    "token_name": "cursor",
    "token_value": "HIER-TOKEN-SECRET"
  },
  "logging": {
    "level": "INFO",
    "verbose": false,
    "tool_calls": true
  }
}
```

### B4. Cursor MCP (`%USERPROFILE%\.cursor\mcp.json`)

Eintrag ergänzen (Pfad anpassen):

```json
{
  "mcpServers": {
    "proxmox": {
      "command": "uvx",
      "args": ["cursor-proxmox-mcp"],
      "env": {
        "PROXMOX_MCP_CONFIG": "C:/Users/DU/proxmox-config/config.json"
      }
    }
  }
}
```

Dann in Cursor: **Settings → MCP → proxmox** neu laden / Cursor neu starten.  
Wenn Tools erscheinen: Schreib mir „MCP ist live“ + gewünschte LXC-IP/Hostname — dann übernehme ich Provisioning.

**Optional Host-SSH** (für `pct`-Befehle / Deploy in den LXC): siehe [SETUP.md des MCP](https://github.com/hackmods/cursor-proxmox-mcp/blob/main/SETUP.md) Abschnitt *SSH for LXC exec*.

---

## C) Manuelle Schritt-für-Schritt-Anleitung (ohne MCP)

### C1. LXC anlegen (Proxmox-UI)

| Feld | Empfehlung |
|------|------------|
| CT ID | freie ID (z. B. `120`) |
| Hostname | `holzlinge-inventar` |
| Template | Debian 12 oder Ubuntu 24.04 |
| Disk | ≥ 8 GB |
| CPU | 2 |
| RAM | 2048 MB |
| Swap | 512 MB |
| Netz | Bridge `vmbr0`, DHCP oder feste IP |
| Features | **nesting=1** (wichtig für Docker) |
| Unprivileged | Ja (üblich); bei Docker-Problemen ggf. `keyctl` / nesting prüfen |

Container **starten**.

### C2. In den LXC (Konsole oder SSH als root)

```bash
apt update && apt upgrade -y
apt install -y curl git ca-certificates

# Docker
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker compose version
```

### C3. App deployen

```bash
mkdir -p /opt
git clone https://github.com/clauspanitz-hub/Holzline-App-V3.git /opt/holzlinge-inventar
cd /opt/holzlinge-inventar

# Kein docker-compose.override.yml im Prod nötig (sonst Port 8001)
# Falls Override lokal mitkommt und stört:
# rm -f docker-compose.override.yml

docker compose up -d --build
docker compose ps
docker compose logs -f --tail=50 app
```

### C4. Prüfen

- App: `http://<LXC-IP>:8000`
- API-Docs: `http://<LXC-IP>:8000/docs`
- Daten: Volume `holzlinge_data` → `/data/holzlinge.db` im Container

### C5. Updates später

```bash
cd /opt/holzlinge-inventar
git pull
docker compose up -d --build
```

### C6. Auth (Pflicht-Login)

Beim ersten Start mit **leeren** Benutzern wird ein Admin aus ENV geseedet (nur wenn noch kein User existiert):

```yaml
environment:
  DATABASE_URL: sqlite:////data/holzlinge.db
  ADMIN_USER: admin
  ADMIN_PASSWORD: "sicheres-passwort"
  SESSION_IDLE_HOURS: "12"
```

Nach dem Seed: Login in der App, weitere Benutzer unter Tab **Benutzer**. `ADMIN_PASSWORD` danach aus Compose entfernen oder belassen (wird ignoriert, sobald User existieren).

### C6b. Shopify-Bestelleingang

Apps kommen aus dem [Dev Dashboard](https://shopify.dev/docs/apps/build/dev-dashboard) (kein `shpat_`-Token mehr in der Admin). Client-ID und Secret unter Einstellungen; Scope **`read_orders`** in einer App-Version; App im Shop installieren. Shop und App müssen in derselben Organisation liegen.

In der Compose-`.env` auf CT 131:

```
SHOPIFY_STORE=dein-shop.myshopify.com
SHOPIFY_CLIENT_ID=…
SHOPIFY_CLIENT_SECRET=…
```

Die App holt per **Client-Credentials** ein 24-Stunden-Access-Token, cached es und ruft die Admin-API nur per Knopf **Shopify abrufen** auf (kein Hintergrund-Poll). Versendet bleibt manuell. Ohne Client-ID/Secret meldet der Knopf die fehlende Konfiguration.

Optional für **Vorschläge** in **zur Prüfung** und **Tageslage** (kein Gedächtnis, siehe ADR `0014` / `0016`):

```
GEMINI_API_KEY=…
GEMINI_MODEL=gemini-3.1-flash-lite
```

`GEMINI_MODEL` = API-ID (`gemini-3.1-flash-lite`), nicht der AI-Studio-Anzeigename. Anzeigenamen mit Leerzeichen normalisiert die App beim Start; trotzdem die ID setzen. Free-Tier und Modellwahl: ADR `0017`.

Ohne Key bleibt manuelle Zuordnung plus gemerkte **Shop-Zuordnung**.

Optional für **Etsy-Mail-Eingang** (IMAP-Warteschlange, ADR `0018`):

```
IMAP_HOST=mail.example.com
IMAP_PORT=993
IMAP_USER=etsy-bestellungen@…
IMAP_PASSWORD=…
IMAP_FOLDER=INBOX
IMAP_PROCESSED_FOLDER=verarbeitet
IMAP_POLL_HOURS=6
```

Ohne IMAP bleibt Shopify/Schnellerfassung; der Etsy-Parse-Knopf meldet fehlende Konfiguration. Gemini-Key wird fürs Parsen und für Vorschläge benötigt.

### C7. Externer Zugang (MyFRITZ + Caddy HTTPS)

Auf dem Proxmox-Host läuft Caddy. Holzlinge:

- **URL:** `https://2hbv2m9qsbil1c81.myfritz.net:9443`
- **Proxy:** Host-Caddy `:9443` → CT 131 `192.168.178.20:8000`
- **Auth:** nur App-Login (kein Caddy Basic-Auth mehr)

**FRITZ!Box Portfreigabe** (einmalig, sonst nur aus dem LAN erreichbar):

1. FRITZ!Box → Internet → Freigaben → Portfreigaben → Gerät = **Proxmox-Host** (`192.168.178.58`)
2. Neu: TCP **9443** → **9443** (IPv4; optional IPv6)
3. Speichern, von Mobilfunk/Hotspot testen (nicht nur WLAN)

Im LAN ohne Portfreigabe: gleiche URL funktioniert, wenn DNS auf die FRITZ! zeigt; alternativ weiter `http://192.168.178.20:8000`.

---

## D) Startbefehle (Referenz)

```bash
cd /opt/holzlinge-inventar
docker compose up -d --build
docker compose logs -f app
docker compose down
```

Lokal kann `docker-compose.override.yml` den Host-Port auf `8001` legen (Dev).

## E) Lokale Entwicklung (ohne Docker)

```bash
# Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (zweites Terminal)
cd frontend
npm install
npm run dev
```
