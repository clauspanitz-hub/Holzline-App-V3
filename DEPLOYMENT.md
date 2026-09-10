# Deployment-Leitfaden (Proxmox LXC)

## Voraussetzungen im Proxmox-Host
- Ein unprivileged oder privileged Debian/Ubuntu-LXC-Container.
- Docker & Docker Compose installiert (`curl -fsSL https://get.docker.com | sh`).
- Portweiterleitung / Caddy Reverse Proxy eingerichtet.

## Startbefehle
```bash
# Repository / Ordner klonen bzw. öffnen
cd /opt/holzlinge-inventar

# Container bauen und starten
docker compose up -d --build

# Logs
docker compose logs -f app

# Stoppen
docker compose down
```

## Zugriff
- App: `http://<LXC-IP>:8000`
- API-Docs: `http://<LXC-IP>:8000/docs`
- SQLite-Daten liegen im Docker-Volume `holzlinge_data` unter `/data/holzlinge.db`.

Lokal kann `docker-compose.override.yml` den Host-Port auf `8001` legen (vermeidet Konflikte mit dem Dev-Backend auf `8000`).

## Lokale Entwicklung (ohne Docker)
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
