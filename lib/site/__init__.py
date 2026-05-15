"""El Site — módulo de monitoreo. Cada submódulo lee una pieza del estado
del Droplet (host, containers, Postgres, Redis, Caddy) o de servicios externos
(Anthropic, OpenAI, DO, n8n vía Tailscale).

Los chequeos son puros: no escriben DB. El almacén (`almacen.py`) es el único
que persiste — vive en La Gerencia y se llama desde el view y el cron.
"""
