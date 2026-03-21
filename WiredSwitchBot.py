#!/usr/bin/env python3
import subprocess
import time
import random
from SwitchController import SwitchController
import cv2
import datetime
import subprocess
import csv
import numpy as np
import shlex
import threading
import collections
import shutil
import sys
import os
import signal

"""GLOBALS"""
QUITTING = False

# Initialize Controller
ctrl = None

#Stream Settings
RTSP_URL = "rtsp://192.168.101.2:554/live" #CHANGE THIS

#Frame Reader
FRAME_WIDTH = 640
FRAME_HEIGHT = 360
PREVIEW_FPS = 12
latest_frame	= None
_process	= None
_reader_thread	= None
_reader_running	= False
_frame_lock	= threading.Lock()
_start_lock	= threading.Lock()
_log_file	= None

#Screenshots Folder
OUTPUT_DIR = "screenshots"
ROLLING_FILE = os.path.join(OUTPUT_DIR, "shinyFound%01d.ts")

os.makedirs(OUTPUT_DIR, exist_ok=True)

"""Frame Reader Stuff"""
def _read_exactly(pipe, n):
	"""Read exactly n bytes from pipe, returning bytes or None on EOF."""
	buf = b""
	while len(buf) < n:
		try:
			chunk = pipe.read(n - len(buf))
		except (ValueError, OSError):
			return None
		if not chunk:
			return None
		buf += chunk
	return buf

def _frame_reader(process: subprocess.Popen):
	global latest_frame, _reader_running
	frame_size = FRAME_WIDTH * FRAME_HEIGHT * 3
	print(f"[reader] started, expecting {frame_size} bytes per frame")
	frames_read = 0
	while _reader_running:
		raw = _read_exactly(process.stdout, frame_size)
		if raw is None:
			print(f"[reader] EOF after {frames_read} frames")
			break
		frames_read += 1
		frame = np.frombuffer(raw, np.uint8).reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
		with _frame_lock:
			latest_frame = frame
	print(f"[reader] thread exiting")

def StartCapture():
	"""Start one FFmpeg process that feeds both the rolling buffer and the frame reader."""
	global _process, _reader_thread, _reader_running, _log_file
	with _start_lock:
		if _process and _process.poll() is None:
			return  # Already running

		command = [
			"ffmpeg",
			"-rtsp_transport", "tcp",
			"-fflags", "nobuffer+discardcorrupt",
			"-flags", "low_delay",
			"-reorder_queue_size", "0",
			"-buffer_size", "1024000",
			"-i", RTSP_URL,
			# Rolling buffer — direct stream copy, no filter
			"-map", "0:v",
			"-c:v", "copy",
			"-an",
			"-f", "segment",
			"-segment_time", "4",
			"-segment_wrap", "6",
			"-reset_timestamps", "1",
			"-y", ROLLING_FILE,
			# Preview — scaled + fps limited, raw pipe
			"-map", "0:v",
			"-vf", f"scale={FRAME_WIDTH}:{FRAME_HEIGHT},fps={PREVIEW_FPS}",
			"-c:v", "rawvideo",
			"-pix_fmt", "bgr24",
			"-an",
			"-f", "rawvideo",
			"pipe:1",
		]

		_log_file = open("ffmpeg.log", "w")
		_process = subprocess.Popen(
			command,
			stdout=subprocess.PIPE,
			stderr=_log_file,
			stdin=subprocess.DEVNULL,
			bufsize=0,
		)

		_reader_running = True
		_reader_thread = threading.Thread(target=_frame_reader, args=(_process,), daemon=True)
		_reader_thread.start()

def StopCapture():
	global _reader_running, _process, _reader_thread, _log_file
	print("Stopping capture")
	_reader_running = False

	if _process:
		_process.terminate()
		try:
			_process.wait(timeout=3)
		except subprocess.TimeoutExpired:
			_process.kill()
			_process.wait()
		_process = None

	if _reader_thread:
		_reader_thread.join(timeout=3)
		_reader_thread = None

	if _log_file:
		_log_file.close()
		_log_file = None

def CaptureFrame():
	with _frame_lock:
		return latest_frame.copy() if latest_frame is not None else None

