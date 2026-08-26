"""
FFmpeg Wrapper — Time Compression Engine, Phase 2.

All FFmpeg operations go through this module. It uses subprocess directly
rather than a third-party wrapper, keeping the dependency count low and
giving precise control over command construction and error parsing.

Design decisions:
- Every function raises FFmpegError with the full stderr on failure.
- All durations are returned in milliseconds (consistent with the DB schema).
- probe_video() is the single authoritative source of video metadata.
- extract_frames() is deterministic: same input + same config = same frames.
"""

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FFmpegNotFoundError(RuntimeError):
    """Raised when ffmpeg/ffprobe binaries are not found on PATH."""


class FFmpegError(RuntimeError):
    """Raised when an ffmpeg/ffprobe command exits with a non-zero code."""

    def __init__(self, message: str, returncode: int, stderr: str) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class VideoCorruptedError(ValueError):
    """Raised when a video file is unreadable or structurally corrupted."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VideoMetadata:
    """
    Complete metadata extracted from a video file via ffprobe.

    All timestamps and durations are in milliseconds to match the DB schema.
    """
    # Identity
    file_path: str
    filename: str
    file_size_bytes: int

    # Timing
    duration_ms: int
    duration_seconds: float

    # Video stream
    width: int
    height: int
    fps: float
    frame_count: int
    codec: str
    codec_long: str
    bit_rate_kbps: int

    # Audio stream
    has_audio: bool
    audio_codec: str | None = None

    # Format
    format_name: str = ""
    format_long_name: str = ""

    # Computed
    frame_skip_frames: int = 1          # populated by caller based on settings
    estimated_keyframes: int = 0         # populated by caller

    # Quality indicators (populated by frame analysis in Phase 3+)
    avg_brightness: float | None = None
    avg_motion_score: float | None = None

    # Classification (user-provided or inferred)
    camera_angle: str = "unknown"
    scene_type: str = "unknown"
    time_of_day: str = "unknown"
    source_domain: str = "cctv"

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def is_long_video(self) -> bool:
        """Videos 1 hour or longer are considered long and need chunked processing."""
        return self.duration_seconds >= 3600

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "filename": self.filename,
            "file_size_bytes": self.file_size_bytes,
            "duration_ms": self.duration_ms,
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "codec": self.codec,
            "bit_rate_kbps": self.bit_rate_kbps,
            "has_audio": self.has_audio,
            "format_name": self.format_name,
            "resolution": self.resolution,
            "is_long_video": self.is_long_video,
        }


# ── Processing profile auto-detection ────────────────────────────────────────

_PROFILES = [
    ("Quick Test",         0,     120,   8),
    ("Short Clip",         120,   600,   20),
    ("Standard",           600,   3600,  90),
    ("Long Recording",     3600,  21600, 600),
    ("Extended Recording", 21600, 86400, 3600),
    ("Custom",             86400, float("inf"), None),
]


def get_processing_profile(duration_seconds: float, fps: float = 25.0, frame_skip_rate: int = 5) -> dict:
    """
    Return the recommended processing profile for a video of the given duration.

    Returns a dict with: profile, estimated_frames, estimated_keyframes,
    estimated_processing_s, duration_hms.
    """
    total_frames = int(duration_seconds * fps)
    estimated_frames = max(1, total_frames // frame_skip_rate)

    profile_name = "Custom"
    est_processing_s: int | None = None
    for i, (name, lo, hi, est) in enumerate(_PROFILES):
        if lo <= duration_seconds < hi:
            profile_name = name
            if est is not None:
                next_est = _PROFILES[i + 1][3] if i + 1 < len(_PROFILES) else est * 2
                ratio = (duration_seconds - lo) / max(1, hi - lo)
                est_processing_s = int(est + ratio * ((next_est or est * 2) - est))
            break

    h = int(duration_seconds // 3600)
    m = int((duration_seconds % 3600) // 60)
    s = int(duration_seconds % 60)
    duration_hms = f"{h:02d}:{m:02d}:{s:02d}"

    return {
        "profile": profile_name,
        "estimated_frames": estimated_frames,
        "estimated_keyframes": max(1, estimated_frames // 5),
        "estimated_processing_s": est_processing_s,
        "duration_hms": duration_hms,
    }


@dataclass
class FrameExtractionConfig:
    """
    Configuration for frame extraction.

    frame_skip_rate: Extract every Nth frame. 1 = every frame, 5 = every 5th.
    output_format:   Image format for extracted frames.
    quality:         JPEG quality 1–31 (lower = better). Only for JPEG output.
    resize:          Optional (width, height) to resize frames. None = original size.
    start_ms:        Start extraction from this timestamp (milliseconds).
    end_ms:          Stop extraction at this timestamp. None = end of video.
    """
    frame_skip_rate: int = 5
    output_format: str = "jpg"
    quality: int = 2
    resize: tuple[int, int] | None = None
    start_ms: int = 0
    end_ms: int | None = None

    def __post_init__(self) -> None:
        if self.frame_skip_rate < 1:
            raise ValueError("frame_skip_rate must be >= 1")
        if self.quality < 1 or self.quality > 31:
            raise ValueError("quality must be between 1 and 31")


@dataclass
class FrameExtractionResult:
    """Result of a frame extraction operation."""
    output_dir: str
    total_frames_extracted: int
    frame_paths: list[str]
    extraction_time_ms: int
    config_used: FrameExtractionConfig
    errors: list[str] = field(default_factory=list)

    @property
    def fps_achieved(self) -> float:
        """Actual extraction throughput in frames per second."""
        if self.extraction_time_ms == 0:
            return 0.0
        return (self.total_frames_extracted / self.extraction_time_ms) * 1000


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

def check_ffmpeg_available() -> dict[str, str]:
    """
    Verify that both ffmpeg and ffprobe are available on PATH.

    Returns:
        {"ffmpeg": "/usr/bin/ffmpeg", "ffprobe": "/usr/bin/ffprobe"}

    Raises:
        FFmpegNotFoundError: If either binary is missing.
    """
    result = {}
    for binary in ("ffmpeg", "ffprobe"):
        path = shutil.which(binary)
        if path is None:
            raise FFmpegNotFoundError(
                f"'{binary}' not found on PATH. "
                f"Install FFmpeg from https://ffmpeg.org/download.html"
            )
        result[binary] = path
    return result


def get_ffmpeg_version() -> str:
    """Return the installed FFmpeg version string."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=10
        )
        first_line = proc.stdout.splitlines()[0] if proc.stdout else "unknown"
        return first_line
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Core: ffprobe
# ---------------------------------------------------------------------------

