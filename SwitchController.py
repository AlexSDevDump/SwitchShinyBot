import serial
import time

class SwitchController:
	BUTTONS = {
		'y':0, 'b':1, 'a':2, 'x':3,
		'l':4, 'r':5, 'zl':6, 'zr':7,
		'minus':8, 'plus':9,
		'l3':10, 'r3':11, 'home':12, 'capture':13
	}

	DPAD = {
		'up':0, 'up_right':45, 'right':90, 'down_right':135, 'down':180,
		'down_left':225, 'left':270, 'up_left':315, 'neutral':-1
	}

	def __init__(self, port='/dev/ttyS0', baud=115200):
		self.ser = serial.Serial(port, baud, timeout=1)
		time.sleep(3)
		print("Connected to Arduino Micro")

	def Press(self, buttons):
		"""Send multiple buttons at once"""
		if isinstance(buttons, str):
			buttons = [buttons]
		indices = []
		for b in buttons:
			if b in self.BUTTONS:
				indices.append(str(self.BUTTONS[b]))
			elif b in self.DPAD:
				self.DPad(b)
				time.sleep(0.05)
		if indices:
			cmd = "PRESS:" + ",".join(indices) + "\n"
			self.ser.write(cmd.encode())
			self.ser.flush()
			time.sleep(0.05)

	def Release(self):
		self.ser.write(b'RELEASE\n')
		self.ser.flush()
		time.sleep(0.05)

	def Tap(self, buttons, hold=0.2):
		self.Press(buttons)
		time.sleep(hold)
		self.Release()

	def DPad(self, direction, hold=0.1):
		angle = self.DPAD.get(direction, -1)
		self.ser.write(f'DPAD:{angle}\n'.encode())
		self.ser.flush()
		time.sleep(hold)
		self.ser.write(b'DPAD:-1\n')
		self.ser.flush()
		time.sleep(0.05)

	def Stick(self, side='LEFT', x=128, y=128):
		self.ser.write(f'STICK:{side}:{x}:{y}\n'.encode())
		self.ser.flush()
		time.sleep(0.05)

	def Disconnect(self):
		if self.ser and self.ser.is_open:
			self.ser.close()
			print("Disconnected")

	def read_echoes(self):
		"""Print all available Arduino echoes"""
		if not self.ser.is_open:
			return
		while self.ser.in_waiting:
			line = self.ser.readline().decode('utf-8', errors='ignore').strip()
			if line:
				print("Arduino says:", line)