def Watchdog():
	while True:
		threading.Event().wait(10)
		if _process is not None and _process.poll() is not None:
			print("FFmpeg exited unexpectedly, restarting...")
			StopCapture()
			time.sleep(2)
			StartCapture()

def WaitForFirstFrame(timeout=10):
	"""Block until the first frame arrives or timeout expires. Returns True if successful."""
	start = time.time()
	while time.time() - start < timeout:
		with _frame_lock:
			if latest_frame is not None:
				return True
		time.sleep(0.1)
	return False

def SaveFrame(filename, frame = None, stamp=False):
	if (frame is None):
		frame = CaptureFrame()

	if frame is None:
		print("NO FRAME DETECTED")
		return

	now = datetime.datetime.now()
	if stamp:
		filename += now.strftime("%Y-%m-%d_%H-%M-%S")
	path = f"screenshots/{filename}.png"
	cv2.imwrite(path, frame)

def SaveHighlight():
	StopCapture()
	time.sleep(4)

	segments = [
		os.path.join(OUTPUT_DIR, f)
		for f in os.listdir(OUTPUT_DIR)
		if f.startswith("shinyFound") and f.endswith(".ts")
	]

	if not segments:
		print("No segments found")
		return

	# Sort chronologically
	segments.sort(key=lambda x: os.path.getmtime(x))

	CONCAT_PATH = os.path.join(OUTPUT_DIR, "concat.txt")
	with open(CONCAT_PATH, "w") as f:
		for s in segments:
			f.write(f"file '{os.path.abspath(s)}'\n")

	now = datetime.datetime.now()
	filename = f"SHINY_{now.strftime('%Y-%m-%d_%H-%M-%S')}.mp4"
	path = os.path.join("screenshots", filename)

	subprocess.run([
		"ffmpeg",
		"-f", "concat",
		"-safe", "0",
		"-i", CONCAT_PATH,
		"-c", "copy",
		"-bsf:a", "aac_adtstoasc",
		path
	])

	print("Saved to", path)
	StartCapture()
	time.sleep(2)

"""Controller Stuff"""
def CreateController():
	control = SwitchController(port = '/dev/ttyS0')
	return control

def PressButtons(inputs, delay=0.1):
	global ctrl
	delay = max(float(delay), 0.1)

	if isinstance(inputs, str):
		inputs = [inputs]
	ctrl.Tap(inputs)
	time.sleep(delay)

def DisconnectController():
        global ctrl
        ctrl.Disconnect()

def ReconnectController():
        global ctrl
        ctrl.Reconnect()

"""Nice Closing"""
def QuitProgram():
	global QUITTING
	if QUITTING:
		return
	QUITTING = True
	print("Shutting down...")
	StopCapture()
	DisconnectController()
	print("Goodbye")
	sys.exit(0)

def OnExit(sig, frame):
	QuitProgram()

signal.signal(signal.SIGINT, OnExit)
signal.signal(signal.SIGTERM, OnExit)

"""Image Processing"""
def CropFrame(image, xMin, xMax, yMin, yMax):
	h, w = image.shape[:2]
	x1 = int(w * xMin)
	x2 = int(w * xMax)
	y1 = int(h * yMin)
	y2 = int(h * yMax)
	croppedFrame = image[y1:y2, x1:x2]
	return croppedFrame

def ThresholdProcessing(image, threshMin=95):
	# Convert to grayscale — white text will be brighter
	grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

	# Normalize brightness and denoise
	blurred = cv2.GaussianBlur(grey, (3, 3), 0)
	# Threshold to isolate white text
	_, binary = cv2.threshold(blurred, threshMin, 255, cv2.THRESH_BINARY)
	# Morphological cleanup
	kernel = np.ones((2, 2), np.uint8)
	cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
	cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

	return cleaned

def ThresholdDetection(binaryMask, threshold):
	whitePixels = cv2.countNonZero(binaryMask)
	totalPixels = binaryMask.shape[0] * binaryMask.shape[1]
	return ((whitePixels / totalPixels) > threshold)

