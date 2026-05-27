## MODIFIED Requirements

### Requirement: Onboarding 时提示备份 active 目录
`/search-skill-setup`（插件命名空间下为 `/search-crew:search-skill-setup`）首次运行时 MUST 醒目提示用户：`~/.config/search-crew/` 是长期沉淀；强烈建议放 iCloud / Dropbox / dotfiles 仓库（原位置改软链接），或定期手动备份。提示同步写入 `~/.config/search-crew/backup-info.md` 让用户随时能查。

**Lock**: user-confirmed
**Confirmed-At**: 2026-05-26

#### Scenario: 首次 /search-skill-setup
- **WHEN** 用户首次跑 `/search-skill-setup` 命令
- **THEN** 输出中含醒目的备份建议段落（不是淹没在长 text 中间一行）；`backup-info.md` 已写入 active 目录
