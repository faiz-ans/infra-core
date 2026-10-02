# infra-core

Site-agnostic on-prem catalog. Desired topology is a local `site.yaml` (gitignored). Observed state is a local `observed.yaml` (gitignored). Apply is push-based Ansible from the operator machine.

```
Day 0   python3 ansible/site.py get --task a --host 10.0.0.10,admin
        # prints a scaffold; copy to site.yaml. Does not overwrite an existing desired file.
Day 1   edit site.yaml   # schema: schema/site.schema.json
        python3 ansible/site.py set --secrets secrets.yaml
Day 2   python3 ansible/site.py apply   # GET A+B → observed.yaml, then SET delta
```

`examples/site.example.yaml` is the placeholder topology. Encrypt secrets with Age/SOPS (`examples/secrets.example.yaml`). The Age key stays on the runner; SET installs Podman secrets. Hosts never get a `site.env`.

## What SET does

Two host roles: **storage** (native mounts, Samba for people, inferred NFS for apps) and **workload** (Podman Quadlets). Official services live under `components/` plus OpenLDAP. OpenMediaVault is not used. Cockpit is a host package on hosts with `admin-gui: true` (default false). Homepage and Glances are ordinary listed services. Windows/HTPC under `windows/` is not driven by GET/SET.

SET may delete accounts. It never deletes user or group home data.

## Layout

| Path | Role |
|---|---|
| `schema/site.schema.json` | Desired topology schema |
| `examples/` | Placeholder site + secrets |
| `ansible/` | `site.py`, playbooks `get.yml` / `set.yml`, roles |
| `components/` | Official Quadlets + `pack.yaml` |
| `windows/` | Unhooked from GET/SET |
| `archive/bootstrap/` | Retired `apply.sh` / OMV / first-run tree |

## Requirements

- Operator: Python 3, Ansible, PyYAML (`pip install -r ansible/requirements.txt`), `sops` + Age when secrets are encrypted.
- Hosts: Debian or Ubuntu only. SSH as a host sysadmin.