"""Sequences"""
class Sequence:
	def __init__(self, game, type, target, seq, block, save):
		self.game = game #Game name
		self.type = type #Type of hunt
		self.target = target #Target Pokemon(not actually used anywhere whoops)
		self.sequence = seq #Event sequence for hunt
		self.block = block #Should it block any directions, in case of accidentally leaving grass patches
		self.save = save

def LoadGame(game):
	with open('sequences.csv', newline = '') as csvfile:
		sequenceReader  = csv.DictReader(csvfile)
		for row in sequenceReader:
			if (row['game'] == game):
				return row['game']
	return False

def LoadSequence(game, method):
	with open('sequences.csv', newline = '') as csvfile:
		sequenceReader = csv.DictReader(csvfile)
		for row in sequenceReader:
			if (row['game'] == game):
				if (row['method'] == method):
					sequence = row['sequence'].split(" ")
					return sequence
	return False

def SelectHunt():
	StartGame()
	game = LoadGame(input("Select Game: "))
	while (game == False):
		print("GAME NOT FOUND")
		game = LoadGame(input("Select Game: "))
	print(game, " loaded")

	method = input("Select Method: ")
	while (LoadSequence(game, method) == False):
		method = input("Select Method: ")

	target = input("Input Hunt Target: ")
	sequence = LoadSequence(game, method)

	block = input("Block direction?: ")

	s = input("Save regularly?: ")

	save = (s == "Y")
	currentSequence = Sequence(game, method, target, sequence, block, save)
	return currentSequence

"""Sequence Event Checks"""
def IsFloat(num):
	try:
		float(num)
		return True
	except ValueError:
		return False

def IsButton(button):
	if (button in SwitchController.BUTTONS or button in SwitchController.DPAD):
		return True
	else:
		return False

def SequenceEvent(event):
	if (IsButton(event)):
		PressButtons([event], 0.1)

	if (IsFloat(event)):
		time.sleep(float(event))

	if (event == "encounter"):
		return IsInEncounter()

	if (event == "battle"):
                image = CaptureFrame()
                return IsBattleLoaded(image)

	if (event == "reset"):
		ResetPosition()

	return False

"""Basic macros for stuff"""
def StartGame():
	print("Loading game")
	PressButtons("home", 0.75)
	PressButtons("a", 0.5)
	SaveFrame("game_loading")
	time.sleep(1.5)

def ResetPosition():
	print("Soft Reset")
	PressButtons(["a","b","x","y"], 3.8)
	rand = round(random.uniform(0, 0.2), 3)
	time.sleep(rand)
	PressButtons("a", 1.1)
	PressButtons("a", 1.1)
	time.sleep(rand)
	PressButtons("a", 2.7)
	PressButtons("a", 1.3)
	time.sleep(rand)
	PressButtons("b", 1.9)
	time.sleep(rand)

def SaveGame():
	PressButtons("x", 1)
	for i in range(4):
		PressButtons("down", 0.25)
	PressButtons("a", 1)
	PressButtons("a", 1)
	PressButtons("a", 2.8)
	PressButtons("a", 1)
	ResetPosition()

"""Event checks"""
def IsInEncounter():
	image = CaptureFrame()
	crop = CropFrame(image, 0.2, 0.8, 0.4, 0.6)
	process = ThresholdProcessing(crop, 50)
	#Check screen goes black
	encounter = not ThresholdDetection(process, 0.1)
	if (encounter):
		SaveFrame("encounter_original", image)
		SaveFrame("encounter_crop", crop)
		SaveFrame("encounter_process", process)
		print("Encounter Found")
	return encounter

def IsBattleLoaded(image):
	crop = CropFrame(image, 0.54, 0.72, 0.80, 0.95)
	process = ThresholdProcessing(crop, 120)
	loaded = ThresholdDetection(process, 0.25)
	if (loaded == True):
		SaveFrame("battle", process)
	return loaded