def probe_video(file_path: str | Path) -> VideoMetadata:
    """
    Extract complete video metadata using ffprobe.

    This is the authoritative metadata source. All downstream modules
    must use the VideoMetadata object rather than re-probing the file.

    Args:
        file_path: Path to the video file.

    Returns:
        VideoMetadata with all fields populated.

    Raises:
        FileNotFoundError: If the file does not exist.
        VideoCorruptedError: If the file cannot be read by ffprobe.
        FFmpegError: If ffprobe exits unexpectedly.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
    except subprocess.TimeoutExpired:
        raise FFmpegError("ffprobe timed out", -1, "")
    except FileNotFoundError:
        raise FFmpegNotFoundError("ffprobe not found on PATH")

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "Invalid data found" in stderr or "moov atom not found" in stderr:
            raise VideoCorruptedError(
                f"File appears to be corrupted: {path.name}\n{stderr}"
            )
        raise FFmpegError(
            f"ffprobe failed for {path.name}",
            returncode=proc.returncode,
            stderr=stderr,
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise VideoCorruptedError(
            f"ffprobe returned non-JSON output for {path.name}"
        ) from exc

    if not data.get("streams"):
        raise VideoCorruptedError(
            f"No streams found in {path.name} — file may be empty or corrupted"
        )

    return _parse_probe_data(path, data)


def _parse_probe_data(path: Path, data: dict) -> VideoMetadata:
    """Parse ffprobe JSON output into a VideoMetadata object."""
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    # Find video and audio streams
    video_stream = next(
        (s for s in streams if s.get("codec_type") == "video"), None
    )
    audio_stream = next(
        (s for s in streams if s.get("codec_type") == "audio"), None
    )

    if video_stream is None:
        raise VideoCorruptedError(
            f"No video stream found in {path.name}"
        )

    # Duration — prefer format-level, fall back to stream-level
    duration_s = float(
        fmt.get("duration")
        or video_stream.get("duration")
        or 0
    )
    duration_ms = int(duration_s * 1000)

    # FPS — avg_frame_rate is the most reliable field
    fps = _parse_fraction(video_stream.get("avg_frame_rate", "25/1"))

    # Frame count — use nb_frames if available, otherwise estimate
    nb_frames = video_stream.get("nb_frames")
    if nb_frames and nb_frames != "N/A":
        frame_count = int(nb_frames)
    else:
        frame_count = int(duration_s * fps) if fps > 0 else 0

    # Bitrate
    bit_rate = int(fmt.get("bit_rate", 0))
    bit_rate_kbps = bit_rate // 1000

    return VideoMetadata(
        file_path=str(path.resolve()),
        filename=path.name,
        file_size_bytes=path.stat().st_size,
        duration_ms=duration_ms,
        duration_seconds=duration_s,
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        fps=fps,
        frame_count=frame_count,
        codec=video_stream.get("codec_name", "unknown"),
        codec_long=video_stream.get("codec_long_name", "unknown"),
        bit_rate_kbps=bit_rate_kbps,
        has_audio=audio_stream is not None,
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
        format_name=fmt.get("format_name", ""),
        format_long_name=fmt.get("format_long_name", ""),
    )


def _parse_fraction(fraction_str: str) -> float:
    """Parse a fraction string like '30000/1001' into a float."""
    try:
        if "/" in fraction_str:
            num, den = fraction_str.split("/")
            den = float(den)
            return float(num) / den if den != 0 else 0.0
        return float(fraction_str)
    except (ValueError, ZeroDivisionError):
        return 0.0


# ---------------------------------------------------------------------------
# Core: validation
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
SUPPORTED_CODECS = {
    "h264", "h265", "hevc", "vp8", "vp9", "av1",
    "mpeg4", "mpeg2video", "mjpeg", "wmv3", "wmv2",
}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 * 1024  # 50 GB


@dataclass
class ValidationResult:
    """Result of video file validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: VideoMetadata | None = None

    @property
    def rejected(self) -> bool:
        return not self.valid


