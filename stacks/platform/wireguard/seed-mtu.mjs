# Seed catalog default client MTU. wg-easy v15 has no INIT_MTU; 1420 is the
# factory default and breaks HTTPS on many cellular paths. Only rewrite 1420
# so an operator-chosen value is left alone. No site values here.
import { DatabaseSync } from 'node:sqlite'
import { existsSync } from 'node:fs'

const dbPath = '/etc/wireguard/wg-easy.db'
if (!existsSync(dbPath)) process.exit(0)
const db = new DatabaseSync(dbPath)
try {
  db.prepare(
    `UPDATE interfaces_table SET mtu = 1280, updated_at = datetime('now') WHERE mtu = 1420`
  ).run()
} catch {
  process.exit(0)
} finally {
  db.close()
}
