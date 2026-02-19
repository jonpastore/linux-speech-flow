# Testing Patterns

**Analysis Date:** 2026-02-18

## Test Framework

**Status:** No automated testing framework detected

**Build System:**
- Build: `make all` - compiles Swift code using `swiftc`
- No test runner configured (no XCTest, Swift Testing, or similar)
- Makefile targets: `all`, `clean`, `run`, `icon`, `dmg`, `codesign-dmg`, `notarize`
- No test target in Makefile

**Run Commands:**
```bash
make all              # Build the app
make run              # Build and run the app
make clean            # Remove build artifacts
```

## Manual Testing Approach

Since no automated testing framework is present, the codebase appears to rely on manual testing and runtime validation.

**Testing Strategy Observed:**
- Smoke testing: Build and launch the app (`make run`)
- Manual verification of core flows (recording, transcription, post-processing)
- Integration testing with real Groq API (live API calls during development)
- Manual permission testing (accessibility, microphone, screen recording)

## Error Handling as Testing

**Validation Functions:**
The codebase uses explicit validation methods that serve dual purposes (runtime validation + quasi-testing):

```swift
// TranscriptionService.swift
static func validateAPIKey(_ key: String) async -> Bool {
    let trimmed = key.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else { return false }

    var request = URLRequest(url: URL(string: "https://api.groq.com/openai/v1/models")!)
    request.setValue("Bearer \(trimmed)", forHTTPHeaderField: "Authorization")

    do {
        let (_, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        return status == 200
    } catch {
        return false
    }
}
```

This function validates API keys against the actual Groq API endpoint, serving as both user-facing validation and integration test.

## Testing Patterns in Code

**Permission Checking:**
- `AVCaptureDevice.authorizationStatus(for: .audio)` - Runtime permission check
- `AXIsProcessTrusted()` - Accessibility permission verification
- `CGPreflightScreenCaptureAccess()` - Screen recording permission check
- Used to gate operations and prevent errors at runtime

**Error Recovery Testing:**
- Explicit error cases in enums enable type-safe error handling
- Example from `AudioRecorder.swift`:
```swift
guard let inputFormat = inputNode.outputFormat(forBus: 0),
      inputFormat.sampleRate > 0 else {
    throw AudioRecorderError.invalidInputFormat("Invalid sample rate: \(inputFormat.sampleRate)")
}
```

**State Validation:**
- Published properties enable observation of state changes during execution
- Example: `@Published var isRecording = false` - can be observed to verify recording started
- Debug panel exposed in UI for runtime inspection: `isDebugOverlayActive`, `lastRawTranscript`, `lastPostProcessedTranscript`

## Debug Support

**Debug Panel:**
- Exposed via settings tab (SettingsTab.runLog and debug panel view)
- Shows real-time pipeline state:
  - `debugStatusMessage`: "Idle", "Preparing audio", "Transcribing audio", "Running post-processing", "Done"
  - `lastRawTranscript`: Raw output from Groq
  - `lastPostProcessedTranscript`: LLM-refined output
  - `lastContextSummary`: Application context captured
  - `lastContextScreenshotDataURL`: Screenshot thumbnail
  - `lastPostProcessingStatus`: Success/failure of LLM processing

**Debug Overlay:**
- `toggleDebugOverlay()` method simulates audio levels with timer
- Shows real-time waveform visualization during recording
- Used to test UI without real audio input

**Performance Metrics:**
- Timing measurements logged via os.log:
```swift
os_log(.info, log: recordingLog, "startRecording() complete: %.3fms total",
       (CFAbsoluteTimeGetCurrent() - t0) * 1000)
```
- Buffer count tracking: `bufferCount` incremented and logged
- Elapsed time calculations relative to recording start

## Timeout Testing

**Timeout Patterns:**
Services implement timeout racing to ensure operations don't hang:

```swift
// TranscriptionService.swift
return try await withThrowingTaskGroup(of: String.self) { group in
    group.addTask {
        return try await self.transcribeAudio(fileURL: fileURL)
    }

    group.addTask {
        try await Task.sleep(nanoseconds: UInt64(self.transcriptionTimeoutSeconds * 1_000_000_000))
        throw TranscriptionError.transcriptionTimedOut(self.transcriptionTimeoutSeconds)
    }

    guard let result = try await group.next() else { ... }
    group.cancelAll()
    return result
}
```

This timeout pattern applies to:
- `TranscriptionService`: 20-second timeout (transcriptionTimeoutSeconds)
- `PostProcessingService`: 20-second timeout (postProcessingTimeoutSeconds)

## Runtime State Inspection

**View State Testing:**
Pipeline history stored locally enables retrospective testing:
- `AppState.pipelineHistory`: Array of `PipelineHistoryItem` objects
- Each entry contains: raw transcript, post-processed transcript, prompts, context, status, audio file reference
- Accessible via Run Log UI for manual inspection
- `maxPipelineHistoryCount = 20`: Keeps last 20 runs for inspection

**Audio Validation:**
- RMS (root mean square) calculation on buffers detects if real audio is being captured:
```swift
var rms: Float = 0
let frames = Int(buffer.frameLength)
if frames > 0, let channelData = buffer.floatChannelData {
    let samples = channelData[0]
    var sum: Float = 0
    for i in 0..<frames { sum += samples[i] * samples[i] }
    rms = sqrtf(sum / Float(frames))
}

// Fire ready callback on first non-silent buffer
if !self.readyFired && rms > 0 {
    self.readyFired = true
    self.onRecordingReady?()
}
```

## API Validation

**Live Testing Against Groq:**
- API key validation hits actual Groq endpoint (`/models`)
- Transcription uses real Groq Whisper API
- Post-processing uses real Groq LLM (`llama-4-scout-17b`)
- No mocking layer; development/testing uses actual API endpoints

## Testing Gaps

**Areas Without Formal Tests:**
- SwiftUI view rendering (no XCTest/Preview testing framework detected)
- Audio file I/O operations (file writing/reading not validated)
- Permission request flows (manual testing only)
- Error dialog display (manual verification)
- Hotkey event handling (manual input testing)
- Storage persistence (manual app restart testing)
- PDF/image screenshot handling (manual verification)

## No Test Files

No `.test.swift`, `.spec.swift`, or similar test files found in the codebase. The project is entirely production code.

**Implication:** All quality assurance relies on:
1. Manual testing during development
2. Runtime error handling and validation
3. Live API integration (no test doubles)
4. User-reported issues (post-release)
5. Debug UI panels for rapid iteration

## Testing Recommendations (Future)

If automated tests were added, focus areas would be:
1. **API validation** - Test Groq API response parsing
2. **Error recovery** - Verify fallback paths when APIs fail
3. **Audio processing** - Unit tests for RMS calculation and audio level smoothing
4. **File I/O** - Verify audio file creation/cleanup
5. **State machines** - Test recording/transcription state transitions
6. **Permission flows** - Mock system permission checks
7. **UI state** - SwiftUI preview tests and integration tests for settings panels

