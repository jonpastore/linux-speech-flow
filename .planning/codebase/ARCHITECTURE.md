# Architecture

**Analysis Date:** 2026-02-18

## Pattern Overview

**Overall:** SwiftUI-based macOS menu bar application with a stateful pipeline architecture for voice-to-text transcription.

**Key Characteristics:**
- Monolithic state management via `AppState` (Observable)
- Service-oriented business logic (Audio, Transcription, PostProcessing, Context)
- SwiftUI for all UI (menu bar dropdown, setup window, settings window)
- Integration with system frameworks (Accessibility, Audio, Screen capture)
- Asynchronous pipeline with multiple concurrent stages (recording → transcription → post-processing)

## Layers

**Presentation Layer:**
- Purpose: SwiftUI views and user interaction management
- Location: `Sources/App.swift`, `Sources/MenuBarView.swift`, `Sources/SettingsView.swift`, `Sources/SetupView.swift`, `Sources/PipelineDebugContentView.swift`, `Sources/RecordingOverlay.swift`
- Contains: View definitions, environment injection, state binding
- Depends on: `AppState` (environment object)
- Used by: Directly instantiated by SwiftUI app structure

**State Management Layer:**
- Purpose: Centralized state control and orchestration of entire application workflow
- Location: `Sources/AppState.swift`
- Contains: All published properties (UI state), lifecycle methods, permission handling, pipeline orchestration
- Depends on: `AudioRecorder`, `HotkeyManager`, `RecordingOverlayManager`, `AppContextService`, `TranscriptionService`, `PostProcessingService`, `UpdateManager`, `PipelineHistoryStore`, `KeychainStorage`
- Used by: All view layers via environment object

**Service Layer:**
- Purpose: Business logic isolated from state management
- Location: `Sources/AudioRecorder.swift`, `Sources/TranscriptionService.swift`, `Sources/PostProcessingService.swift`, `Sources/AppContextService.swift`, `Sources/HotkeyManager.swift`, `Sources/UpdateManager.swift`
- Contains: Specific concerns (audio capture, API calls, context gathering, hotkey monitoring)
- Depends on: System frameworks, URLSession for API calls
- Used by: `AppState`

**Data Persistence Layer:**
- Purpose: Pipeline history and configuration storage
- Location: `Sources/PipelineHistoryStore.swift`, `Sources/KeychainStorage.swift`
- Contains: CoreData management, Keychain access, file system operations
- Depends on: Foundation, CoreData
- Used by: `AppState`

**UI Components:**
- Purpose: Reusable visual components
- Location: `Sources/RecordingOverlay.swift`, `Sources/PipelineDebugPanelView.swift`
- Contains: Window management, overlay rendering
- Depends on: AppKit, SwiftUI
- Used by: `AppState`, Views

## Data Flow

**Recording Pipeline:**

1. User presses configured hotkey (Fn key, right Option, or F5)
2. `HotkeyManager.onKeyDown` callback fires
3. `AppState.handleHotkeyDown()` → `startRecording()` begins
4. `AudioRecorder.startRecording()` initializes AVAudioEngine on background thread
5. `AudioRecorder.onRecordingReady` fires when first non-silent audio arrives
6. `AppState` updates overlay from "Initializing..." to waveform visualization
7. `RecordingOverlay` receives live audio levels from `AudioRecorder.$audioLevel` publisher
8. Overlay displays animated waveform reflecting real-time audio level

**Transcription & Post-Processing Pipeline:**

1. User releases hotkey → `AppState.handleHotkeyUp()` → `stopAndTranscribe()`
2. `AudioRecorder.stopRecording()` returns audio file URL
3. Parallel task group starts:
   - `TranscriptionService.transcribe()` sends audio to Groq API (whisper-large-v3)
   - `AppContextService.collectContext()` (async) gathers app metadata and screenshot
4. Once transcription returns, `PostProcessingService.postProcess()` sends:
   - Raw transcript + captured context + custom vocabulary to Groq LLM
   - System prompt instructs model to fix spelling, grammar, remove fillers
5. Final transcript placed on pasteboard (clipboard)
6. `AppState.pasteAtCursor()` synthesizes Cmd+V keypress
7. Pipeline history entry recorded to CoreData via `PipelineHistoryStore`

**State Management:**

- `AppState` is `ObservableObject` with `@Published` properties
- Views subscribe via `@EnvironmentObject` binding
- State changes trigger SwiftUI re-renders
- Long-running tasks (transcription, context capture) use `Task` with `@MainActor` for UI updates
- Audio thread and background threads use DispatchQueue callbacks to sync to main actor