def validate_video_file(file_path: str | Path) -> ValidationResult:
    """
    Validate a video file for ingestion.

    Checks performed (in order):
    1. File exists
    2. File extension is supported
    3. File is not empty
    4. File size is within limit
    5. ffprobe can read the file (corruption check)
    6. File has a valid video stream
    7. Codec is supported
    8. Duration is non-zero

    Returns:
        ValidationResult — always returns (never raises), errors in .errors list.
    """
    path = Path(file_path)
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Existence
    if not path.exists():
        return ValidationResult(valid=False, errors=[f"File not found: {path}"])

    # 2. Extension
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        errors.append(
            f"Unsupported file extension '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # 3. Empty file
    size = path.stat().st_size
    if size == 0:
        return ValidationResult(valid=False, errors=["File is empty (0 bytes)"])

    # 4. Size limit
    if size > MAX_FILE_SIZE_BYTES:
        errors.append(
            f"File size {size / (1024**3):.1f} GB exceeds limit of "
            f"{MAX_FILE_SIZE_BYTES / (1024**3):.0f} GB"
        )

    # Early exit if extension already failed
    if errors:
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    # 5–8. ffprobe validation
    try:
        metadata = probe_video(path)
    except VideoCorruptedError as exc:
        return ValidationResult(
            valid=False,
            errors=[f"File is corrupted or unreadable: {exc}"],
        )
    except FFmpegError as exc:
        return ValidationResult(
            valid=False,
            errors=[f"FFmpeg error during validation: {exc}"],
        )
    except FFmpegNotFoundError as exc:
        return ValidationResult(
            valid=False,
            errors=[f"FFmpeg not available: {exc}"],
        )

    # 6. Codec check
    if metadata.codec.lower() not in SUPPORTED_CODECS:
        warnings.append(
            f"Codec '{metadata.codec}' is not in the known-good list. "
            f"Processing may fail. Supported: {', '.join(sorted(SUPPORTED_CODECS))}"
        )

    # 7. Duration check
    if metadata.duration_seconds <= 0:
        errors.append("Video has zero or unknown duration")

    # 8. Minimum resolution
    if metadata.width < 64 or metadata.height < 64:
        errors.append(
            f"Resolution {metadata.resolution} is below minimum 64x64"
        )

    # FPS sanity check
    if metadata.fps <= 0:
        errors.append(f"Invalid FPS: {metadata.fps}")
    elif metadata.fps > 240:
        warnings.append(f"Very high FPS ({metadata.fps:.1f}). Frame extraction will be slow.")

    valid = len(errors) == 0
    return ValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
        metadata=metadata if valid else None,
    )


