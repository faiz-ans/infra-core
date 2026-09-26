## MODIFIED Requirements

### Requirement: Templated services.yaml
Homepage SHALL run on a workload host that lists it. Its config SHALL be generated or substituted by SET from desired topology (domain, placed services, official pack). Operators MUST NOT hand-copy Homepage YAML onto the host.

#### Scenario: Domain is not committed
- **WHEN** Homepage config is read from git
- **THEN** hrefs use topology variables rather than a literal live domain

### Requirement: Public href, internal widget URL
Each catalogued service entry SHALL use a public href through the ingress host. Widget, ping, or siteMonitor URLs for **host-netns** services on the same machine SHALL use pasta host-loopback `169.254.1.2` and the service port. Same `site` network names MAY be used when both sides are on that network. Other-host scrapes SHALL use that host’s IP. The Pi-hole v6 widget key SHALL be the Pi-hole web password.

#### Scenario: PeaNUT tile from site network
- **WHEN** Homepage is on `site` and PeaNUT is host-net on `:8092`
- **THEN** the widget URL is `http://169.254.1.2:8092` and not the NAS LAN IP

### Requirement: Podman status dots, no Komodo
Homepage MAY mount the workload user’s Podman API socket for status dots. It MUST NOT require Komodo API keys. Host stats SHALL use Glances when that engine is selected.

#### Scenario: No Komodo keys
- **WHEN** Homepage is SET
- **THEN** `HOMEPAGE_VAR_KOMODO_*` is not required
