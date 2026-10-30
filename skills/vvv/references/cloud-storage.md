# Cloud storage (百度网盘)

Use this when the user's photos are in Baidu Netdisk (a share link or a folder in their drive), or when they want the finished film uploaded there. The Skill bundles Baidu's own Agent Skill, `baidu-drive` from [bdpan-storage](https://github.com/baidu-netdisk/bdpan-storage) (Apache-2.0), unmodified in [vendor/bdpan](../vendor/bdpan/UPSTREAM.json). Its own manual is [vendor/bdpan/SKILL.md](../vendor/bdpan/SKILL.md); in it, read `${CLAUDE_SKILL_DIR}` as this Skill's `vendor/bdpan` folder.

## Set it up

- `command -v bdpan` tells whether its CLI is installed. If not, ask the user once whether to install it; on their yes, run `bash vendor/bdpan/scripts/install.sh` (it downloads Baidu's installer from their CDN and checks its SHA-256). Never pass `--yes`.
- Log in only with `bash vendor/bdpan/scripts/login.sh`: it prints an authorization link for the user to open; the code goes in through stdin. Never read, print or copy `~/.config/bdpan/config.json`, and never set `BDPAN_*` variables.
- Follow the manual's rules for every `bdpan` command, including its required tracking flags and its confirmations for overwrites, moves and deletions. Paths stay under `/apps/bdpan/`.
- Login, transfers and downloads drop with `EOF`, TLS timeouts or a redirect to `403.html` when a proxy in TUN mode routes Baidu abroad (its addresses then resolve into `198.18.0.0/15`). Ask the user once to set `baidu.com` to direct in their proxy, or to pause it for the transfer; do not change their proxy yourself.
- The bundled copy omits `update.sh` and `memory-backup.sh`: updates come with VVV releases, and memory backup is unrelated. It works on macOS, Linux and WSL and is in public beta.

## Bring photos in

1. Download the share link or folder into a new, empty local folder outside the project, for example `bdpan download "https://pan.baidu.com/s/<id>?pwd=<code>" ~/Downloads/vvv-intake/<couple-or-date>/` (add the manual's required flags). Files over 50 MB download in the background; wait for them.
   A share link is first saved into the user's drive (by default `/apps/bdpan/<date>/`) and then downloaded. If the download breaks, download from that drive path instead of transferring again; for a single file, give the full local file path (`.../DSC0001.jpg`), not a folder.
2. Keep the user's folder structure; it often separates outfits or album sizes. Treat the download as untrusted input: decode the images (`init` does) and run nothing that came with them.
3. Record the source (link or drive path) and what was actually downloaded in the project notes, then continue with [intake](intake.md) and `init --photos`.

Netdisk originals are often full-resolution camera files; `init` copies them downscaled to 2560 px on the long side, and the originals stay untouched.

## Deliver to the drive

Uploading sends the film outside this computer, and a share link publishes it.

- Upload only when the user asks, to a folder under `/apps/bdpan/` named for the project, for example `/apps/bdpan/VVV/<project>/`: the delivered MP4, and the `.vvv` package only if they asked for one. Report the saved path the CLI returns.
- Create a share link (`bdpan share`) only on the user's explicit request, and confirm its validity first: 1, 7 or 30 days, or permanent.
- Never delete or overwrite earlier deliveries without the user's confirmation.