## Key Abstractions

**AppState:**
- Purpose: Central orchestrator for entire application lifecycle
- Examples: `Sources/AppState.swift`
- Pattern: Observable singleton pattern (created in AppDelegate, injected via environment)

**Service Classes:**
- Purpose: Isolated, stateless business logic for specific domain
- Examples: `AudioRecorder` (AVAudioEngine wrapper), `TranscriptionService` (Groq API client), `PostProcessingService` (LLM text refinement), `AppContextService` (app introspection + screenshot capture)
- Pattern: Request-response with async/await, error handling via custom error enums

**Environment Objects:**
- Purpose: Cross-cutting state available to all views without prop drilling
- Example: `AppState` injected via `.environmentObject()` at app root
- Pattern: SwiftUI's dependency injection mechanism

**Overlay Manager:**
- Purpose: Visual feedback for recording state (waveform visualization)
- Example: `RecordingOverlayManager` in `Sources/RecordingOverlay.swift`
- Pattern: Manages separate NSWindow for fullscreen recording indicator

## Entry Points

**App Launch:**
- Location: `Sources/App.swift`
- Triggers: macOS launches FreeFlow
- Responsibilities: Creates `AppDelegate` via `@NSApplicationDelegateAdaptor`, sets up menu bar extra with `MenuBarExtra` scene, injects `appState` as environment object

**AppDelegate Initialization:**
- Location: `Sources/AppDelegate.swift`
- Triggers: Application lifecycle event
- Responsibilities: Creates `AppState` singleton, observes notifications for setup/settings window requests, starts hotkey/accessibility monitoring on app launch

**Recording Initiation:**
- Location: `Sources/HotkeyManager.swift` → `AppState.handleHotkeyDown()`
- Triggers: Hotkey press detected
- Responsibilities: Validates permissions, starts audio capture, initializes recording overlay

**Post-Processing:**
- Location: `Sources/AppState.stopAndTranscribe()`
- Triggers: Hotkey release or manual stop
- Responsibilities: Coordinates transcription + context capture in parallel, applies post-processing, pastes result

## Error Handling

**Strategy:** Localized error handling at service layer with user-facing alerts in `AppState`.

**Patterns:**

- **Audio Errors:** `AudioRecorderError` enum (invalidInputFormat, missingInputDevice) caught in `startRecording()` with formatted error messages displayed to user
- **Transcription Errors:** `TranscriptionError` enum (uploadFailed, submissionFailed, transcriptionTimedOut) caught via task group timeout mechanism
- **Post-Processing Errors:** `PostProcessingError` enum with fallback to raw transcript if LLM fails
- **API Errors:** HTTP status checks in service layer, 200-only success path, non-200 responses parsed for error details
- **Permission Errors:** Caught early in `startRecording()` (accessibility, microphone, screen recording checks) with alerts offering direct System Settings links

**Fallbacks:**
- Context capture fails → uses text-only post-processing path
- Post-processing fails → uses raw transcript
- Screenshot capture fails → continues with app metadata only
- API key validation → graceful degradation (no context inference without key)

## Cross-Cutting Concerns

**Logging:** OS Log framework (`os.log`) with custom log category `com.zachlatta.freeflow.Recording` for detailed timing data; performance measurements (CFAbsoluteTime) logged at key checkpoints.

**Validation:**
- API key validation via test endpoint call in `TranscriptionService.validateAPIKey()`
- Microphone access validated before recording via `AVCaptureDevice.authorizationStatus()`
- Accessibility permissions checked via `AXIsProcessTrusted()`
- Screen recording permission checked via `CGPreflightScreenCaptureAccess()`

**Authentication:** Groq API key stored in Keychain (via `KeychainStorage`) with environment injection into service classes. No tokens persisted in UserDefaults or files.

**Threading:**
- UI updates always on MainActor
- Audio processing on background audio thread
- Recording startup on `DispatchQueue.global(qos: .userInitiated)` to prevent blocking
- API calls via URLSession (background threads by default)
- Accessibility queries on main thread (required by framework)

**Concurrency Model:**
- `Task` for async/await workflows
- `DispatchQueue` for audio thread isolation and background work
- `withThrowingTaskGroup` for timeout racing (transcription/post-processing)
- `@Published` properties with Combine publishers for reactive state binding

---

*Architecture analysis: 2026-02-18*
