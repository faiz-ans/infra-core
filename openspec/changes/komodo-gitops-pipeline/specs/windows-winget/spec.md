## ADDED Requirements

### Requirement: Winget stub only
The repository SHALL include a `windows/` winget package list (or equivalent export) covering intended HTPC apps (Kodi, AutoHotkey, Firefox, Steam, Dolphin, ePSXe, PCSX2, and Docker Desktop as needed for the HTPC engine). This change SHALL NOT implement Playnite retirement, Kodi-as-launcher, AHK scripts, or Firefox kiosk configuration.

#### Scenario: List exists without cutover
- **WHEN** the catalog is cloned
- **THEN** `windows/` contains a winget manifest or package list, and no Kodi launcher cutover automation is required for this change to be complete
