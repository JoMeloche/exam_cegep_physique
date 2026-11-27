# macOS app

`ExamGen-<version>-macos-arm64.dmg` (Apple Silicon: M1 and later) and
`ExamGen-<version>-macos-x86_64.dmg` (Intel Macs). macOS 11 or later. LaTeX (TinyTeX with the
packages in `tex-packages.txt`) and the starter question bank are inside the app; nothing else to install.
The library is created in `~/exam_app` on first launch.

## Getting the .dmg

- **GitHub Actions**: workflow *Build macOS app* (`.github/workflows/build-macos.yml`) runs on every pull
  request touching `app/`, on demand (Actions tab, *Run workflow*), and on `v*` tags. Each run keeps the
  two .dmg files as artifacts; a `v*` tag also attaches them to the GitHub release.
- **On a Mac**: Python 3.12, Node 20+, then from `app/`: `bash packaging/build_macos.sh`
  → `packaging/dist/ExamGen-<version>-macos-<arch>.dmg` (built for that Mac's own architecture).

## Installing (unsigned app)

1. Open the .dmg and drag **ExamGen** onto **Applications**.
2. The first time, macOS blocks it ("Apple could not verify…") because it is not signed with an
   Apple Developer ID:
   - macOS 15 Sequoia and later: double-click the app, click **Done**, then open
     **System Settings → Privacy & Security**, scroll down to *"ExamGen" was blocked*, click
     **Open Anyway**, and confirm with your password.
   - macOS 14 and earlier: right-click (Control-click) the app in Applications → **Open** → **Open**.
3. After that it opens normally. If macOS says the app is "damaged", run once in Terminal:
   `xattr -dr com.apple.quarantine /Applications/ExamGen.app`

## Signing and notarization (removes step 2)

Needs an Apple Developer Program membership (99 USD/year) and a *Developer ID Application* certificate.
`build_macos.sh` already handles it when these are set:

- `MACOS_SIGN_IDENTITY="Developer ID Application: Name (TEAMID)"` signs the TeX binaries and the app
  with the hardened runtime, then the .dmg.
- `MACOS_NOTARY_PROFILE=<profile>` (created once with `xcrun notarytool store-credentials`) submits the
  .dmg to Apple's notary service and staples the ticket.

In GitHub Actions this means storing the certificate (.p12, base64) and its password, plus an App Store
Connect API key, as repository secrets and importing them into a temporary keychain before the build step.
