# Homepage archive — flip tiles & Glances service customizations

Not loaded by Homepage. Kept for optional re-enable later.

| File | Contents |
|---|---|
| `flip-and-glances-service.js` | Flip button (Glances/Pi-hole NAS↔HTPC), Glances info styling + copy-to-clipboard |
| `flip-and-glances-service.css` | Matching CSS for flip hit-box and Glances service widget layout |
| `services-flip-snippets.yaml` | Paired HTPC service entries + native Glances widget block |

## Re-enable

1. Merge JS/CSS into `config/custom.js` / `config/custom.css` (or paste sections where noted).
2. Restore snippets in `config/services.yaml` (Glances + Glances HTPC, Pi-hole HTPC).
3. Redeploy homepage.
