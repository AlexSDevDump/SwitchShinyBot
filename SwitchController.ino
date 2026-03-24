#include <SwitchJoystick.h>

SwitchJoystick_ SwitchJoystick;

String inputBuffer = "";

void setup() {
  Serial.begin(115200);       // debug / echoes
  Serial1.begin(115200);      // Pi communication
  SwitchJoystick.begin();
  Serial.println("Arduino ready");
}

void loop() {
  while (Serial1.available()) {
    char c = Serial1.read();
    if (c == '\n' || c == '\r') {
      inputBuffer.trim();
      if (inputBuffer.length() > 0) {
        processCommands(inputBuffer);
      }
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}

// Handles multiple commands in one line or comma-separated buttons
void processCommands(String cmds) {
  int start = 0;
  for (int i = 0; i < cmds.length(); i++) {
    if (i + 6 < cmds.length() && 
        (cmds.substring(i, i + 6) == "PRESS:" ||
         cmds.substring(i, i + 5) == "DPAD:" ||
         cmds.substring(i, i + 6) == "STICK:")) {
      if (i != 0) {
        String cmd = cmds.substring(start, i);
        handleCommand(cmd);
        start = i;
      }
    }
  }
  handleCommand(cmds.substring(start));
}

// Actual command handler
void handleCommand(String cmd) {
  cmd.trim();
  Serial.print("CMD RECEIVED: ");
  Serial.println(cmd);

  if (cmd.startsWith("PRESS:")) {
    String btns = cmd.substring(6);
    int s = 0;
    int comma = btns.indexOf(',');
    while (comma != -1) {
      int idx = btns.substring(s, comma).toInt();
      SwitchJoystick.pressButton(idx);
      delay(10);
      Serial.print("Button pressed: ");
      Serial.println(idx);
      s = comma + 1;
      comma = btns.indexOf(',', s);
    }
    if (s < btns.length()) {
      int idx = btns.substring(s).toInt();
      SwitchJoystick.pressButton(idx);
      Serial.print("Button pressed: ");
      Serial.println(idx);
    }
  } 
  else if (cmd == "RELEASE") {
    for (int i = 0; i < 16; i++) SwitchJoystick.releaseButton(i);
    SwitchJoystick.setXAxis(128);
    SwitchJoystick.setYAxis(128);
    SwitchJoystick.setZAxis(128);
    SwitchJoystick.setRzAxis(128);
    Serial.println("All released");
  } 
  else if (cmd.startsWith("DPAD:")) {
    int angle = cmd.substring(5).toInt();
    SwitchJoystick.setHatSwitch(angle);
    Serial.print("DPad angle: ");
    Serial.println(angle);
  } 
  else if (cmd.startsWith("STICK:")) {
    int first = cmd.indexOf(':', 6);
    int second = cmd.indexOf(':', first + 1);
    String side = cmd.substring(6, first);
    int x = cmd.substring(first + 1, second).toInt();
    int y = cmd.substring(second + 1).toInt();
    if (side == "LEFT") {
      SwitchJoystick.setXAxis(x);
      SwitchJoystick.setYAxis(y);
    } else {
      SwitchJoystick.setZAxis(x);
      SwitchJoystick.setRzAxis(y);
    }
    Serial.println("Stick updated: " + cmd);
  }
}