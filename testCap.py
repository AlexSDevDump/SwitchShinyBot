import subprocess
import time
from pathlib import Path

DEVICE  = "/dev/video0"
WIDTH   = 640
HEIGHT  = 480
FPS     = 10
OUTDIR  = Path("frames")

def save_frames():
	OUTDIR.mkdir(exist_ok=True)
	frame_size = WIDTH * HEIGHT * 3

	process = subprocess.Popen(
		[
			"ffmpeg",
			"-f", "v4l2",
			"-input_format", "mjpeg",
			"-video_size", f"{WIDTH}x{HEIGHT}",
			"-framerate", str(FPS),
			"-i", DEVICE,
			"-c:v", "rawvideo",
			"-pix_fmt", "bgr24",
			"-f", "rawvideo",
			"pipe:1",
		],
		stdout=subprocess.PIPE,
		stderr=subprocess.DEVNULL,
		stdin=subprocess.DEVNULL,
		bufsize=0,
	)

	if process.poll() is not None:
		print(f"Failed to open {DEVICE}")
		return

	print(f"Saving frames to {OUTDIR}/ — Ctrl+C to stop")
	index = 0

	try:
		while True:
			raw = process.stdout.read(frame_size)
			if len(raw) < frame_size:
				print("Stream ended")
				break
			index += 1
			if index % (FPS * 2) == 0:
				path = OUTDIR / f"frame_{index:06d}.jpg"
				subprocess.run(
					[
						"ffmpeg", "-y",
						"-f", "rawvideo", "-pix_fmt", "bgr24",
						"-video_size", f"{WIDTH}x{HEIGHT}",
						"-i", "pipe:0",
						"-frames:v", "1",
						str(path),
					],
					input=raw,
					capture_output=True,
				)
				print(f"Saved {path}")
	except KeyboardInterrupt:
		print("Stopping...")
	finally:
		process.terminate()
		process.wait()

if __name__ == "__main__":
	save_frames()