# ---------------------------------------------------------------------------
# Core: frame extraction
# ---------------------------------------------------------------------------

def extract_frames(
    video_path: str | Path,
    output_dir: str | Path,
    config: FrameExtractionConfig,
    metadata: VideoMetadata | None = None,
) -> FrameExtractionResult:
    """
    Extract frames from a video file using FFmpeg.

    Determinism guarantee: given the same video file and FrameExtractionConfig,
    this function always produces the same set of frames. This is critical for
    benchmark reproducibility.

    Frames are named: frame_{frame_number:08d}.{ext}
    Example: frame_00000001.jpg, frame_00000006.jpg (skip_rate=5)

    Args:
        video_path:  Path to the source video.
        output_dir:  Directory to write extracted frames.
        config:      Extraction configuration (skip rate, format, quality).
        metadata:    Pre-computed metadata (avoids re-probing if available).

    Returns:
        FrameExtractionResult with paths to all extracted frames.

    Raises:
        FFmpegError: If extraction fails.
        VideoCorruptedError: If the video cannot be read.
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use provided metadata or probe now
    if metadata is None:
        metadata = probe_video(video_path)

    start_time = time.perf_counter()

    # Build the video filter chain
    # select='not(mod(n,SKIP))' selects every Nth frame (0-indexed)
    # setpts resets timestamps for the selected frames
    vf_parts = [f"select='not(mod(n\\,{config.frame_skip_rate}))'", "setpts=N/FRAME_RATE/TB"]

    if config.resize:
        w, h = config.resize
        vf_parts.append(f"scale={w}:{h}")

    vf = ",".join(vf_parts)

    # Output pattern
    output_pattern = str(output_dir / f"frame_%08d.{config.output_format}")

    # Build time range args
    time_args: list[str] = []
    if config.start_ms > 0:
        time_args += ["-ss", str(config.start_ms / 1000)]
    if config.end_ms is not None:
        duration_s = (config.end_ms - config.start_ms) / 1000
        time_args += ["-t", str(duration_s)]

    cmd = [
        "ffmpeg",
        "-y",                          # overwrite output
        *time_args,
        "-i", str(video_path),
        "-vf", vf,
        "-vsync", "vfr",               # variable frame rate output (required with select filter)
        "-frame_pts", "1",             # embed PTS in frame (for timestamp recovery)
        "-q:v", str(config.quality),   # JPEG quality
        output_pattern,
    ]

    logger.debug("Frame extraction command: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,              # 1 hour max for very long videos
        )
    except subprocess.TimeoutExpired:
        raise FFmpegError("Frame extraction timed out after 1 hour", -1, "")
    except FileNotFoundError:
        raise FFmpegNotFoundError("ffmpeg not found on PATH")

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "Invalid data" in stderr or "moov atom not found" in stderr:
            raise VideoCorruptedError(f"Cannot extract frames: {stderr}")
        raise FFmpegError(
            f"Frame extraction failed for {video_path.name}",
            returncode=proc.returncode,
            stderr=stderr,
        )

    # Collect output frames
    frame_paths = sorted(
        str(p) for p in output_dir.glob(f"frame_*.{config.output_format}")
    )
    extraction_time_ms = int((time.perf_counter() - start_time) * 1000)

    logger.info(
        "Extracted %d frames from %s in %dms (skip_rate=%d)",
        len(frame_paths),
        video_path.name,
        extraction_time_ms,
        config.frame_skip_rate,
    )

    return FrameExtractionResult(
        output_dir=str(output_dir),
        total_frames_extracted=len(frame_paths),
        frame_paths=frame_paths,
        extraction_time_ms=extraction_time_ms,
        config_used=config,
    )


def extract_frames_chunked(
    video_path: str | Path,
    output_dir: str | Path,
    config: FrameExtractionConfig,
    metadata: VideoMetadata,
    chunk_duration_s: int = 1800,
) -> Iterator[FrameExtractionResult]:
    """
    Extract frames in time-based chunks for memory-efficient long-video processing.

    Yields a FrameExtractionResult for each chunk. The caller can process and
    discard each chunk's frames before the next chunk is extracted, keeping
    memory usage bounded regardless of video length.

    Args:
        video_path:       Path to the source video.
        output_dir:       Base output directory. Each chunk writes to a subdirectory.
        config:           Extraction configuration.
        metadata:         Pre-computed video metadata (required).
        chunk_duration_s: Seconds per chunk. Default: 1800 (30 minutes).

    Yields:
        FrameExtractionResult per chunk.
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    total_duration_s = metadata.duration_seconds
    chunk_start = 0.0
    chunk_index = 0

    while chunk_start < total_duration_s:
        chunk_end = min(chunk_start + chunk_duration_s, total_duration_s)

        chunk_config = FrameExtractionConfig(
            frame_skip_rate=config.frame_skip_rate,
            output_format=config.output_format,
            quality=config.quality,
            resize=config.resize,
            start_ms=int(chunk_start * 1000),
            end_ms=int(chunk_end * 1000),
        )

        chunk_output = output_dir / f"chunk_{chunk_index:04d}"
        chunk_output.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Extracting chunk %d: %.0f–%.0f seconds",
            chunk_index, chunk_start, chunk_end
        )

        result = extract_frames(video_path, chunk_output, chunk_config, metadata)
        yield result

        chunk_start = chunk_end
        chunk_index += 1


