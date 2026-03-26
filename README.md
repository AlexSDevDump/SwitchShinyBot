This is a janky python script, and your experience may vary.


-Installation

If you are using the wireless script, it requires NXBT to be installed as that powers basically all of it, so please visit https://github.com/Brikwerk/nxbt for more info.
NXBT requires root access to the bluetooth controller, so make sure it can get that.
I would recommend running this on a Pi 4 or higher device, as you may encounter some memory and processing issues when handling frames, depending on the video feed settings.


-Streaming via RTSP

If, like me, you are streaming your footage to the host device via RTSP, simply edit the RTSP_URL line in the script to yours, and it should run smoothly as is. Just ensure the resoulution and framerate settings are adequate.

-Direct Connection To Capture Card

If you have a Capture Card that your device is able to ready locally, you can skip all of the stream stuff and change it to the device's internal address. You will have to rewrite a few bits to get it to work, and no I don't have that set up as mine wouldn't detect. I told you this was janky.


-How To Use The Bot

In game, make sure you are in position to where you want to be hunting, eg in grass or in front of a static encounter.

Save the game and make sure that the pause menu is hovering over Pokedex.

Press the home button and navigate to the controller menu, enter Change Grip/Order menu.

Run the bot, wait for it to open the stream and start the controller connection.

If needed, open bluetoothctl and type yes when prompted.

The controller should now connect, and load the game up.

Type in your game (FRLG, RSE etc), method (re, sr etc), target, and if you want to block any directions so you don't accidentally run out of the grass.

Let it run and pray that the shinies turn up.


-Create your own sequences

Open the sequences.csv, and type out on a new line, following the expected pattern. The game and method can be called anything.

Button inputs: a,b,x,y,up,down,left,right,l,r,zl,zr,plus,minus,home,capture.

Loop control: loop, end. Use as loop left right end to walk left and right repeatedly.

Events: encounter, check, battle, summary. Encounter scans for a black screen, check times the battle length for a shiny, battle scans if the battle menu has loaded, summarry looks at the Pokemon summary screen for the shiny star indicator.

Floats: 0.5 for example adds a 0.5 second delay.
