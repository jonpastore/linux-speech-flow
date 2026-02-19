# Technology Stack

**Analysis Date:** 2026-02-18

## Languages

**Primary:**
- Swift - Used for all application code, macOS app written entirely in Swift

## Runtime

**Environment:**
- macOS 13.0+ (LSMinimumSystemVersion in Info.plist)
- Apple Silicon (arm64) + Intel (x86_64) universal binary support

**Build System:**
- Native Swift compiler (swiftc)
- Makefile-based build orchestration (`/home/jon/projects/freeflow/Makefile`)
- Universal binary creation via `lipo` for multi-architecture support

## Frameworks

**Core UI:**
- SwiftUI - Modern declarative UI framework used throughout the app
  - MenuBarExtra for menu bar presence
  - NSHostingView for embedding SwiftUI in AppKit windows
  - Used in: `App.swift`, `MenuBarView.swift`, `SettingsView.swift`, `SetupView.swift`, `RecordingOverlay.swift`

**Application Architecture:**
- AppKit (NSApplication, NSApplicationDelegate, NSWindow, NSAlert) - macOS native application framework
- Combine - Reactive framework for state management and asynchronous operations

**System Integration:**
- AVFoundation - Audio recording and device enumeration (`AudioRecorder.swift`)
- CoreAudio - Low-level audio device management (`AudioRecorder.swift`, `AppState.swift`)
- ServiceManagement - Launch-at-login functionality (`AppState.swift`, `SettingsView.swift`)
- ApplicationServices - Accessibility API for context capture and text insertion (`AppContextService.swift`, `AppState.swift`)
- ScreenCaptureKit - Screenshot capture for context awareness (`AppState.swift`)
- Carbon - Low-level event handling for global hotkey monitoring (`HotkeyManager.swift`)
- Security - Keychain access for credential storage (legacy, see `KeychainStorage.swift`)
- Foundation - Core utilities and networking

**Logging:**
- os.log - Apple's native structured logging framework (`recordingLog` in `AppState.swift`)

**Persistence:**
- CoreData - Historical pipeline storage (`PipelineHistoryStore.swift`)
- UserDefaults - Application preferences and settings (`AppState.swift`, `UpdateManager.swift`)
- File system storage - JSON-based settings storage in application support directory (`KeychainStorage.swift`)

## Key Dependencies

**None external (no package manager):**
- All dependencies are native macOS/Swift frameworks
- No CocoaPods, SPM, or third-party package dependencies

## Configuration

**Environment:**
- API Key storage: Stored in plaintext JSON file in `~/Library/Application Support/FreeFlow/.settings`
  - Migrated from Keychain in previous versions
  - Account key: `"groq_api_key"`
- Custom vocabulary storage via UserDefaults key: `"custom_vocabulary"`
- Microphone selection via UserDefaults key: `"selected_microphone_id"`
- Hotkey configuration via UserDefaults key: `"hotkey_option"`
- Launch-at-login via macOS ServiceManagement API

**Build:**
- `Makefile` at project root
- `Info.plist` for bundle metadata and system permissions
- `FreeFlow.entitlements` for code signing
- Compiler flags for multi-architecture support: `-target arm64-apple-macosx13.0`, `-target x86_64-apple-macosx13.0`

**System Permissions Required:**
- `NSMicrophoneUsageDescription` - Microphone access (Info.plist)
- `NSSpeechRecognitionUsageDescription` - Speech recognition (Info.plist)
- `NSAccessibilityUsageDescription` - Accessibility for text insertion (Info.plist)

## Platform Requirements

**Development:**
- macOS with Swift compiler (swiftc)
- Xcode command line tools for SDK access
- Apple Silicon or Intel Mac
- Standard Unix tools (cp, plutil, lipo, hdiutil, bash)

**Production:**
- macOS 13.0 or later
- Distributed via `.dmg` (disk image) file
- Code signed and notarized for distribution

---

*Stack analysis: 2026-02-18*
