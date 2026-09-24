## ADDED Requirements

### Requirement: Collabora first-run prerequisites

A site that enables OpenCloud office editing SHALL deploy Collabora with a persistent CA bundle that trusts Caddy `tls internal` and a `proof_key` available at `/etc/coolwsd/proof_key`. OpenCloud SHALL set `COLLABORATION_APP_PROOF_DISABLE=true` so CheckFileInfo succeeds when CODE does not send WOPI proof headers. First-run documentation SHALL list Redeploy **collabora** (and confirm `collabora-ca` healthy) as part of the OpenCloud working path, not only as a white-iframe recovery step.

#### Scenario: New site opens a document

- **WHEN** OpenCloud collaboration is enabled and Collabora is Deployed with `collabora-ca` healthy
- **THEN** opening an office file in the browser reaches Collabora without ProofKeys / issuer certificate failures that require rediscovering distroless CODE behavior
