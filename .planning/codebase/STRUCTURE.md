# Codebase Structure

**Analysis Date:** 2026-02-18

## Directory Layout

```
freeflow/
├── Sources/                              # All Swift source code
│   ├── App.swift                         # SwiftUI app root entry point
│   ├── AppDelegate.swift                 # Application lifecycle and window management
│   ├── AppState.swift                    # Central state management (36KB)
│   ├── AppContextService.swift           # App metadata and screenshot capture (25KB)
│   ├── AudioRecorder.swift               # Audio engine and device management (14KB)
│   ├── TranscriptionService.swift        # Groq whisper API integration
│   ├── PostProcessingService.swift       # Groq LLM text refinement
│   ├── HotkeyManager.swift               # Global hotkey event monitoring
│   ├── UpdateManager.swift               # App versioning and auto-update checks (18KB)
│   ├── KeychainStorage.swift             # Secure API key storage
│   ├── PipelineHistoryStore.swift        # CoreData persistence layer (8.7KB)
│   ├── PipelineHistoryItem.swift         # Pipeline history data model
│   ├── RecordingOverlay.swift            # Waveform visualization window (15KB)
│   ├── MenuBarView.swift                 # Menu bar dropdown UI (7.9KB)
│   ├── SettingsView.swift                # Settings window UI (44KB)
│   ├── SetupView.swift                   # Initial setup wizard (41KB)
│   ├── PipelineDebugContentView.swift    # Pipeline inspector UI (6.7KB)
│   ├── PipelineDebugPanelView.swift      # Debug panel container (1.6KB)
│   └── Notification+VoiceToText.swift    # Custom notification extensions (100B)
├── Resources/                            # App icon and assets
├── Info.plist                            # App metadata and permissions
├── FreeFlow.entitlements                 # macOS sandbox entitlements
├── Makefile                              # Build and development commands
├── .github/                              # GitHub workflows
├── .planning/                            # Documentation (generated)
└── README.md                             # Project description
```

## Directory Purposes

**Sources:**
- Purpose: All Swift source code for the application
- Contains: Services, views, state management, data persistence
- Key files: `AppState.swift` (36KB, core orchestration), `SettingsView.swift` (44KB, complex UI)

**Resources:**
- Purpose: Asset files (app icon)
- Contains: PNG image files
- Key files: `AppIcon-README.png`

**.planning/codebase/:**
- Purpose: Generated architecture documentation
- Contains: ARCHITECTURE.md, STRUCTURE.md, and other analysis docs
- Generated: Yes, by `/gsd:map-codebase` command
- Committed: Yes

## Key File Locations

**Entry Points:**

- `Sources/App.swift`: SwiftUI `@main` app struct, creates menu bar extra with root view
- `Sources/AppDelegate.swift`: macOS application delegate, manages window lifecycle and initialization
- `Resources/Info.plist`: App metadata (bundle identifier, version, permissions)
- `FreeFlow.entitlements`: Sandbox permissions (audio input, screen recording, accessibility)

**Core State Management:**

- `Sources/AppState.swift`: Central `ObservableObject` coordinating all subsystems (audio, transcription, permissions, history)

**Service Layer:**

- `Sources/AudioRecorder.swift`: AVAudioEngine wrapper with buffer tap for waveform visualization
- `Sources/TranscriptionService.swift`: Groq whisper-large-v3 API client
- `Sources/PostProcessingService.swift`: Groq LLM text refinement with context injection
- `Sources/AppContextService.swift`: App introspection (bundle, window title, selected text) and screenshot capture via CoreGraphics
- `Sources/HotkeyManager.swift`: NSEvent global/local event monitors for hotkey detection
- `Sources/UpdateManager.swift`: Version checking and download progress tracking

**Data Persistence:**

- `Sources/PipelineHistoryStore.swift`: CoreData stack (NSPersistentContainer) for pipeline run history
- `Sources/KeychainStorage.swift`: Keychain access for sensitive API key storage

**UI Views:**

