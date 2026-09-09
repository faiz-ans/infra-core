// Seed catalog defaults in wg-easy v15 SQLite. No INIT_MTU / INIT_DEVICE.
// - Factory client MTU 1420 → 1280 (operator-chosen MTU is left alone).
// - Device + live MASQUERADE follow the current default IPv4 route iface.
//   Prefer the NIC that holds NAS_LAN_IP. Skip DOWN / no-carrier (NIC swaps
//   leave a stale default on eth0). Node often has no /usr/sbin on PATH, so
//   PostUp writes iptables and this seed never sees the rule.
//   Re-apply after wg-easy PostUp, which otherwise restores -o eth0.
import { execSync } from 'node:child_process'
import { networkInterfaces } from 'node:os'
import { DatabaseSync } from 'node:sqlite'
import { existsSync, readFileSync } from 'node:fs'

const dbPath = '/etc/wireguard/wg-easy.db'
if (!existsSync(dbPath)) process.exit(0)

const PATH = '/usr/sbin:/sbin:/usr/bin:/bin'

function sh(cmd) {
  try {
    return execSync(cmd, {
      encoding: 'utf8',
      shell: '/bin/sh',
      env: { ...process.env, PATH },
    })
  } catch {
    return ''
  }
}

function skipIface(dev) {
  return !dev || /^(wg|docker|br-|lo|veth|tun|tap)/.test(dev)
}

function isV4(a) {
  return a && (a.family === 'IPv4' || a.family === 4)
}

function operUp(dev) {
  try {
    const st = readFileSync(`/sys/class/net/${dev}/operstate`, 'utf8').trim()
    if (st === 'down' || st === 'lowerlayerdown' || st === 'notpresent') return false
  } catch {
    /* missing sysfs */
  }
  try {
    if (readFileSync(`/sys/class/net/${dev}/carrier`, 'utf8').trim() === '0') return false
  } catch {
    /* some NICs omit carrier while UP */
  }
  return true
}

function hasV4(dev) {
  const addrs = networkInterfaces()[dev]
  return Boolean(addrs && addrs.some(isV4))
}

function ifaceForAddr(ip) {
  if (!ip) return ''
  for (const [name, addrs] of Object.entries(networkInterfaces())) {
    if (skipIface(name) || !operUp(name)) continue
    if ((addrs || []).some((a) => isV4(a) && a.address === ip)) return name
  }
  return ''
}

function defaultDev() {
  const lan = ifaceForAddr(process.env.INIT_DNS || process.env.NAS_LAN_IP || '')
  // Single-uplink NAS: NAT out the NIC that holds the LAN address. A stale
  // default on eth0 (NIC swap) otherwise wins on metric.
  if (lan) return lan

  const cands = []
  try {
    const lines = readFileSync('/proc/net/route', 'utf8').trim().split('\n').slice(1)
    for (const line of lines) {
      const cols = line.trim().split(/\s+/)
      const iface = cols[0]
      const dest = cols[1]
      const gw = cols[2]
      const metric = Number.parseInt(cols[6], 10)
      if (dest !== '00000000' || skipIface(iface) || !operUp(iface) || !hasV4(iface)) continue
      cands.push({
        iface,
        metric: Number.isFinite(metric) ? metric : 0,
        hasGw: gw && gw !== '00000000',
      })
    }
  } catch {
    /* fall through */
  }
  cands.sort((a, b) => Number(b.hasGw) - Number(a.hasGw) || a.metric - b.metric)
  if (cands[0]) return cands[0].iface

  const m = sh('ip -4 route get 1.1.1.1 2>/dev/null').match(/\bdev\s+(\S+)/)
  const dev = m ? m[1] : ''
  return skipIface(dev) || !operUp(dev) ? '' : dev
}

function iptablesBin() {
  for (const b of ['/usr/sbin/iptables-nft', '/usr/sbin/iptables', 'iptables']) {
    if (b.startsWith('/') && !existsSync(b)) continue
    return b
  }
  return 'iptables'
}

function natLines(bin) {
  return sh(`${bin} -t nat -S POSTROUTING`)
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
}

function syncMasq(cidr, dev) {
  if (!cidr || !dev) return
  const bin = iptablesBin()
  let kept = false
  for (const line of natLines(bin)) {
    if (!line.includes('MASQUERADE') || !line.includes(`-s ${cidr}`)) continue
    const om = line.match(/-o\s+(\S+)/)
    const odev = om ? om[1] : ''
    if (odev === dev && !kept) {
      kept = true
      continue
    }
    sh(`${bin} -t nat -D POSTROUTING ${line.replace(/^-A POSTROUTING\s+/, '')}`)
  }
  if (!kept) {
    sh(`${bin} -t nat -A POSTROUTING -s ${cidr} -o ${dev} -j MASQUERADE`)
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
  console.error(`seed-mtu: defaultDev=${dev || '(none)'} dbDevice=${row?.device || '(none)'}`)
  if (dev) {
    const cidrs = new Set(['10.8.0.0/24'])
    if (row?.ipv4_cidr) cidrs.add(row.ipv4_cidr)
    if (row && row.device !== dev) {
      db.prepare(
        `UPDATE interfaces_table SET device = ?, updated_at = datetime('now')`
      ).run(dev)
      try {
        const old = row.device || 'eth0'
        db.prepare(
          `UPDATE hooks_table SET
             post_up = REPLACE(REPLACE(post_up, ?, '-o {{device}}'), '-o eth0', '-o {{device}}'),
             post_down = REPLACE(REPLACE(post_down, ?, '-o {{device}}'), '-o eth0', '-o {{device}}'),
             updated_at = datetime('now')`
        ).run(`-o ${old}`, `-o ${old}`)
      } catch {
        /* no hooks_table */
      }
    }
    for (const cidr of cidrs) syncMasq(cidr, dev)
    console.error(`seed-mtu: MASQUERADE -o ${dev}`)
  }
} catch (err) {
  console.error(`seed-mtu: ${err}`)
  process.exit(0)
} finally {
  db.close()
}
