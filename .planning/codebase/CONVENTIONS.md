# Coding Conventions

**Analysis Date:** 2026-02-18

## Naming Patterns

**Files:**
- PascalCase for all Swift source files: `AppState.swift`, `AudioRecorder.swift`, `TranscriptionService.swift`
- One primary class/struct per file, named to match filename
- Extension files use `+` notation: `Notification+VoiceToText.swift`

**Functions:**
- camelCase for all function names: `startRecording()`, `handleHotkeyDown()`, `validateAPIKey()`
- Prefix with action verb: `start`, `stop`, `handle`, `load`, `save`, `validate`, `compute`, `format`
- Private helper functions use leading underscore convention: `_setupView()`, `_computeAudioLevel()`
- View builder functions: `settingsCard()`, `startupSection`, `vocabularySection`
- Boolean queries: `hasCompletedSetup`, `isRecording`, `isValidatingKey`, `canDeleteEntry()`

**Variables:**
- camelCase for all local and property variables: `audioRecorder`, `appState`, `isRecording`, `apiKey`
- Constants use camelCase with leading `let`: `let maxPipelineHistoryCount = 20`
- Storage key constants use camelCase: `apiKeyStorageKey`, `customVocabularyStorageKey`
- Abbreviations are expanded to words, not uppercase: use `audioLevel` not `audioLvl` or `AUDIOLEVEL`
- Underscore prefixed for private members: `_audioEngine`, `_tempFileURL`
- Weak self captures use descriptive names: `[weak self]` with guard checks

**Types:**
- PascalCase for enums: `HotkeyOption`, `SettingsTab`, `AudioRecorderError`, `TranscriptionError`
- Enum cases in camelCase: `.fnKey`, `.rightOption`, `.general`, `.runLog`
- Protocol names: `ObservableObject`, `Identifiable`, `LocalizedError` (follow Apple conventions)
- Class names: PascalCase, descriptive: `AppState`, `AudioRecorder`, `TranscriptionService`
- Struct names for Views: PascalCase: `SettingsView`, `GeneralSettingsView`, `MenuBarLabel`

## Code Style

**Formatting:**
- No explicit formatter configured; follows Swift style guide conventions
- 4-space indentation (standard Swift)
- Braces on same line (1TBS style): `if condition {` not `if condition\n{`
- No trailing whitespace
- Line wrapping when lines exceed ~100 characters

**Linting:**
- No linter configuration detected
- Code follows standard Swift conventions implicitly
- Type safety and optionals handled explicitly (no forced unwraps except where justified)

## Import Organization

**Order:**
1. Foundation and system frameworks: `import Foundation`, `import Combine`, `import AppKit`
2. Apple frameworks: `import AVFoundation`, `import CoreAudio`, `import SwiftUI`
3. Domain-specific frameworks: `import ServiceManagement`, `import ApplicationServices`, `import ScreenCaptureKit`
4. Logging: `import os.log`

**Path Aliases:**
- Not used in this codebase; all imports are direct framework imports
- No @_exported or underscore prefixed imports

## Error Handling

**Patterns:**
- Custom error enums implementing `LocalizedError` protocol: `AudioRecorderError`, `TranscriptionError`, `PostProcessingError`
- Error cases are explicit and descriptive: `.missingInputDevice`, `.invalidInputFormat(String)`, `.uploadFailed(String)`
- Error messages provide actionable guidance: `"Accessibility permission required. Grant access in System Settings > Privacy & Security > Accessibility."`
- Do-catch blocks for recoverable errors; explicit error types in throws
- Silent failures in cleanup paths: `try? FileManager.default.removeItem(at: url)`
- Timeout errors tracked: `TranscriptionError.transcriptionTimedOut(TimeInterval)`
- Task errors caught and handled in Task blocks with explicit error recovery

**Error Recovery:**
- Errors displayed to user via `appState.errorMessage` string (published property)
- Status text updated to "Error" when operations fail: `statusText = "Error"`
- Dialogs shown for permission-related errors with actionable buttons
- Transcription/post-processing errors fall back to raw transcript when LLM processing fails

## Logging

