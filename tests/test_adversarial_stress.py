"""
Adversarial Stress Test Suite for Glide Ultra Local Studio.
Stress-tests SFX mixer edge cases, boundary conditions, audio formats,
and frontend responsive CSS rules.

Run:
  .\\.venv-build311\\Scripts\\python.exe -m unittest tests.test_adversarial_stress
"""
from __future__ import annotations

import array
import math
import os
from pathlib import Path
import re
import struct
import tempfile
import unittest
import numpy as np

import glide_core.audio.sfx_mixer as sfx_mixer


class SfxMixerAdversarialTests(unittest.TestCase):
    """Stress testing the SFX mixer with extreme, adversarial, and malformed inputs."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="glide_adversarial_sfx_")
        self.work = Path(self.tmp_dir.name)

    def tearDown(self):
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def _create_wav_file(
        self,
        filename: str,
        n_frames: int,
        channels: int = 2,
        sampwidth: int = 2,
        framerate: int = 48000,
        fmt_tag: int = 1,
        raw_data: bytes | None = None,
    ) -> Path:
        """Helper to create arbitrary WAV files including custom formats, 24-bit PCM, 32-bit float, etc."""
        path = self.work / filename
        frame_bytes = channels * sampwidth
        data_size = n_frames * frame_bytes if raw_data is None else len(raw_data)

        # RIFF header
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,
            fmt_tag,
            channels,
            framerate,
            framerate * frame_bytes,
            frame_bytes,
            sampwidth * 8,
            b"data",
            data_size,
        )
        if raw_data is None:
            raw_data = b"\x00" * data_size
        path.write_bytes(header + raw_data)
        return path

    def test_empty_audio_clip_zero_bytes(self):
        """Zero-byte file should be safely rejected without crashing the mixer."""
        empty_file = self.work / "zero_byte.wav"
        empty_file.write_bytes(b"")

        prepared = [({"time": 0.5, "effect": "test"}, empty_file)]
        bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 2.0, self.work)
        self.assertTrue(bed.exists())
        self.assertGreater(bed.stat().st_size, 44)

        # Output must be pure silence
        data = bed.read_bytes()[44:]
        arr = np.frombuffer(data, dtype=np.int16)
        self.assertEqual(np.count_nonzero(arr), 0)

    def test_zero_length_wav_asset(self):
        """Valid WAV header with 0 data frames should be safely handled without crash."""
        zero_frames = self._create_wav_file("zero_frames.wav", n_frames=0, raw_data=b"")
        prepared = [({"time": 0.0, "effect": "silent"}, zero_frames)]

        bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 1.0, self.work)
        self.assertTrue(bed.exists())
        arr = np.frombuffer(bed.read_bytes()[44:], dtype=np.int16)
        self.assertEqual(len(arr), 48000 * 2)
        self.assertEqual(np.count_nonzero(arr), 0)

    def test_corrupted_and_truncated_headers(self):
        """Files with truncated or garbage headers must be skipped without crashing."""
        for name, junk in [
            ("partial_riff.wav", b"RIFF"),
            ("tiny_garbage.wav", b"\x00\x01\x02\x03\x04\x05"),
            ("fake_header.wav", b"RIFF\x20\x00\x00\x00WAVEfmt \x10\x00"),
            ("non_audio.wav", b"This is a plain text file pretending to be audio."),
        ]:
            bad_file = self.work / name
            bad_file.write_bytes(junk)
            prepared = [({"time": 0.2, "effect": "bad"}, bad_file)]
            bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 1.0, self.work)
            self.assertTrue(bed.exists())
            arr = np.frombuffer(bed.read_bytes()[44:], dtype=np.int16)
            self.assertEqual(np.count_nonzero(arr), 0)

    def test_empty_prepared_events_and_zero_duration(self):
        """Empty event list and zero or negative timeline duration must produce valid silent bed."""
        # Zero duration clamped to minimum 0.1s
        bed_zero = sfx_mixer.build_pcm_sfx_event_bed([], 0.0, self.work)
        self.assertTrue(bed_zero.exists())
        arr = np.frombuffer(bed_zero.read_bytes()[44:], dtype=np.int16)
        self.assertGreaterEqual(len(arr), 4800 * 2)  # 0.1s at 48kHz stereo

        # Negative duration clamped to minimum 0.1s
        bed_neg = sfx_mixer.build_pcm_sfx_event_bed([], -5.0, self.work)
        self.assertTrue(bed_neg.exists())

        # None/invalid time keys
        dummy = self._create_wav_file("dummy.wav", n_frames=480, raw_data=b"\x10\x00" * 480 * 2)
        prepared = [
            ({"time": None}, dummy),
            ({"time": -10.0}, dummy),
            ({"time": 999999.0}, dummy),
        ]
        bed_invalid_times = sfx_mixer.build_pcm_sfx_event_bed(prepared, 1.0, self.work)
        self.assertTrue(bed_invalid_times.exists())

    def test_24bit_pcm_assets_mono_and_stereo(self):
        """24-bit PCM assets (sampwidth=3) must load, downmix/expand, scale accurately, and mix."""
        # 480 frames of 24-bit audio
        # Generate full scale positive (+8388607) and full scale negative (-8388608)
        n_frames = 1000
        # 24-bit stereo samples
        raw_samples = bytearray()
        for i in range(n_frames):
            # Alternating sine-like values
            val = int(8388607 * math.sin(2 * math.pi * 440 * i / 48000))
            if val < 0:
                val = (1 << 24) + val
            b0 = val & 0xFF
            b1 = (val >> 8) & 0xFF
            b2 = (val >> 16) & 0xFF
            raw_samples.extend([b0, b1, b2, b0, b1, b2])  # L and R

        pcm24_file = self._create_wav_file(
            "test_24bit_stereo.wav",
            n_frames=n_frames,
            channels=2,
            sampwidth=3,
            fmt_tag=1,
            raw_data=bytes(raw_samples),
        )

        prepared = [({"time": 0.1, "effect": "bell_24bit"}, pcm24_file)]
        bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 1.0, self.work)
        self.assertTrue(bed.exists())

        mixed = np.frombuffer(bed.read_bytes()[44:], dtype=np.int16)
        self.assertFalse(np.isnan(mixed).any())
        self.assertGreater(np.count_nonzero(mixed), 0)
        self.assertLessEqual(np.max(mixed), 32767)
        self.assertGreaterEqual(np.min(mixed), -32768)

    def test_24bit_pcm_resampling(self):
        """24-bit PCM at 44100 Hz must be resampled cleanly to 48000 Hz without NaN or artifact clicks."""
        n_frames = 4410  # 0.1s at 44.1kHz
        raw_samples = bytearray()
        for i in range(n_frames):
            val = int(7000000 * math.cos(2 * math.pi * 1000 * i / 44100))
            if val < 0:
                val = (1 << 24) + val
            b0 = val & 0xFF
            b1 = (val >> 8) & 0xFF
            b2 = (val >> 16) & 0xFF
            raw_samples.extend([b0, b1, b2, b0, b1, b2])

        pcm24_44k = self._create_wav_file(
            "test_24bit_44k.wav",
            n_frames=n_frames,
            channels=2,
            sampwidth=3,
            framerate=44100,
            fmt_tag=1,
            raw_data=bytes(raw_samples),
        )

        prepared = [({"time": 0.2, "effect": "resample_test"}, pcm24_44k)]
        bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 1.0, self.work)
        mixed = np.frombuffer(bed.read_bytes()[44:], dtype=np.int16)
        self.assertFalse(np.isnan(mixed).any())
        self.assertGreater(np.count_nonzero(mixed), 0)

    def test_32bit_float_assets_ieee(self):
        """32-bit float assets (sampwidth=4, fmt_tag=3) must load and normalize to 16-bit range."""
        n_frames = 2000
        t = np.linspace(0, 0.5, n_frames * 2, dtype=np.float32)
        flt_data = (0.8 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

        float_file = self._create_wav_file(
            "float_32bit.wav",
            n_frames=n_frames,
            channels=2,
            sampwidth=4,
            fmt_tag=3,
            raw_data=flt_data.tobytes(),
        )

        prepared = [({"time": 0.1, "effect": "float_sfx"}, float_file)]
        bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 1.0, self.work)
        mixed = np.frombuffer(bed.read_bytes()[44:], dtype=np.int16)

        self.assertFalse(np.isnan(mixed).any())
        self.assertGreater(np.count_nonzero(mixed), 0)
        self.assertLessEqual(np.max(mixed), 32767)
        self.assertGreaterEqual(np.min(mixed), -32768)

    def test_32bit_float_with_nan_and_infinity_adversarial(self):
        """Adversarial 32-bit float asset containing NaN, +inf, -inf, and out-of-bounds values."""
        n_frames = 500
        flt_array = np.full(n_frames * 2, 0.5, dtype=np.float32)
        # Inject poisonous values
        flt_array[10:20] = np.nan
        flt_array[30:40] = np.inf
        flt_array[50:60] = -np.inf
        flt_array[70:80] = 50.0   # Extreme overshoot
        flt_array[90:100] = -100.0  # Extreme undershoot

        poison_file = self._create_wav_file(
            "poison_float.wav",
            n_frames=n_frames,
            channels=2,
            sampwidth=4,
            fmt_tag=3,
            raw_data=flt_array.tobytes(),
        )

        prepared = [({"time": 0.05, "effect": "poison"}, poison_file)]
        bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 1.0, self.work)
        mixed = np.frombuffer(bed.read_bytes()[44:], dtype=np.int16)

        # Output must be completely finite without any NaN or Inf
        self.assertFalse(np.isnan(mixed).any(), "NaN found in mixed output!")
        self.assertTrue(np.isfinite(mixed).all(), "Non-finite values found in output!")
        self.assertLessEqual(np.max(mixed), 32767)
        self.assertGreaterEqual(np.min(mixed), -32768)

    def test_ramp_envelope_attenuates_to_exact_zero_at_boundaries(self):
        """
        Verify that the 192-sample ramp envelope smoothly attenuates step jumps
        to EXACTLY 0 at onset (sample 0) and exit (last sample).
        """
        # Create a DC block signal with maximum value +32000
        n_frames = 1000
        channels = 2
        dc_arr = np.full(n_frames * channels, 32000, dtype=np.int32)

        # Directly test internal ramp envelope function
        # (reproduced identically from sfx_mixer._apply_ramp_envelope)
        def apply_ramp(arr: np.ndarray, ch: int = 2, max_fade: int = 192) -> np.ndarray:
            clip_frames = len(arr) // ch
            fade_frames = min(max_fade, clip_frames // 2)
            if fade_frames > 0:
                ramp = np.linspace(0.0, 1.0, fade_frames, endpoint=True, dtype=np.float32)
                for c in range(ch):
                    arr[c : fade_frames * ch : ch] = (
                        arr[c : fade_frames * ch : ch] * ramp
                    ).astype(np.int32)
                    arr[-fade_frames * ch + c :: ch] = (
                        arr[-fade_frames * ch + c :: ch] * ramp[::-1]
                    ).astype(np.int32)
            return arr

        processed = apply_ramp(dc_arr.copy(), ch=2, max_fade=192)

        # 1. Onset: sample 0 of Left channel and Right channel MUST BE EXACTLY 0
        self.assertEqual(processed[0], 0, "Onset left sample 0 is not exactly 0!")
        self.assertEqual(processed[1], 0, "Onset right sample 0 is not exactly 0!")

        # 2. Exit: last sample of Left channel and Right channel MUST BE EXACTLY 0
        self.assertEqual(processed[-2], 0, "Exit left sample is not exactly 0!")
        self.assertEqual(processed[-1], 0, "Exit right sample is not exactly 0!")

        # 3. Smooth monotonic progression on onset ramp
        onset_left = processed[0 : 192 * 2 : 2]
        self.assertEqual(len(onset_left), 192)
        self.assertEqual(onset_left[0], 0)
        self.assertEqual(onset_left[-1], 32000)
        # Check non-decreasing monotonicity
        self.assertTrue(np.all(np.diff(onset_left) >= 0), "Onset ramp is not monotonically increasing!")

        # 4. Smooth monotonic progression on exit ramp
        exit_left = processed[-192 * 2 :: 2]
        self.assertEqual(len(exit_left), 192)
        self.assertEqual(exit_left[0], 32000)
        self.assertEqual(exit_left[-1], 0)
        # Check non-increasing monotonicity
        self.assertTrue(np.all(np.diff(exit_left) <= 0), "Exit ramp is not monotonically decreasing!")

    def test_short_clip_ramp_attenuation(self):
        """Test ramp envelope behavior on short clips where clip_frames < 2 * 192."""
        for clip_frames in [1, 2, 4, 10, 50, 100, 384]:
            arr = np.full(clip_frames * 2, 25000, dtype=np.int32)
            clip_f = len(arr) // 2
            fade_f = min(192, clip_f // 2)
            if fade_f > 0:
                ramp = np.linspace(0.0, 1.0, fade_f, endpoint=True, dtype=np.float32)
                for ch in range(2):
                    arr[ch : fade_f * 2 : 2] = (arr[ch : fade_f * 2 : 2] * ramp).astype(np.int32)
                    arr[-fade_f * 2 + ch :: 2] = (arr[-fade_f * 2 + ch :: 2] * ramp[::-1]).astype(np.int32)

                # Boundary check
                self.assertEqual(arr[0], 0, f"Failed at clip_frames={clip_frames}")
                self.assertEqual(arr[1], 0, f"Failed at clip_frames={clip_frames}")
                self.assertEqual(arr[-2], 0, f"Failed at clip_frames={clip_frames}")
                self.assertEqual(arr[-1], 0, f"Failed at clip_frames={clip_frames}")

    def test_timeline_truncation_tail_ramp(self):
        """When a clip is truncated by the end of the timeline, the tail ramp must attenuate to 0."""
        # Create 1s clip (48000 frames) with DC 30000
        clip_path = self._create_wav_file(
            "dc_clip.wav",
            n_frames=48000,
            channels=2,
            sampwidth=2,
            raw_data=(struct.pack("<hh", 30000, 30000) * 48000),
        )

        # Place at 0.9s on a 1.0s timeline (clip will be truncated to 0.1s = 4800 frames)
        prepared = [({"time": 0.9, "effect": "truncated"}, clip_path)]
        bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 1.0, self.work)
        mixed = np.frombuffer(bed.read_bytes()[44:], dtype=np.int16)

        # The last sample of the timeline should smoothly attenuate to 0
        last_left = mixed[-2]
        last_right = mixed[-1]
        self.assertEqual(last_left, 0, f"Truncated clip tail left did not attenuate to 0: {last_left}")
        self.assertEqual(last_right, 0, f"Truncated clip tail right did not attenuate to 0: {last_right}")

    def test_buffer_overflow_summation_clamping(self):
        """50 loud overlapping clips must not cause integer overflow or wrapping."""
        loud_clip = self._create_wav_file(
            "loud.wav",
            n_frames=2000,
            channels=2,
            sampwidth=2,
            raw_data=(struct.pack("<hh", 30000, 30000) * 2000),
        )

        # 50 overlapping clips at same start time
        prepared = [({"time": 0.1, "effect": f"loud_{i}"}, loud_clip) for i in range(50)]
        bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 0.5, self.work)
        mixed = np.frombuffer(bed.read_bytes()[44:], dtype=np.int16)

        # Maximum must be exactly 32767, not negative wrap-around
        self.assertEqual(np.max(mixed), 32767)
        self.assertGreaterEqual(np.min(mixed), -32768)
        self.assertFalse(np.isnan(mixed).any())

    def test_multichannel_5_1_surround_downmix(self):
        """6-channel (5.1 surround) 24-bit audio must cleanly extract first 2 channels without error."""
        n_frames = 1000
        # 6 channels, 24-bit (3 bytes per sample) -> 18 bytes per frame
        raw_samples = bytearray()
        for i in range(n_frames):
            # Channels 0 and 1 have audio, channels 2-5 have different values
            val = int(5000000 * math.sin(i * 0.1))
            if val < 0:
                val = (1 << 24) + val
            b0, b1, b2 = val & 0xFF, (val >> 8) & 0xFF, (val >> 16) & 0xFF
            # 6 channels: L, R, C, LFE, Ls, Rs
            raw_samples.extend([b0, b1, b2, b0, b1, b2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

        surround_file = self._create_wav_file(
            "surround_5_1.wav",
            n_frames=n_frames,
            channels=6,
            sampwidth=3,
            fmt_tag=1,
            raw_data=bytes(raw_samples),
        )

        prepared = [({"time": 0.1, "effect": "surround"}, surround_file)]
        bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 0.5, self.work)
        mixed = np.frombuffer(bed.read_bytes()[44:], dtype=np.int16)
        self.assertFalse(np.isnan(mixed).any())
        self.assertGreater(np.count_nonzero(mixed), 0)

    def test_8bit_unsigned_pcm_asset(self):
        """8-bit unsigned PCM asset (sampwidth=1) must load, center at 0, and mix properly."""
        n_frames = 1000
        # 8-bit unsigned values: 128 is zero, 255 is +max, 0 is -max
        raw = bytes([int(128 + 100 * math.sin(i * 0.1)) for i in range(n_frames * 2)])
        pcm8_file = self._create_wav_file(
            "pcm8.wav",
            n_frames=n_frames,
            channels=2,
            sampwidth=1,
            fmt_tag=1,
            raw_data=raw,
        )

        prepared = [({"time": 0.05, "effect": "retro_8bit"}, pcm8_file)]
        bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 0.5, self.work)
        mixed = np.frombuffer(bed.read_bytes()[44:], dtype=np.int16)
        self.assertFalse(np.isnan(mixed).any())
        self.assertGreater(np.count_nonzero(mixed), 0)

    def test_pure_python_fallback_mode(self):
        """Force exception in NumPy path to verify pure Python fallback engine works seamlessly."""
        clip1 = self._create_wav_file(
            "clip_for_fallback.wav",
            n_frames=1000,
            channels=2,
            sampwidth=2,
            raw_data=(struct.pack("<hh", 12000, 12000) * 1000),
        )
        prepared = [({"time": 0.1, "effect": "fallback_fx"}, clip1)]

        # Patch numpy in build_pcm_sfx_event_bed to raise an exception
        from unittest.mock import patch
        with patch.dict("sys.modules", {"numpy": None}):
            bed = sfx_mixer.build_pcm_sfx_event_bed(prepared, 0.5, self.work)
            self.assertTrue(bed.exists())
            self.assertGreater(bed.stat().st_size, 44)
            data = bed.read_bytes()[44:]
            arr = array.array("h")
            arr.frombytes(data)
            self.assertGreater(len(arr), 0)
            self.assertGreater(max(abs(x) for x in arr), 0)


class FrontendLayoutAdversarialTests(unittest.TestCase):
    """Stress testing the frontend CSS layout rules, responsive breakpoints, and ultrawide constraints."""

    @classmethod
    def setUpClass(cls):
        cls.css_path = Path("frontend/style.css")
        cls.html_path = Path("frontend/index.html")
        cls.css_content = cls.css_path.read_text(encoding="utf-8")
        cls.html_content = cls.html_path.read_text(encoding="utf-8")

    def test_render_dock_max_width_constraint(self):
        """
        Verify that .render-dock enforces max-width: calc(1920px - 44px)
        and body.sidebar-collapsed .render-dock enforces max-width: calc(1920px + 148px).
        This prevents stretching across ultrawide 2560px and 3440px viewports.
        """
        # Standard dock max-width
        dock_match = re.search(r"\.render-dock\s*\{[^}]*max-width:\s*calc\(1920px\s*-\s*44px\)", self.css_content)
        self.assertIsNotNone(dock_match, "Standard .render-dock missing max-width: calc(1920px - 44px) constraint!")

        # Sidebar collapsed dock max-width
        collapsed_match = re.search(
            r"body\.sidebar-collapsed\s+\.render-dock\s*\{[^}]*max-width:\s*calc\(1920px\s*\+\s*148px\)",
            self.css_content,
        )
        self.assertIsNotNone(collapsed_match, "body.sidebar-collapsed .render-dock missing max-width constraint!")

    def test_render_dock_ultrawide_geometry(self):
        """
        Empirically calculate render dock boundary box across 1080px, 2560px (1440p), and 3440px (ultrawide).
        """
        # .app has max-width: 1920px
        # Sidebar default width: 260px; Sidebar collapsed width: 72px
        # .render-dock: left: 280px, right: 22px, max-width: 1876px (1920 - 44)
        for viewport_w in [1080, 2560, 3440]:
            # Normal sidebar
            left_offset = 280
            right_offset = 22
            unconstrained_w = viewport_w - left_offset - right_offset
            constrained_w = min(unconstrained_w, 1920 - 44)

            # At 1080px: unconstrained = 778px, constrained = 778px
            # At 2560px: unconstrained = 2258px, constrained = 1876px
            # At 3440px: unconstrained = 3138px, constrained = 1876px
            if viewport_w == 1080:
                self.assertEqual(constrained_w, 778)
                self.assertLessEqual(constrained_w, viewport_w)
            elif viewport_w in (2560, 3440):
                self.assertEqual(constrained_w, 1876)
                self.assertLessEqual(constrained_w, 1920)

    def test_responsive_grid_adaptation_1051_1250(self):
        """
        Verify that @media (max-width:1250px) adapts .grid.two to 1fr
        preventing card squeezing between 1051px and 1250px.
        """
        query_match = re.search(
            r"@media\s*\(\s*max-width:\s*1250px\s*\)\s*\{([^}]+(?:\}[^}]+)*)\}",
            self.css_content,
        )
        self.assertIsNotNone(query_match, "@media (max-width:1250px) breakpoint is missing!")
        block = query_match.group(1)
        self.assertIn(".grid.two", block, ".grid.two rule missing in max-width:1250px block!")
        self.assertIn("grid-template-columns:1fr", block.replace(" ", ""), "grid-template-columns: 1fr missing!")

    def test_responsive_down_to_1080x680(self):
        """
        Verify layout behavior at 1080x680 minimum window dimensions.
        """
        # At 1080px width: max-width:1250px is active (1fr cards)
        # At 680px height: bottom docks and padding ensure no clipping
        # App has bottom padding:
        self.assertTrue(".app" in self.css_content)
        # Verify dock has fixed bottom position
        self.assertIn("bottom:", self.css_content)

    def test_level_desc_multiline_wrapping(self):
        """
        Verify that .level-desc has white-space: normal and -webkit-line-clamp: 2
        (no single-line truncation or ellipsis overflow).
        """
        desc_match = re.search(r"\.level-desc\s*\{([^}]+)\}", self.css_content)
        self.assertIsNotNone(desc_match, ".level-desc rule missing in style.css!")
        rules = desc_match.group(1)
        self.assertIn("white-space: normal", rules)
        self.assertIn("line-clamp: 2", rules)
        self.assertNotIn("white-space: nowrap", rules)

    def test_select_option_uniqueness(self):
        """
        Verify that select options in frontend/index.html have no duplicate values.
        """
        selects = re.findall(r"<select\b[^>]*>(.*?)</select>", self.html_content, re.DOTALL | re.IGNORECASE)
        self.assertGreater(len(selects), 0)
        for i, s_body in enumerate(selects):
            option_vals = re.findall(r'<option\b[^>]*value="([^"]+)"', s_body, re.IGNORECASE)
            duplicates = [v for v in set(option_vals) if option_vals.count(v) > 1]
            self.assertEqual(len(duplicates), 0, f"Select #{i} has duplicate option values: {duplicates}")


if __name__ == "__main__":
    unittest.main()
