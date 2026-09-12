#!/usr/bin/env node
// Compose interpolates `$` in `.env` (both project file and env_file).
// Reload Komodo's file literally, then exec Homepage's entrypoint.
const fs = require("fs");
const { spawn } = require("child_process");

const envPath = "/run/komodo.env";
if (fs.existsSync(envPath)) {
  for (const raw of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    if (!raw || raw.trimStart().startsWith("#")) continue;
    const i = raw.indexOf("=");
    if (i < 1) continue;
    const left = raw.slice(0, i);
    const k = left.trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(k)) continue;
    let v = raw.slice(i + 1);
    if (left.endsWith(" ") && v.startsWith(" ")) v = v.slice(1);
    if (
      (v.startsWith('"') && v.endsWith('"') && v.length >= 2) ||
      (v.startsWith("'") && v.endsWith("'") && v.length >= 2)
    ) {
      v = v.slice(1, -1);
    }
    process.env[k] = v;
  }
}

const args = process.argv.slice(2);
if (args.length === 0) {
  process.stderr.write("load-komodo-env: missing command\n");
  process.exit(1);
}
const child = spawn(args[0], args.slice(1), { stdio: "inherit", env: process.env });
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 1);
});
