# Seed catalog defaults in wg-easy v15 SQLite. No INIT_MTU / INIT_DEVICE.
# - Factory client MTU 1420 → 1280 (operator-chosen MTU is left alone).
# - Device = current default IPv4 route iface so MASQUERADE follows a NIC
#   rename (e.g. IO board eth0 → X1509 eth1). Handshake can succeed while
#   internet fails if NAT still points at the old interface.
import { execSync } from 'node:child_process'
import { DatabaseSync } from 'node:sqlite'
import { existsSync } from 'node:fs'

const dbPath = '/etc/wireguard/wg-easy.db'
if (!existsSync(dbPath)) process.exit(0)

function defaultDev() {
  try {
    const out = execSync('ip -4 route show default', {
      encoding: 'utf8',
    })
    const m = out.match(/\bdev\s+(\S+)/)
    const dev = m ? m[1] : ''
    if (!dev || /^(wg|docker|br-|lo)/.test(dev)) return ''
    return dev
  } catch {
    return ''
  }
}

const db = new DatabaseSync(dbPath)
try {
  db.prepare(
    `UPDATE interfaces_table SET mtu = 1280, updated_at = datetime('now') WHERE mtu = 1420`
  ).run()
  const dev = defaultDev()
  if (dev) {
    try {
      db.prepare(
        `UPDATE interfaces_table SET device = ?, updated_at = datetime('now') WHERE device IS NULL OR device = '' OR device != ?`
      ).run(dev, dev)
    } catch {
      /* older schema without device */
    }
  }
} catch {
  process.exit(0)
} finally {
  db.close()
}