- `Sources/MenuBarView.swift`: Primary menu bar dropdown (status, buttons, permissions warnings)
- `Sources/SettingsView.swift`: Tabbed settings window (General + Run Log tabs)
- `Sources/SetupView.swift`: Initial onboarding/setup wizard
- `Sources/RecordingOverlay.swift`: Full-screen recording indicator with waveform visualization
- `Sources/PipelineDebugContentView.swift`: Detailed pipeline run inspector

**Build & Configuration:**

- `Makefile`: Contains `make build`, `make run`, `make archive` targets
- `Info.plist`: Bundle name, version, minimum OS, permissions declarations
- `FreeFlow.entitlements`: Audio input (kAudioHardwarePropertyDevices), Screen recording (CGWindow APIs), Accessibility (AXUIElement APIs)

## Naming Conventions

**Files:**

- PascalCase for all file names: `AppState.swift`, `AudioRecorder.swift`, `HotkeyManager.swift`
- Suffixes indicate purpose: `*Service.swift` (business logic), `*View.swift` (UI), `*Manager.swift` (lifecycle/state), `*Store.swift` (persistence)

**Directories:**

- `Sources/` for Swift code
- `Resources/` for assets
- `.planning/codebase/` for documentation

**Classes/Structs:**

- PascalCase: `AppState`, `AudioRecorder`, `TranscriptionService`
- Enums: `HotkeyOption`, `SettingsTab`, `AudioRecorderError`
- Prefixed errors: `*Error` (TranscriptionError, PostProcessingError)

**Functions:**

- camelCase: `startRecording()`, `stopAndTranscribe()`, `focusedWindowTitle()`
- Private functions prefixed: `private func` (not using underscore prefix)

**Properties:**

- `@Published` for observable state: `isRecording`, `lastTranscript`, `pipelineHistory`
- Private storage without prefix: `private var audioEngine`, `private var smoothedLevel`
- Constants: UPPER_CASE in enums, camelCase for properties

## Where to Add New Code

**New Feature (e.g., new transcription provider):**
- Primary code: Create new service file `Sources/NewProviderService.swift` following pattern of `TranscriptionService.swift`
- Integration: Add property to `AppState.swift` and call from appropriate lifecycle method
- Tests: Not currently in repo, but would go in `Tests/` directory if added

**New UI Component/View:**
- Implementation: Create in `Sources/ComponentView.swift` as `struct ComponentView: View`
- Environment: Inject `@EnvironmentObject var appState: AppState` if state needed
- Used by: Reference in parent view where needed

**New Permission or System Integration:**
- Implementation: Add to `AppState.swift` lifecycle methods (e.g., `startAccessibilityPolling()`)
- UI: Add permission check + warning button to `MenuBarView.swift`

**New Service/Manager (background task):**
- Location: `Sources/NewService.swift`
- Pattern: Follow `UpdateManager.swift` or `HotkeyManager.swift` for callback-based initialization
- Ownership: Create instance in `AppState.init()` and manage lifecycle there

**Configuration/Constants:**
- Storage: Add to top of relevant service file (e.g., `private let apiKey` in service constructor)
- Or: Add enum with cases to top of `AppState.swift` for UI constants (`HotkeyOption`, `SettingsTab`)

**Data Model:**
- Location: Create as struct in `Sources/ModelName.swift` (e.g., `PipelineHistoryItem.swift`)
- Persistence: If using CoreData, add entity to store model and helper in `PipelineHistoryStore.swift`
- Codable: Make models conform to `Codable` if serializing to JSON

## Special Directories

**.planning/codebase/:**
- Purpose: Contains architecture and structure documentation
- Generated: Yes (created by `/gsd:map-codebase` command)
- Committed: Yes (part of repo)

**.github/:**
- Purpose: GitHub Actions CI/CD workflows
- Committed: Yes

**Resources/:**
- Purpose: App assets (icons, images)
- Generated: No (manually maintained)
- Committed: Yes

---

*Structure analysis: 2026-02-18*
