import time
import board
import busio
import adafruit_mprls
import digitalio
from digitalio import DigitalInOut, Direction
from analogio import AnalogIn
import usb_hid
import supervisor

from adafruit_hid.mouse import Mouse
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

Version = 0.1

time.sleep(0.1)
print('Hello World!')
time.sleep(0.1)

# Import variables from settings.py 
from settings import printMode
from settings import swapAxes
from settings import invertHor
from settings import invertVert 
from settings import horMin
from settings import horMax
from settings import vertMin
from settings import vertMax
from settings import horDBLo
from settings import horDBHi
from settings import vertDBLo
from settings import vertDBHi
from settings import mouseSpeed
from settings import mouseScrollSpeed
from settings import mouseScrollDelay
from settings import mouseModeToggleDelay
from settings import sipThreshold
from settings import pufThreshold
from settings import swapSipPuf

# Leave the wild card in case we forget to add a variable to the list above.
# Editors don't like this for autocomplete, error checking, etc., but better than not running
from settings import *

print("Settings imported")

# Define HID objects
mouse = Mouse(usb_hid.devices)
#kbd = Keyboard(usb_hid.devices)

# Define inputs for each axis according to the swapAxes from settings.py
if (not swapAxes):
    hor = AnalogIn(board.A3)
    vert = AnalogIn(board.A4)
else:
    hor = AnalogIn(board.A4)
    vert = AnalogIn(board.A3)

# Transform inversion flags to be used for calculating outputs
if (not invertHor):
    horDirection = 1
else:
    horDirection = -1

if (not invertVert):
    vertDirection = 1
else:
    vertDirection = -1

def range_map(value, in_min, in_max, out_min, out_max):
    return max(out_min, min(out_max, (value - in_min) * (out_max - out_min)
               / (in_max - in_min) + out_min))

prevLCValue = False
prevRCValue = False
lc = False
rc = False

mouseEnable = True

mouseMode = True
rcDownTime = 0.0
mouseModeToggled = False
rightButtonFlag = False
leftButtonFlag = False
scrollBlinkValue = 0

printDelay = 1
counter = 0

i2c = busio.I2C(board.SCL, board.SDA)

# Simplest use, connect to default over I2C
mpr = adafruit_mprls.MPRLS(i2c, psi_min=0, psi_max=25)

initPressure = mpr.pressure

led = DigitalInOut(board.D1)
led.direction = Direction.OUTPUT

while True:
    # Read pressure
    newPressure = mpr.pressure

    if swapSipPuf == True:
		if newPressure > initPressure + sipThreshold:
			lc = True
		else:
			lc = False

		if newPressure < initPressure - pufThreshold:
			rc = True
		else:
			rc = False
    else:
		if newPressure < initPressure - sipThreshold:
			lc = True
		else:
			lc = False

		if newPressure > initPressure + pufThreshold:
			rc = True
		else:
			rc = False

    # Update left mouse button
    if prevLCValue != lc:
        if lc:
            print("               LC Press")
            mouse.press(Mouse.LEFT_BUTTON)
            leftButtonFlag = True
        else:
            print("               LC Release")
            mouse.release(Mouse.LEFT_BUTTON)
            leftButtonFlag = False
        prevLCValue = lc

    # Update right mouse button
    if prevRCValue != rc:
        if rc:
            print("               RC Press")
            rightButtonFlag = True
            rcDownTime = time.monotonic()
        else:
            print("               RC Release")
            if mouseModeToggled == False:      # press was short - issue click
                mouse.click(Mouse.RIGHT_BUTTON)
            else:
                mouseModeToggled = False
            rightButtonFlag = False
        prevRCValue = rc
    elif rc and mouseModeToggled == False:
        rcPressLength = time.monotonic() - rcDownTime
        if rcPressLength >= mouseModeToggleDelay:
            mouseMode = not mouseMode
            mouseModeToggled = True
            rightButtonFlag = False

    # Get joystick inputs
    horValRaw = horDirection * range_map(hor.value, 0, 65535, -1.0, 1.0)
    vertValRaw = vertDirection *  range_map(vert.value, 0, 65535, -1.0, 1.0)

    # Scale inputs to mouse speed
    if horValRaw < horDBLo:
        horValScaled = range_map(horValRaw, horMin, horDBLo, -1.0, 0)
    elif horValRaw > horDBHi:
        horValScaled = range_map(horValRaw, horDBHi, horMax, 0.0, 1.0)
    else:
        horValScaled = 0.0

    if vertValRaw < vertDBLo:
        vertValScaled = range_map(vertValRaw, vertMin, vertDBLo, -1.0, 0)
    elif vertValRaw > vertDBHi:
        vertValScaled = range_map(vertValRaw, vertDBHi, vertMax, 0.0, 1.0)
    else:
        vertValScaled = 0.0

    # If enabled, square inputs to give a non-linear response
    if squaredInput:
        horValScaled = horValScaled * abs(horValScaled)
        vertValScaled = vertValScaled * abs(vertValScaled)

    mouseHor = (int)(mouseSpeed * horValScaled)
    mouseVert = (int)(mouseSpeed * vertValScaled)

    if mouseEnable == True:
        if mouseMode == True:
            # Issue mouse command
            mouse.move(mouseHor, mouseVert)
        else:
            # Issue scroll command
            scrollSpeed = mouseVert * mouseScrollSpeed
            mouse.move(wheel = scrollSpeed)
            time.sleep(mouseScrollDelay)

    if supervisor.runtime.serial_bytes_available:
        value = input().strip()
        if value == "+++":
            print("SipNPuf ", Version, " ", horMax, " ", horDBHi, " ", horMin, " ", horDBLo,
                vertMax, " ", vertDBHi, " ", vertMin, " ", vertDBLo, " ", mouseSpeed, " ", squaredInput, " ", swapSipPuf, " ")
            printMode = True
        elif value == "---": 
            mouseEnable = False

    # control LED
    if leftButtonFlag == True or rightButtonFlag == True:
        led.value = False
    elif mouseMode == False:
        scrollBlinkValue += 1
        if scrollBlinkValue > 3:
            led.value = True
            scrollBlinkValue = 0
        elif scrollBlinkValue > 1:
            led.value = False
    else:
        led.value = True
    # print - enable as desired
    printDelay -= 1
    if printMode == True and printDelay <= 0:
        printDelay = 2
        print("X ", horValRaw, " ", horValScaled, " Y ", vertValRaw, " ", vertValScaled, " P ", newPressure - initPressure)
        #if mouseMode:
        #    print("P ", newPressure) #, " X", mouseHor, " Y", mouseVert)
        #    print("P ", newPressure, " X", horValRaw, " ", horMinDisplay, " ", horMaxDisplay,  " Y", vertValRaw, " ", vertMinDisplay, " ", vertMaxDisplay)
        #else:
        #    print("P ", newPressure) #, " S", scrollSpeed)

    time.sleep(0.05)
