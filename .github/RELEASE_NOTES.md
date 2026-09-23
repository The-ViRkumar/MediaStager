Batch-renames TV episodes and movies into Jellyfin/Plex-correct filenames
and folders — Series or Movie mode, `guessit`-powered parsing, TMDB
enrichment, sidecar/artwork sync, a batch queue across multiple folders,
and one-click undo. Full usage and feature guide in the
[README](https://github.com/The-ViRkumar/MediaStager#readme).

### Download

No installation needed — pick your platform below and run it directly.

| Platform | File |
|---|---|
| Windows | `MediaStager-<version>-windows.exe` |
| macOS | `MediaStager-<version>-macos` |
| Linux | `MediaStager-<version>-linux` |

**macOS / Linux:** mark it executable first, then run it:
```bash
chmod +x MediaStager-<version>-macos   # or -linux
./MediaStager-<version>-macos
```

**macOS Gatekeeper:** this build isn't notarized, so the first launch may
be blocked. Right-click the file → **Open** to approve it once, or run
`xattr -d com.apple.quarantine MediaStager-<version>-macos` if needed.

---
