# Codebase Concerns

**Analysis Date:** 2026-02-18

## Tech Debt

**Silent Error Handling in Audio Operations:**
- Issue: Multiple locations use `try?` and empty `catch {}` blocks that suppress errors without logging
- Files: `Sources/AudioRecorder.swift` (line 217), `Sources/AppState.swift` (lines 541, 1023), `Sources/SettingsView.swift` (line 1023)
- Impact: Failed audio writes, file operations, or playback errors are silently lost, making debugging difficult and audio loss possible
- Fix approach: Replace with proper error logging or propagate errors to UI. Example: `audioFile = nil` error at line 217 of AudioRecorder should log the reason before clearing the file reference.

**Silent File System Failures:**
- Issue: Directory creation and file operations in multiple places use `try?` without error handling or user notification
- Files: `Sources/KeychainStorage.swift` (lines 12, 46, 54, 56, 58), `Sources/PipelineHistoryStore.swift` (line 14), `Sources/AppState.swift` (lines 166, 184)
- Impact: Data loss if storage directory cannot be created, audio files cannot be saved, or pipeline history cannot be persisted. User sees no indication.
- Fix approach: Log errors and show user alerts for critical operations (audio save, history save). Fall back to alternatives if available.

**Weak Permission Checking During Recording:**
- Issue: Screenshot capture permission failure stops recording mid-flow (`Sources/AppState.swift`, lines 785-812), but microphone permission is checked after recording starts
- Files: `Sources/AppState.swift` (lines 358-382), (lines 785-812)
- Impact: User records audio expecting it to work, then discovers screenshot permission is required and recording is aborted
- Fix approach: Pre-flight check all required permissions (mic + screenshot) before entering recording UI state, not during

## Known Bugs

**Accessibility Permission Alert Trigger:**
- Symptoms: Screenshot capture errors trigger "Accessibility Permission Required" alert that doesn't match the actual issue
- Files: `Sources/AppState.swift` (line 794 `isScreenCapturePermissionError` check), (line 819 alert messaging)
- Trigger: When screenshot capture permission is missing, the error message says "Accessibility Permission Required" instead
- Workaround: Check system settings to confirm which permission is actually missing

**Potential Memory Leak in Audio Device Listener:**
- Symptoms: Audio device listener block may retain self, causing circular references
- Files: `Sources/AppState.swift` (lines 284-302)
- Trigger: Listener is installed but never explicitly removed, only via deinit
- Workaround: None currently. Listener should be cleaned up in `stopAccessibilityPolling()`

**Empty Catch Blocks Hide Transcription Failures:**
- Symptoms: Transcription task failures in async context are caught and silently dropped
- Files: `Sources/SetupView.swift` (line 941: `recorder.cleanup()` in Task without error propagation)
- Trigger: Network errors, API errors during test transcription are logged to console but not shown to user
- Workaround: Check console output to diagnose transcription failures

## Security Considerations

**API Key Storage Using Simple File-Based Keychain:**
- Risk: API keys stored in `~/Library/Application Support/FreeFlow/` using basic file encryption with JSON serialization
- Files: `Sources/KeychainStorage.swift` (entire file — uses plaintext JSON with file permissions)
- Current mitigation: File permissions set to 0o600 (owner read/write only)
- Recommendations:
  - Use system Keychain API (`Security.framework`) instead of custom file-based storage for sensitive keys
  - Current approach is only marginally better than plaintext
  - Even with file permissions, the JSON file is accessible if system is compromised

**Unverified Screenshot Data URLs in History:**
- Risk: Screenshot data is stored as base64 data URLs in Core Data without validation
- Files: `Sources/AppState.swift` (lines 581-582), `Sources/SettingsView.swift` (lines 765-772)
- Current mitigation: Data is only stored locally
- Recommendations:
  - Validate base64 data before storing
  - Consider warning users that screenshots contain sensitive context (UI state, text visible on screen)
  - Document privacy implications clearly

**Groq API Key Exposure in Logs:**
- Risk: API key could be logged in error messages or passed in error alerts
- Files: Review `Sources/TranscriptionService.swift` and `Sources/AppContextService.swift` for error message construction
- Current mitigation: Keys are in Authorization headers (not typically logged by URLSession)
- Recommendations:
  - Ensure error messages never include API key material
  - Test error paths to confirm keys aren't leaked