def extract_thumbnail(
    video_path: str | Path,
    output_path: str | Path,
    timestamp_s: float = 5.0,
    width: int = 320,
) -> str:
    """
    Extract a single thumbnail frame at a specific timestamp.

    Args:
        video_path:   Source video.
        output_path:  Output image path (must end in .jpg or .png).
        timestamp_s:  Seek position in seconds.
        width:        Output thumbnail width (height auto-calculated).

    Returns:
        Path to the extracted thumbnail.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp_s),
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", f"scale={width}:-1",
        str(output_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise FFmpegError(
            f"Thumbnail extraction failed",
            returncode=proc.returncode,
            stderr=proc.stderr,
        )

    return str(output_path)


def extract_frames_by_indices(
    video_path: str | Path,
    output_dir: str | Path,
    frame_indices: list[int],
    output_format: str = "jpg",
    quality: int = 2,
    batch_size: int = 200,
) -> "FrameExtractionResult":
    """
    Extract specific frame indices from a video using FFmpeg's select filter.

    This is the adaptive-skip extraction path. Rather than extracting every Nth
    frame (fixed skip rate), this function extracts ONLY the frames selected by
    AdaptiveSkipAnalyzer.select_frames().

    Algorithm:
      - For batches of ≤ batch_size indices: builds
        select='eq(n\\,10)+eq(n\\,25)+...' filter string
      - For large frame sets (> batch_size), splits into multiple FFmpeg calls
        to avoid shell command-line length limits
      - Frames are named frame_{frame_number:08d}.jpg matching the original
        frame number in the video (not the extraction sequence number)

    Args:
        video_path:    Path to the source video.
        output_dir:    Directory to write extracted frames.
        frame_indices: Sorted list of 0-based frame indices to extract.
        output_format: Image format (default: jpg).
        quality:       JPEG quality 1-31 (lower = better).
        batch_size:    Max indices per FFmpeg call (avoids arg length limits).

    Returns:
        FrameExtractionResult with paths to all extracted frames.

    Status: IMPLEMENTED. Not yet validated on videos with >10,000 frames.
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not frame_indices:
        return FrameExtractionResult(
            output_dir=str(output_dir),
            total_frames_extracted=0,
            frame_paths=[],
            extraction_time_ms=0,
            config_used=FrameExtractionConfig(frame_skip_rate=1),
        )

    start_time = time.perf_counter()
    frame_indices = sorted(set(frame_indices))
    all_frame_paths: list[str] = []

    # Process in batches to keep select= filter string manageable
    for batch_start in range(0, len(frame_indices), batch_size):
        batch = frame_indices[batch_start: batch_start + batch_size]

        # Build select filter: eq(n,10)+eq(n,25)+...
        # Each term selects one specific frame by its 0-based index
        select_expr = "+".join(f"eq(n\\,{idx})" for idx in batch)
        vf = f"select='{select_expr}',setpts=N/FRAME_RATE/TB"

        # Use a temporary subdirectory per batch to avoid filename collisions
        batch_dir = output_dir / f"_batch_{batch_start:06d}"
        batch_dir.mkdir(parents=True, exist_ok=True)
        batch_pattern = str(batch_dir / f"frame_%08d.{output_format}")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-vsync", "vfr",
            "-q:v", str(quality),
            batch_pattern,
        ]

        logger.debug(
            "[extract_frames_by_indices] batch %d–%d: %d frames",
            batch_start, batch_start + len(batch) - 1, len(batch),
        )

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3600,
            )
        except subprocess.TimeoutExpired:
            raise FFmpegError("Frame extraction by indices timed out", -1, "")
        except FileNotFoundError:
            raise FFmpegNotFoundError("ffmpeg not found on PATH")

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            if "Invalid data" in stderr or "moov atom not found" in stderr:
                raise VideoCorruptedError(f"Cannot extract frames: {stderr}")
            raise FFmpegError(
                f"Frame extraction by indices failed for batch {batch_start}",
                returncode=proc.returncode,
                stderr=stderr,
            )

        # Rename extracted files to reflect original frame numbers
        # FFmpeg names them frame_00000001.jpg, frame_00000002.jpg etc.
        # We rename to frame_XXXXXXXX.jpg matching the original video frame number
        extracted = sorted(batch_dir.glob(f"frame_*.{output_format}"))
        for seq_path, orig_idx in zip(extracted, batch):
            dest_name = f"frame_{orig_idx:08d}.{output_format}"
            dest_path = output_dir / dest_name
            seq_path.rename(dest_path)
            all_frame_paths.append(str(dest_path))

        # Remove now-empty batch subdir
        try:
            batch_dir.rmdir()
        except OSError:
            pass  # May have leftover files if extraction partially failed

    extraction_time_ms = int((time.perf_counter() - start_time) * 1000)
    all_frame_paths = sorted(all_frame_paths)

    logger.info(
        "[extract_frames_by_indices] Extracted %d frames from %s in %dms",
        len(all_frame_paths), video_path.name, extraction_time_ms,
    )

    return FrameExtractionResult(
        output_dir=str(output_dir),
        total_frames_extracted=len(all_frame_paths),
        frame_paths=all_frame_paths,
        extraction_time_ms=extraction_time_ms,
        config_used=FrameExtractionConfig(frame_skip_rate=1),  # adaptive — no single skip rate
    )