**Framework:** `os.log` (Apple's unified logging system)

**Patterns:**
- Create subsystem-specific loggers: `private let recordingLog = OSLog(subsystem: "com.zachlatta.freeflow", category: "Recording")`
- Log levels used: `.info` for normal flow, no `.debug` or `.error` visible
- Timing measurements included: `os_log(.info, log: recordingLog, "startRecording() complete: %.3fms total", (CFAbsoluteTimeGetCurrent() - t0) * 1000)`
- Formatted with public-scope placeholders: `os_log(..., "isRecording=%{public}d, isTranscribing=%{public}d", ...)`
- Used for performance tracking: buffer counts, timing checkpoints, state transitions
- No console.log or print() found in production code

## Comments

**When to Comment:**
- Block comments (MARK:) used heavily to organize large structs/classes: `// MARK: - General Settings`, `// MARK: Startup`
- Inline comments explain non-obvious logic: `// Simulate audio levels with a timer`, `// Ignore key repeat`
- Storage key comments document purpose: `private let apiKeyStorageKey = "groq_api_key"`
- Algorithm explanations: `// Fire ready callback on first non-silent buffer`
- No JSDoc/DocComment conventions observed; comments are sparse and pragmatic

**MARK: Organization:**
- Used to segment large files into logical sections
- Format: `// MARK: - Section Name` for main sections, `// MARK: Subsection` for subsections
- Visible in Xcode's code navigator

## Function Design

**Size:** Functions range from 3 lines to 200+ lines
- Small helper functions: 5-15 lines
- Service methods: 30-60 lines
- UI builder methods: 50-150 lines
- Complex pipeline handlers: 100-200 lines

**Parameters:**
- Avoid long parameter lists; prefer injecting dependencies via init or properties
- Use named parameters for clarity: `func makeMultipartBody(audioData: Data, fileName: String, model: String, boundary: String)`
- Default values used sparingly: `func deleteHistoryEntry(id: UUID)` (no defaults)
- Trailing closures for completion handlers: `onRecordingReady = { [weak self] in ... }`

**Return Values:**
- Explicit return types required: `-> String`, `-> URL?`, `-> [AudioDevice]`
- Optional returns for nullable results: `-> String?`, `-> URL?`
- Custom result types for complex returns: `PostProcessingResult` with named properties
- Void functions use implicit return (no explicit return statement)

## Module Design

**Exports:**
- All public types (enums, classes, structs) at module level
- No access modifiers beyond private/fileprivate (everything implicitly internal)
- Private implementation details marked with `private` or `private static`
- Weak references in closures captured as `[weak self]` to prevent cycles

**Barrel Files:**
- Not used; each file is independent
- View modifiers occasionally used: `extension View { ... }`
- Protocol extensions for default behavior (e.g., `extension HotkeyOption: Identifiable`)

## Published Properties & Observation

**Pattern:** SwiftUI reactive binding pattern used throughout
- `@Published` for observable state in `ObservableObject` classes: `@Published var isRecording = false`
- `@EnvironmentObject` to pass app state down view hierarchy: `@EnvironmentObject var appState: AppState`
- `@State` for local view state: `@State private var isValidatingKey = false`
- `@StateObject` for lifecycle-managed objects: `@StateObject private var githubCache = GitHubMetadataCache.shared`
- `@ObservedObject` for external observable objects: `@ObservedObject private var updateManager = UpdateManager.shared`
- Property observers used for side effects: `didSet { UserDefaults.standard.set(...) }`

## Async/Await Patterns

**Concurrency:**
- `async` functions for I/O operations: `async func transcribe(fileURL: URL) -> String`
- `async throws` for operations that can fail: `async func validateAPIKey(_ key: String) -> Bool`
- `await` keyword required at call sites
- `Task { ... }` for background work
- `Task.sleep(nanoseconds:)` for delays: `try await Task.sleep(nanoseconds: UInt64(indicatorDelay * 1_000_000_000))`
- `withThrowingTaskGroup` for racing operations (transcription + timeout): parallel execution with first-to-complete cancellation
- `MainActor.run { ... }` for UI updates from async context
- Weak self captures in async blocks to prevent cycles: `[weak self] in`

## Casting & Type Handling

**Pattern:** Explicit type checking with guard statements
- Guard-let pattern: `guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]`
- Optional chaining: `(response as? HTTPURLResponse)?.statusCode`
- Forced unwrapping only in safe contexts: `URL(string: "...")!` where URL is known valid
- Type casting with guard fallback: `guard httpResponse.statusCode == 200 else { throw ... }`

