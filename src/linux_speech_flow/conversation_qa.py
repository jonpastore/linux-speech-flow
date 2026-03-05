import os
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from linux_speech_flow.config import load_config


class ConversationQAWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application,
        transcript: str,
        metadata: dict,
        pipeline,
        initial_result: dict,
        on_finalised=None,
        selected_models: list[str] | None = None,
        window_info: dict | None = None,
        save_analysis: bool = True,
        inject_to_window: bool = False,
    ):
        super().__init__(application=application, title="Conversation Q&A")
        self.set_default_size(640, 700)
        self.set_resizable(True)

        self._transcript = transcript
        self._metadata = metadata
        self._pipeline = pipeline
        self._current_result = dict(initial_result)
        self._on_finalised = on_finalised
        self._selected_models = selected_models or ["groq"]
        self._window_info = window_info or {}
        self._save_analysis = save_analysis
        self._inject_to_window = inject_to_window
        self._qa_rounds: list[dict] = []
        self._round_count = 0
        self._is_speaking = False
        self._audio_recorder = None

        config = load_config()
        self._max_qa_iterations = config.get("conv_max_qa_iterations", 3)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_vexpand(True)
        log_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer.append(log_scroll)

        self._log_view = Gtk.TextView()
        self._log_view.set_editable(False)
        self._log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._log_view.set_margin_start(12)
        self._log_view.set_margin_end(12)
        self._log_view.set_margin_top(12)
        self._log_view.set_margin_bottom(8)
        self._log_buf = self._log_view.get_buffer()
        log_scroll.set_child(self._log_view)

        sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        outer.append(sep1)

        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        bottom.set_margin_start(16)
        bottom.set_margin_end(16)
        bottom.set_margin_top(12)
        bottom.set_margin_bottom(12)
        outer.append(bottom)

        q_label = Gtk.Label(label="AI Question:")
        q_label.set_xalign(0)
        bottom.append(q_label)

        q_scroll = Gtk.ScrolledWindow()
        q_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        q_scroll.set_min_content_height(60)
        q_scroll.set_max_content_height(100)
        self._question_view = Gtk.TextView()
        self._question_view.set_editable(True)
        self._question_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._question_buf = self._question_view.get_buffer()
        q_scroll.set_child(self._question_view)
        bottom.append(q_scroll)

        a_label = Gtk.Label(label="Your Answer:")
        a_label.set_xalign(0)
        bottom.append(a_label)

        self._answer_entry = Gtk.Entry()
        self._answer_entry.set_placeholder_text("Type your answer here...")
        bottom.append(self._answer_entry)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.append(btn_row)

        self._speak_btn = Gtk.Button(label="Speak")
        self._speak_btn.connect("clicked", self._on_speak)
        btn_row.append(self._speak_btn)

        self._submit_btn = Gtk.Button(label="Submit Answer")
        self._submit_btn.add_css_class("suggested-action")
        self._submit_btn.connect("clicked", self._on_submit_answer)
        btn_row.append(self._submit_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_row.append(spacer)

        self._done_btn = Gtk.Button(label="Done, use current output")
        self._done_btn.connect("clicked", self._on_done)
        btn_row.append(self._done_btn)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_xalign(0)
        self._status_label.add_css_class("dim-label")
        bottom.append(self._status_label)

        GLib.idle_add(self._init_first_question)

    def _init_first_question(self):
        confidence = self._current_result.get("confidence", 0.0)
        questions = self._current_result.get("questions", [])
        summary = self._current_result.get("summary", "")
        if summary:
            self._append_log(f"Summary:\n{summary}\n")
        if confidence >= 0.95 or not questions:
            self._show_confidence_confirmation(confidence, is_init=True)
        else:
            self._set_question(questions[0])
            self._update_status()
        return False

    def _set_question(self, question: str):
        self._question_buf.set_text(question)

    def _append_log(self, text: str):
        end_iter = self._log_buf.get_end_iter()
        self._log_buf.insert(end_iter, text + "\n")
        end_mark = self._log_buf.get_insert()
        self._log_view.scroll_to_mark(end_mark, 0.0, True, 0.0, 1.0)

    def _update_status(self):
        confidence = self._current_result.get("confidence", 0.0)
        pct = int(confidence * 100)
        self._status_label.set_text(f"Round {self._round_count} | Confidence: {pct}%")

    def _set_buttons_sensitive(self, sensitive: bool):
        self._speak_btn.set_sensitive(sensitive)
        self._submit_btn.set_sensitive(sensitive)
        self._done_btn.set_sensitive(sensitive)

    def _on_submit_answer(self, _btn):
        question = self._question_buf.get_text(
            self._question_buf.get_start_iter(),
            self._question_buf.get_end_iter(),
            False,
        ).strip()
        answer = self._answer_entry.get_text().strip()
        if not answer:
            return

        self._append_log(f"AI: {question}")
        self._append_log(f"You: {answer}\n")

        self._qa_rounds.append({"question": question, "answer": answer})
        self._answer_entry.set_text("")
        self._set_buttons_sensitive(False)
        model_str = " + ".join(m.capitalize() for m in self._selected_models)
        self._status_label.set_text(f"Calling {model_str} AI...")

        t = threading.Thread(
            target=self._qa_thread,
            args=(question, answer),
            daemon=True,
        )
        t.start()

    def _qa_thread(self, question: str, answer: str):
        try:
            result = self._pipeline.continue_qa(
                self._current_result,
                question,
                answer,
                self._transcript,
                self._selected_models,
            )
        except Exception as exc:
            result = {
                "title": self._current_result.get("title", "untitled"),
                "summary": self._current_result.get("summary", ""),
                "confidence": self._current_result.get("confidence", 0.0),
                "questions": [],
                "action_items": [],
                "error": str(exc),
            }
        GLib.idle_add(self._on_qa_result, result)

    def _on_qa_result(self, result: dict):
        self._current_result = result
        self._round_count += 1
        self._set_buttons_sensitive(True)
        self._update_status()

        summary = result.get("summary", "")
        if summary:
            self._append_log(f"[Updated summary]\n{summary}\n")

        confidence = result.get("confidence", 0.0)
        questions = result.get("questions", [])

        if confidence >= 0.95:
            self._show_confidence_confirmation(confidence, is_init=False)
        elif self._round_count >= self._max_qa_iterations:
            self._show_continue_rounds_dialog()
        elif questions:
            self._set_question(questions[0])
        else:
            self._set_question("Do you have any additional context to share?")

        return False

    def _show_confidence_confirmation(self, confidence: float, is_init: bool):
        dialog = Gtk.Window(title="AI Analysis Complete")
        dialog.set_modal(True)
        dialog.set_transient_for(self)
        dialog.set_default_size(400, 160)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        dialog.set_child(box)

        pct = int(confidence * 100)
        msg = Gtk.Label(label=f"AI has reached {pct}% confidence. Finalise output?")
        msg.set_wrap(True)
        msg.set_xalign(0.0)
        box.append(msg)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        continue_btn = Gtk.Button(label="Continue Q&A")

        def _on_continue(_b):
            dialog.close()
            questions = self._current_result.get("questions", [])
            if questions:
                self._set_question(questions[0])
            else:
                self._set_question("Do you have any additional context to share?")

        continue_btn.connect("clicked", _on_continue)
        btn_row.append(continue_btn)

        finalise_btn = Gtk.Button(label="Finalise")
        finalise_btn.add_css_class("suggested-action")

        def _on_finalise(_b):
            dialog.close()
            self._finalise()

        finalise_btn.connect("clicked", _on_finalise)
        btn_row.append(finalise_btn)

        dialog.present()

    def _show_continue_rounds_dialog(self):
        dialog = Gtk.Window(title="Continue Q&A?")
        dialog.set_modal(True)
        dialog.set_transient_for(self)
        dialog.set_default_size(400, 160)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        dialog.set_child(box)

        msg = Gtk.Label(
            label=f"You've completed {self._max_qa_iterations} Q&A rounds. Continue with more rounds?"
        )
        msg.set_wrap(True)
        msg.set_xalign(0.0)
        box.append(msg)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        stop_btn = Gtk.Button(label="Finalise now")

        def _on_stop(_b):
            dialog.close()
            self._finalise()

        stop_btn.connect("clicked", _on_stop)
        btn_row.append(stop_btn)

        continue_btn = Gtk.Button(label="Continue Q&A")
        continue_btn.add_css_class("suggested-action")

        def _on_continue(_b):
            dialog.close()
            questions = self._current_result.get("questions", [])
            if questions:
                self._set_question(questions[0])
            else:
                self._set_question("Do you have any additional context to share?")

        continue_btn.connect("clicked", _on_continue)
        btn_row.append(continue_btn)

        dialog.present()

    def _on_done(self, _btn):
        confidence = self._current_result.get("confidence", 0.0)
        pct = int(confidence * 100)

        dialog = Gtk.Window(title="Finalise Output")
        dialog.set_modal(True)
        dialog.set_transient_for(self)
        dialog.set_default_size(400, 160)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        dialog.set_child(box)

        if confidence < 0.95:
            msg_text = (
                f"AI confidence at {pct}% — output may be incomplete. Finalise anyway?"
            )
        else:
            msg_text = f"AI has reached {pct}% confidence. Finalise output?"

        msg = Gtk.Label(label=msg_text)
        msg.set_wrap(True)
        msg.set_xalign(0.0)
        box.append(msg)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        box.append(btn_row)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _b: dialog.close())
        btn_row.append(cancel_btn)

        finalise_btn = Gtk.Button(label="Finalise")
        finalise_btn.add_css_class("suggested-action")

        def _on_finalise(_b):
            dialog.close()
            self._finalise()

        finalise_btn.connect("clicked", _on_finalise)
        btn_row.append(finalise_btn)

        dialog.present()

    def _finalise(self) -> None:
        from linux_speech_flow.conversation_pipeline import coalesce_file, conv_filename
        from linux_speech_flow.conversation_dialog import TranscriptOutputWindow

        self._metadata["models_used"] = ", ".join(
            m.capitalize() for m in self._selected_models
        )
        summary = self._current_result.get("summary", "")
        ai_title = self._current_result.get("title", "untitled")

        # Build combined output: transcript with analysis appended
        combined = self._transcript
        if summary:
            combined += "\n\n---\n\n## AI Analysis\n\n" + summary
        if self._qa_rounds:
            combined += "\n\n## Q&A\n"
            for r in self._qa_rounds:
                combined += f"\nAI: {r['question']}\nYou: {r['answer']}\n"

        save_path = None
        if self._save_analysis:
            config = load_config()
            save_dir = Path(
                config.get("conv_save_dir", "~/Documents/conversations")
            ).expanduser()
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = str(save_dir / conv_filename(ai_title))
            coalesce_file(save_path, self._metadata, summary, self._qa_rounds, self._transcript)

        if self._inject_to_window and self._window_info.get("window_id"):
            from linux_speech_flow.injector import paste_text
            paste_text(combined, self._window_info)

        if self._on_finalised:
            self._on_finalised(save_path)

        app = self.get_application()
        metadata = dict(self._metadata)
        window_info = self._window_info
        self.close()

        out_win = TranscriptOutputWindow(
            application=app,
            transcript=combined,
            metadata=metadata,
            window_info=window_info,
            heading="Analysis Output",
        )
        out_win.present()

    def _on_speak(self, _btn):
        if self._is_speaking:
            if self._audio_recorder:
                self._audio_recorder.stop(cancel=False)
        else:
            self._is_speaking = True
            self._speak_btn.set_label("Stop Speaking")
            self._set_buttons_sensitive(False)
            self._speak_btn.set_sensitive(True)
            self._status_label.set_text("Recording... (stops on silence)")

            from linux_speech_flow.recorder import AudioRecorder

            config = load_config()
            device = config.get("microphone") or None
            self._audio_recorder = AudioRecorder(
                device_name=device,
                max_duration=120,
                silence_duration=3,
            )
            self._audio_recorder.start(
                on_complete=self._on_speak_complete,
                on_error=self._on_speak_error,
            )

    def _on_speak_complete(self, wav_path: str):
        self._is_speaking = False
        self._audio_recorder = None
        self._speak_btn.set_label("Speak")
        self._speak_btn.set_sensitive(False)
        self._status_label.set_text("Transcribing...")

        def _transcribe_thread():
            try:
                text, confidence = self._pipeline.transcribe_chunk_verbose(wav_path)
            except Exception:
                text, confidence = "", 0.0
            finally:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass
            GLib.idle_add(self._on_speak_transcribed, text, confidence)

        threading.Thread(target=_transcribe_thread, daemon=True).start()

    def _on_speak_transcribed(self, text: str, confidence: float = 0.0):
        self._set_buttons_sensitive(True)
        if text:
            self._answer_entry.set_text(text)
            pct = int(confidence * 100)
            conf_str = f" ({pct}% confidence)" if pct > 0 else ""
            self._status_label.set_text(f"Transcribed{conf_str} — review and submit")
        else:
            self._status_label.set_text("No speech detected — try again")
        return False

    def _on_speak_error(self, message: str):
        self._is_speaking = False
        self._speak_btn.set_label("Speak")
        self._audio_recorder = None
        self._set_buttons_sensitive(True)
        self._status_label.set_text(f"Recording error: {message}")
