# Seed catalog defaults in wg-easy v15 SQLite. No INIT_MTU / INIT_DEVICE.
# - Factory client MTU 1420 → 1280 (operator-chosen MTU is left alone).
# - Device + live MASQUERADE follow the current default IPv4 route iface.
#   Default iface comes from /proc/net/route (host netns; no `ip` in the image).
#   Re-apply after wg-easy PostUp, which otherwise restores -o eth0.
import { execSync } from 'node:child_process'
import { DatabaseSync } from 'node:sqlite'
import { existsSync, readFileSync } from 'node:fs'

const dbPath = '/etc/wireguard/wg-easy.db'
if (!existsSync(dbPath)) process.exit(0)

function sh(cmd) {
  try {
    return execSync(cmd, { encoding: 'utf8', shell: '/bin/sh' })
  } catch {
    return ''
  }
}

function skipIface(dev) {
  return !dev || /^(wg|docker|br-|lo)/.test(dev)
}

function defaultDev() {
  try {
    const lines = readFileSync('/proc/net/route', 'utf8').trim().split('\n').slice(1)
    let best = { metric: Infinity, dev: '' }
    for (const line of lines) {
      const cols = line.trim().split(/\s+/)
      const iface = cols[0]
      const dest = cols[1]
      const metric = Number.parseInt(cols[6], 10)
      if (dest !== '00000000' || skipIface(iface)) continue
      if (metric < best.metric) best = { metric, dev: iface }
    }
    if (best.dev) return best.dev
  } catch {
    /* fall through */
  }
  const m = sh('ip -4 route show default 2>/dev/null; /sbin/ip -4 route show default 2>/dev/null').match(
    /\bdev\s+(\S+)/
  )
  const dev = m ? m[1] : ''
  return skipIface(dev) ? '' : dev
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