**Third-Party API Dependency Without Rate Limiting:**
- Risk: Groq API calls (transcription, context inference) have no local rate limiting
- Files: `Sources/TranscriptionService.swift`, `Sources/AppContextService.swift`
- Current mitigation: Groq has server-side rate limits
- Recommendations:
  - Implement client-side rate limiting to gracefully handle quota exhaustion
  - Show user feedback when hitting rate limits instead of generic errors

## Performance Bottlenecks

**Large UI View Complexity in SettingsView and SetupView:**
- Problem: SettingsView and SetupView are 1,095 and 1,128 lines respectively with complex nested SwiftUI hierarchy
- Files: `Sources/SettingsView.swift`, `Sources/SetupView.swift`
- Cause: All views, components, and helpers defined in single file with deep view hierarchies
- Improvement path:
  - Split into separate view files for each section (GeneralSettingsView, RunLogView, APIKeySection, etc.)
  - Extract helper components (SettingsCard, PipelineStepView, etc.) to separate files
  - This will improve compile time and reduce memory during UI rendering

**AppState as God Object:**
- Problem: AppState manages 30+ @Published properties and handles recording, transcription, audio device management, permissions, history, context capture, and debug overlay all in one class (892 lines)
- Files: `Sources/AppState.swift` (entire file)
- Cause: Central repository approach means every state change triggers potentially expensive @Published notifications across the entire app
- Improvement path:
  - Extract RecordingManager for recording/transcription/audio logic
  - Extract PermissionManager for accessibility/microphone/screenshot permission state
  - Extract PipelineManager for history management
  - Keep AppState as a lightweight coordinator

**Screenshot Capture & Compression During Recording:**
- Problem: Screenshot capture with LLM inference happens on background thread during active recording
- Files: `Sources/AppContextService.swift` (screenshot capture), `Sources/AppState.swift` (startContextCapture, line 710)
- Cause: Context capture is async but not throttled or prioritized lower than audio capture
- Improvement path:
  - Defer full screenshot processing until after recording stops if it's taking >500ms
  - Implement timeout on context capture task (currently no timeout, can block indefinitely)
  - Consider running inference on a lower QoS queue

**AllCases Iteration in Audio Device Enumeration:**
- Problem: `AudioDevice.deviceID(forUID:)` calls `availableInputDevices()` which re-enumerates all audio devices via CoreAudio
- Files: `Sources/AudioRecorder.swift` (lines 87-90)
- Cause: Full enumeration just to find one device ID
- Improvement path:
  - Cache audio device list with invalidation on device changes
  - Use direct CoreAudio lookup if UID is available

## Fragile Areas

**Audio Engine Reuse Logic:**
- Files: `Sources/AudioRecorder.swift` (lines 140-149)
- Why fragile: Engine reuse checks `currentDeviceUID == deviceUID` but if device is unplugged and replugged, same UID could point to different hardware. Switching devices mid-setup can create inconsistent state.
- Safe modification: Always restart engine when deviceUID changes. Add logging to track device changes.
- Test coverage: No tests for device hot-swap scenarios

**Accessibility Element Extraction with Force Casting:**
- Files: `Sources/AppState.swift` (lines 760-776)
- Why fragile: Uses `AXUIElementCreateApplication` without null checks and `unsafeBitCast` without validation
- Safe modification: Wrap all AX calls in try-catch, validate UIElement types before casting
- Test coverage: No tests for apps that don't expose standard accessibility attributes

**Pipeline History Store Core Data Migration:**
- Files: `Sources/PipelineHistoryStore.swift` (entire file)
- Why fragile: Core Data store is created on first access with no schema versioning. If data model changes, schema compatibility breaks silently.
- Safe modification: Implement Core Data versioning or use simpler JSON storage with explicit migrations
- Test coverage: No tests for history persistence across version upgrades

**Screenshot Data URL Generation Without Validation:**
- Files: `Sources/AppContextService.swift` (lines 540-600 screenshot capture)
- Why fragile: Base64 data URL construction assumes image encoding will succeed without validation
- Safe modification: Validate data URL length against `maxScreenshotDataURILength` (500KB) and fail gracefully with error message instead of silently truncating
- Test coverage: No tests for large screenshots or edge cases

## Scaling Limits

**Pipeline History Hard-Limited to 20 Entries:**
- Current capacity: Last 20 runs stored in Core Data
- Limit: SQLite/Core Data backend will degrade with thousands of entries; UI rendering slows with deeply nested history items
- Scaling path:
  - Implement pagination/lazy loading in RunLogView
  - Archive old runs to separate file storage
  - Consider database backend for larger deployments

