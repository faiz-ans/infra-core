# Seed catalog defaults in wg-easy v15 SQLite. No INIT_MTU / INIT_DEVICE.
# - Factory client MTU 1420 → 1280 (operator-chosen MTU is left alone).
# - Device + live MASQUERADE follow the current default IPv4 route iface.
#   Handshake + LAN with no WAN means NAT still points at a dead NIC.
import { execSync } from 'node:child_process'
import { DatabaseSync } from 'node:sqlite'
import { existsSync } from 'node:fs'

const dbPath = '/etc/wireguard/wg-easy.db'
if (!existsSync(dbPath)) process.exit(0)

function sh(cmd) {
  try {
    return execSync(cmd, { encoding: 'utf8' })
  } catch {
    return ''
  }
}

function defaultDev() {
  const m = sh('ip -4 route show default').match(/\bdev\s+(\S+)/)
  const dev = m ? m[1] : ''
  if (!dev || /^(wg|docker|br-|lo)/.test(dev)) return ''
  return dev
}

function natLines() {
  return sh('iptables -t nat -S POSTROUTING')
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
}

function syncMasq(cidr, dev) {
  if (!cidr || !dev) return
  for (const line of natLines()) {
    if (!line.includes('MASQUERADE') || !line.includes(`-s ${cidr}`)) continue
    const om = line.match(/-o\s+(\S+)/)
    const odev = om ? om[1] : ''
    if (odev && odev !== dev) {
      sh(`iptables -t nat -D POSTROUTING ${line.replace(/^-A POSTROUTING\s+/, '')}`)
    }
  }
  const has = natLines().some(
    (l) =>
      l.includes('MASQUERADE') &&
      l.includes(`-s ${cidr}`) &&
      l.includes(`-o ${dev}`)
  )
  if (!has) {
    sh(`iptables -t nat -A POSTROUTING -s ${cidr} -o ${dev} -j MASQUERADE`)
  }
}

const db = new DatabaseSync(dbPath)
try {
  db.prepare(
    `UPDATE interfaces_table SET mtu = 1280, updated_at = datetime('now') WHERE mtu = 1420`
  ).run()

  const row = db
    .prepare(`SELECT ipv4_cidr, device FROM interfaces_table LIMIT 1`)
    .get()
  const dev = defaultDev()
  if (row && dev) {
    if (row.device !== dev) {
      db.prepare(
        `UPDATE interfaces_table SET device = ?, updated_at = datetime('now')`
      ).run(dev)
      try {
        db.prepare(
          `UPDATE hooks_table SET
             post_up = REPLACE(post_up, ?, '{{device}}'),
             post_down = REPLACE(post_down, ?, '{{device}}'),
             updated_at = datetime('now')`
        ).run(`-o ${row.device}`, `-o ${row.device}`)
      } catch {
        /* no hooks_table */
      }
    }
    syncMasq(row.ipv4_cidr, dev)
  }
} catch {
  process.exit(0)
} finally {
  db.close()
}
