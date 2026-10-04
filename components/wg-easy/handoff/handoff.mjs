// Translate the few wg and wg-quick invocations wg-easy makes into
// structured helper operations. genkey, pubkey, genpsk, and strip never
// reach this process.
import { connect } from 'node:net'
import { readFileSync } from 'node:fs'

const sock = process.env.WG_HELPER_SOCK || '/etc/wireguard/.wg-helper.sock'
const cmd = process.argv[2]
const args = process.argv.slice(3)

function fail(message) {
  process.stderr.write(`wg-helper: ${message}\n`)
  process.exit(127)
}

function frame(obj) {
  const body = Buffer.from(JSON.stringify(obj))
  const head = Buffer.alloc(4)
  head.writeUInt32BE(body.length)
  return Buffer.concat([head, body])
}

function readFrame(chunks) {
  const buf = Buffer.concat(chunks)
  if (buf.length < 4) return null
  const size = buf.readUInt32BE(0)
  if (buf.length < 4 + size) return null
  return JSON.parse(buf.subarray(4, 4 + size).toString('utf8'))
}

function operation() {
  if (cmd === 'wg' && args.length === 3 && args[0] === 'show' && args[2] === 'dump') {
    return { op: 'show', iface: args[1] }
  }
  if (cmd === 'wg' && args.length === 3 && args[0] === 'syncconf') {
    const source = args[2]
    if (!/^\/dev\/fd\/\d+$/.test(source)) fail('rejected command')
    return { op: 'sync', iface: args[1], config: readFileSync(source, 'utf8') }
  }
  if (cmd === 'wg-quick' && args.length === 2 && (args[0] === 'up' || args[0] === 'down')) {
    return { op: args[0], iface: args[1] }
  }
  fail('rejected command')
}

const payload = frame(operation())
const client = connect(sock)
const chunks = []
client.on('error', (err) => {
  process.stderr.write(`wg-helper: ${err.message}\n`)
  process.exit(1)
})
client.on('connect', () => {
  client.end(payload)
})
client.on('data', (chunk) => {
  chunks.push(chunk)
  const msg = readFrame(chunks)
  if (!msg) return
  if (msg.stdout) process.stdout.write(Buffer.from(msg.stdout, 'base64'))
  if (msg.stderr) process.stderr.write(Buffer.from(msg.stderr, 'base64'))
  process.exit(Number.isInteger(msg.code) ? msg.code : 1)
})
client.on('end', () => {
  if (!readFrame(chunks)) {
    process.stderr.write('wg-helper: no reply\n')
    process.exit(1)
  }
})