def CheckEncounter():
	print("Checking shiny")
	delay = 2.3
	#delay = 4.7
	time.sleep(1)
	SaveFrame("shiny_precheck")
	time.sleep(delay - 1)
	image = CaptureFrame()
	SaveFrame("shiny_raw", image)
	#Gen 3
	crop = CropFrame(image, 0.2, 0.4, 0.75, 0.85)
	#Gen 4
	#crop = CropFrame(image, 0.15, 0.4, 0.25, 0.35)
	SaveFrame("shiny_crop", crop)
	process = ThresholdProcessing(crop, 130)
	SaveFrame("shiny_check", process)
	shiny = not ThresholdDetection(process, 0.015)
	#Check shiny pokemon
	return shiny

def CheckSummary():
	image = CaptureFrame()
	SaveFrame("star_summary", image)
	crop = CropFrame(image, 0.435, 0.47, 0.215, 0.275)
	SaveFrame("star_crop", crop)
	process = ThresholdProcessing(crop, 240)
	SaveFrame("star_threshold", process)
	shiny = not ThresholdDetection(process, 0.8)
	return shiny

"""Main hunt"""
def HuntShiny(sequence):
	global ctrl
	seq = sequence.sequence
	time.sleep(3)

	foundShiny = False
	encounterCount = 1
	while (foundShiny == False):
		if (encounterCount % 100 == 0):
			if (sequence.save == True):
				SaveGame();
		i = 0
		while i < len(seq):
			if (seq[i] == "loop"):
				endIndex = -1
				for j in range(i, len(seq)):
					if (seq[j] == "end"):
						endIndex = j
						break

				if (endIndex == -1):
					return
				encounterStarted = False
				print("Looping Started")
				loops = 0
				while (encounterStarted == False):
					for l in range(i + 1, j):
						if (IsButton(seq[l]) and seq[l] == sequence.block):
							continue
						encounterStarted = SequenceEvent(seq[l])
						if (encounterStarted == True):
							break
					loops += 1
					if (loops > 20):
						ResetPosition()
						loops = 0
						time.sleep(1)

				print("Looping Ended")
				i = endIndex
				delay = 1.4
				time.sleep(delay)
				#Wait until encounter loads
				encounterLoaded = False
				print("Waiting For Encounter To Load")
				while (encounterLoaded == False):
					image = CaptureFrame()
					crop = CropFrame(image, 0.4, 0.6, 0.4, 0.6)
					process = ThresholdProcessing(crop, 75)
					#Check screen goes black
					encounterLoaded = ThresholdDetection(process, 0.4)
					if (encounterLoaded):
						print("Encounter Loaded")
					time.sleep(0.02)

			elif (seq[i] == "battle"):
				battleLoaded = False
				time.sleep(3.5)
				while (battleLoaded == False):
					image = CaptureFrame()
					battleLoaded = IsBattleLoaded(image)
					time.sleep(0.3)
				print("Battle started")
				time.sleep(0.1)

			elif (seq[i] == "check"):
				foundShiny = CheckEncounter()
				if (not foundShiny):
					print("Shiny not found")
				else:
					break

			elif (seq[i] == "summary"):
				foundShiny = CheckSummary()
				if (not foundShiny):
					print("Shiny not found")
				else:
					break
			else:
				SequenceEvent(seq[i])
			i += 1
		if (foundShiny == True):
			break
		encounterCount += 1
		print(encounterCount, " encounters")

	print("SHINY FOUND AFTER ", encounterCount, " ENCOUNTERS")
	SaveFrame("Shiny " + sequence.target, stamp = True)

	#Disconnect Controller to allow player to catch
	try:
		DisconnectController()
	except:
		pass
	time.sleep(4)
	SaveHighlight()
	caught = input("Type Y when shiny caught: ")
	while (caught != "Y"):
		caught = input("Type Y when shiny caught: ")

def main():
	global ctrl
	time.sleep(0.01)
	ctrl = CreateController()
	time.sleep(1)
	PressButtons("a", 1)
	PressButtons("b", 1)

	StartCapture()
	threading.Thread(target=Watchdog, daemon=True).start()

	if not WaitForFirstFrame(timeout=10):
		print("Stream failed, check ffmpeg.log")
		QuitProgram()
	else:
		print("Frame stream ready.")

	while True:
		time.sleep(0.01)
		sequence = SelectHunt()
		HuntShiny(sequence)

if __name__ == "__main__":
	main()
