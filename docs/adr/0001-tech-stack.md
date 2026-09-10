# FastAPI + SQLite + Svelte in einem Docker-Image

Phase-1-MVP für Proxmox/LXC: schlanker Stack ohne Extra-DB-Container. FastAPI liefert die API und das gebaute Svelte-Frontend; SQLite liegt als Volume-Datei. Getrennt genug für spätere Shopify-/Auth-Erweiterungen, wartungsarm genug für einen Ein-Service-Compose-Stack.

**Status:** accepted

**Considered Options:** SvelteKit-Monolith; FastAPI + PostgreSQL + Svelte (zwei Services)
