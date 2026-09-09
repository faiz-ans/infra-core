# Seed catalog defaults in wg-easy v15 SQLite. No INIT_MTU / INIT_DEVICE.
# - Factory client MTU 1420 → 1280 (operator-chosen MTU is left alone).
# - Device + live MASQUERADE follow the current default IPv4 route iface.
#   Prefer an UP iface with a gateway. Skip DOWN / no-carrier (NIC swaps leave
#   a stale default on eth0). Node often has no /usr/sbin on PATH, so PostUp
#   writes iptables and this seed never sees the rule.
#   Re-apply after wg-easy PostUp, which otherwise restores -o eth0.
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
  const lan = ifaceForAddr(process.env.INIT_DNS || process.env.NAS_LAN_IP || '')
  if (lan && cands.some((c) => c.iface === lan)) return lan
  if (cands[0]) return cands[0].iface
  if (lan) return lan

  const m = sh('ip -4 route get 1.1.1.1 2>/dev/null').match(/\bdev\s+(\S+)/)
  const dev = m ? m[1] : ''
  return skipIface(dev) || !operUp(dev) ? '' : dev
}

function iptablesBins() {
  const bins = []
  for (const b of ['/usr/sbin/iptables', '/usr/sbin/iptables-nft', '/usr/sbin/iptables-legacy', 'iptables']) {
    if (b.startsWith('/') && !existsSync(b)) continue
    if (!bins.includes(b)) bins.push(b)
  }
  return bins.length ? bins : ['iptables']
}

function natLines(bin) {
  return sh(`${bin} -t nat -S POSTROUTING`)
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
}

function syncMasq(cidr, dev) {
  if (!cidr || !dev) return
  for (const bin of iptablesBins()) {
    for (const line of natLines(bin)) {
      if (!line.includes('MASQUERADE') || !line.includes(`-s ${cidr}`)) continue
      const om = line.match(/-o\s+(\S+)/)
      const odev = om ? om[1] : ''
      if (odev && odev !== dev) {
        sh(`${bin} -t nat -D POSTROUTING ${line.replace(/^-A POSTROUTING\s+/, '')}`)
      }
    }
    const has = natLines(bin).some(
      (l) =>
        l.includes('MASQUERADE') &&
        l.includes(`-s ${cidr}`) &&
        l.includes(`-o ${dev}`)
    )
    if (!has) {
      sh(`${bin} -t nat -A POSTROUTING -s ${cidr} -o ${dev} -j MASQUERADE`)
    }
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
  if (row && dev) {
    if (row.device !== dev) {
      db.prepare(
        `UPDATE interfaces_table SET device = ?, updated_at = datetime('now')`
      ).run(dev)
    }
    try {
      const old = row.device && row.device !== dev ? row.device : 'eth0'
      db.prepare(
        `UPDATE hooks_table SET
           post_up = REPLACE(REPLACE(post_up, ?, '-o {{device}}'), '-o eth0', '-o {{device}}'),
           post_down = REPLACE(REPLACE(post_down, ?, '-o {{device}}'), '-o eth0', '-o {{device}}'),
           updated_at = datetime('now')`
      ).run(`-o ${old}`, `-o ${old}`)
    } catch {
      /* no hooks_table */
    }
    syncMasq(row.ipv4_cidr, dev)
    console.error(`seed-mtu: MASQUERADE -s ${row.ipv4_cidr} -o ${dev}`)
  }
} catch (err) {
  console.error(`seed-mtu: ${err}`)
  process.exit(0)
} finally {
  db.close()
}