**Audio File Storage Accumulation:**
- Current capacity: Audio files stored in `~/Library/Application Support/FreeFlow/audio/` indefinitely
- Limit: No automatic cleanup; disk space can be exhausted after weeks of frequent use
- Scaling path:
  - Implement automatic cleanup of audio files older than N days (default: 30)
  - Show storage usage in settings
  - Warn user when audio directory exceeds 1GB

**Screenshot Compression at 1024x1024 with 50% Quality:**
- Current capacity: Single screenshot captured per recording
- Limit: Compressed screenshot still 50-200KB; base64 data URL approaches 500KB limit
- Scaling path:
  - Implement adaptive compression based on content detection
  - Crop irrelevant UI chrome (menu bars, status bars)
  - Add quality knob for users with slow networks

## Dependencies at Risk

**CoreData Without Error Recovery:**
- Risk: Core Data operations are wrapped in `try?` throughout codebase; corruption goes undetected
- Files: `Sources/PipelineHistoryStore.swift` (multiple `try?` catches at lines 42, 57, 70, 90)
- Impact: History data can silently disappear; no user indication
- Migration plan:
  - Add Core Data stack validation on startup
  - Implement atomic transactions with rollback for history mutations
  - Add migration guide for users with corrupted stores

**AVAudioEngine State Management:**
- Risk: Audio engine lifecycle is tightly coupled to AppState; if engine enters error state, recovery is incomplete
- Files: `Sources/AudioRecorder.swift` (lines 126-273)
- Impact: Recording may fail silently if engine is in error state; requires app restart
- Migration plan:
  - Wrap AVAudioEngine in more robust state machine
  - Detect and recover from engine failures automatically
  - Add diagnostics logging for audio subsystem issues

## Missing Critical Features

**No Offline Transcription:**
- Problem: Entire transcription pipeline requires Groq API (internet connection required)
- Blocks: Users cannot use app on flights, in remote locations, or during network outages
- Workaround: None. Users must enable internet access.

**No Local Storage Encryption:**
- Problem: Audio files and history stored unencrypted on disk
- Blocks: HIPAA/PCI compliance use cases; sensitive business use cases
- Workaround: Rely on full-disk encryption (FileVault) for protection

**No Undo/Revision History for Typed Text:**
- Problem: Text is pasted immediately after transcription; no record of what was typed
- Blocks: Users cannot undo if transcription result was wrong
- Workaround: Manually undo in target application

**No Multi-User or Sync:**
- Problem: Settings, history, and API keys are per-machine only
- Blocks: Teams cannot share configurations; users with multiple Macs must reconfigure each machine
- Workaround: Manual configuration on each machine

## Test Coverage Gaps

**No Unit Tests:**
- What's not tested: Service layer (TranscriptionService, AppContextService, PostProcessingService) has no unit tests
- Files: `Sources/TranscriptionService.swift`, `Sources/AppContextService.swift`, `Sources/PostProcessingService.swift`
- Risk: API changes, error handling bugs, model selection logic failures go undetected
- Priority: High — these are critical business logic

**No Integration Tests:**
- What's not tested: End-to-end recording → transcription → post-processing → paste flow
- Files: Entire pipeline from `Sources/AppState.swift` (startRecording → stopAndTranscribe)
- Risk: Regressions in recording flow only caught through manual QA
- Priority: Medium — affects entire user workflow

**No Audio Device Tests:**
- What's not tested: Device enumeration, device switching, missing device handling, hot-swap scenarios
- Files: `Sources/AudioRecorder.swift` (AudioDevice enumeration), device selection logic in AppState
- Risk: Audio input fails silently when using non-default devices or when devices are unplugged
- Priority: High — common failure mode

**No Permission State Tests:**
- What's not tested: Permission change detection, recovery after permission denial, prompt behavior
- Files: `Sources/AppState.swift` (permission polling, recovery logic)
- Risk: App state becomes inconsistent when permissions are changed in system settings mid-use
- Priority: Medium — affects user experience if permissions revoked

**No Accessibility API Tests:**
- What's not tested: Window title extraction, selected text extraction, focus detection for various apps
- Files: `Sources/AppContextService.swift` (accessibility element extraction), `Sources/AppState.swift` (window title fetching)
- Risk: Context capture fails or returns empty for unsupported apps; UI shows "No context captured"
- Priority: Medium — impacts context-aware post-processing effectiveness

---

*Concerns audit: 2026-02-18*
