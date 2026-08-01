#!/bin/bash
# Shared configuration for OpenClaw skills
# Source this file from any skill script using:
#   SKILLS_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
#   source "$SKILLS_ROOT/airtable-config/config.sh"

# Obsidian vault
OBSIDIAN_VAULT="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/2nd Brain (I)"

# Common vault subdirectories
OBSIDIAN_DAILY_NOTES="$OBSIDIAN_VAULT/3-Resources/Daily Notes"
OBSIDIAN_SOPS="$OBSIDIAN_VAULT/3-Resources/SOPs"
OBSIDIAN_ARCHIVE="$OBSIDIAN_VAULT/4-Archive"
OBSIDIAN_PEOPLE="$OBSIDIAN_VAULT/Extras/People"
OBSIDIAN_AI_CONTENT="$OBSIDIAN_VAULT/3-Resources/AI and Automation/Content Queue"
OBSIDIAN_AI_DIGESTS="$OBSIDIAN_VAULT/3-Resources/AI and Automation/AI Digests"
OBSIDIAN_AI_PROFILE="$OBSIDIAN_VAULT/3-Resources/AI and Automation/AI Interest Profile.md"

# Agent memory/logs
CLAWD_HOME="$HOME/clawd"
CLAWD_MEMORY="$CLAWD_HOME/memory"
CLAWD_LOGS="$CLAWD_HOME/logs"

# Voice Memos
VOICE_MEMOS_DIR="$HOME/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"
OBSIDIAN_VOICE_MEMOS="$OBSIDIAN_VAULT/3-Resources/Voice Memos"

# Skills root (derived from this script's location)
SKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
