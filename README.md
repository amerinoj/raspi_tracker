Raspi_tracker: A Simple GPS Tracker for Rasberry
-------

# Description
Raspi_tracker is a simple GPS tracker with html viewer and client program to adjust the parameters. It was originally targeted Raspberry Pi (as display), but it **might** work with other Linux distros. 
In general, Raspi_tracker does not require re-compilation should work on an "out of the box" Raspberry Pi.

Html viewer
![alt text](https://github.com/amerinoj/raspi_tracker/blob/master/img/Example.png?raw=true) 

Client software
![alt text](https://github.com/amerinoj/raspi_tracker/blob/master/img/Client.png?raw=true) 

# Installation
```
sudo -i
bash <(curl -s https://raw.githubusercontent.com/amerinoj/raspi_tracker/master/install.sh) 
```

# Basic configuration
## Config Thingspeak channels and api key
Open a free account for small non-commercial projects
https://thingspeak.com/prices/thingspeak_home

Config your channel with 4 fields 'lat' 'long' 'alt' 'time'
![alt text](https://github.com/amerinoj/raspi_tracker/blob/master/img/thingspeak_fields.png?raw=true)

Get your api keys
![alt text](https://github.com/amerinoj/raspi_tracker/blob/master/img/thingspeak_api_key.png?raw=true)

Edit gps-traker.html and replace 'thing_url' and 'thing_key' with your url channel id and read api key. 

```
const thing_url = "https://api.thingspeak.com/channels/0000000/";
const thing_key = "api_key=XXXXXXXXXXXXXXXX";
```

Edit raspi_tracker.conf

`[upload]`
Configure 'url' with your thingspeak write api key. 
```
url = https://api.thingspeak.com/update?api_key=XXXXXXXXXXXXXXXX
```

`[gps]`
Configure your gps device  parameters.
```
device_path =/dev/ttyACM0
baudrate = 11520
timeout = 50
gps_precision = 12
```


## Config Google Maps  api key
Open a free google account and create a google platform project.
Follow the next wiki:
https://developers.google.com/maps/documentation/javascript/get-api-key

You need assigned  'Maps JavaScript API' in your project . if in addition you assigned  'Directions API' you can use 'driving' and 'walking' simulation in the map. But 'Directions API' has a payment restrincion or trial time.
![alt text](https://github.com/amerinoj/raspi_tracker/blob/master/img/google_api.png?raw=true)

Edit gps-traker.html and replace 'src="https://maps.googleapis.com/maps/api/js?key'  with your google url api key. 
```
<script  src="https://maps.googleapis.com/maps/api/js?keyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"></script>	
```

# Advanced configuration
## Configure raspi_tracker settings

Adjust config settings in  /opt/raspi_tracker/raspi_tracker.conf

`[gps]`
Configure your gps device  parameters.
```
device_path =/dev/ttyACM0
baudrate = 11520
timeout = 50
gps_precision = 12
```

`[miscellanea]`
If minimum_upload is enable the position will be update only if the gps target go out from the current assumption.
The current position is a perimeter calculated from current position plus gps accuracy
gps accuracy = gps_precision ^ Hdop
```
minimum_upload = True
```

`[adaptative]`
If adaptative_time is enable the refress_time under 'upload' is omite.
Adaptative time enable a dynamic calculated time to upload the possition to cloud.
The time depend on speed of the gps
```
adaptative_time = True
```
Enable a dynamic time value to upload data to cloud. The time is calculated with REFERENCE_METERS, put in REFERENCE_METERS(meters)
The others speed are derivated from this relate REFRESS_TIME=current_speed_in_m/s(36/REFERENCE_METERS).
The minumum_time define in seconds is the minimun time used when the calculated time is less than this
```
minimum_time = 2
reference_meters = 30
```
Reference table calculated for 25 meters, for 50km/h the position will be update every 9,6 seconds
Current km/h	Current m/s		REFERENCE_METERS	REFRESS_TIME
	10			2,7777				25				1,929012346
	20			5,555555556			25				3,858024691
	30			8,333333333			25				5,787037037
	40			11,11111111			25				7,716049383
	50			13,88888889			25				9,645061728
	60			16,66666667			25				11,57407407
	70			19,44444444			25				13,50308642
	80			22,22222222			25				15,43209877
	90			25					25				17,36111111
	100			27,77777778			25				19,29012346
	110			30,55555556			25				21,2191358
	120			33,33333333			25				23,14814815
	130			36,11111111			25				25,07716049
	140			38,88888889			25				27,00617284
	150			41,66666667			25				28,93518519




`[share]`
The raspi tracker has a GUI client "client_tracker.pwc" to show the GPS parameters, these setting share the gps data between the two programs.
The traffic can be share in local machine or between two machines , define your bind ip address, port and interface.
```
ip = 127.0.0.1
port = 6927
dev = lo
```

`[debug]`
Change the debug level from 'info' to 'debug' to enable debug output
```
debug_level = debug
```
You can see the output debug on screen and the output is save in the file Raspi_Tracker_debug.txt defined under debug_file parameter
```
debug_file = Raspi_Tracker_debug.txt
```
Stop the service and run the program manually
```
sudo service raspi_tracker stop
sudo ./opt/raspi_tracker/raspi_tracker.py
```

## Configure client_tracker settings

Adjust config settings in  /opt/raspi_tracker/client/client_tracker.conf

`[connection]`
Define the ip and port server than is share the data. 
```
ip = 127.0.0.1
port = 6927
```
Define the network card used to reach the server
```
dev = lo
```


`[debug]`
Change the debug level from 'info' to 'debug' to enable debug output
You can see the output debug on screen and the output is save in the file Client_Tracker_debug.txt defined under debug_file parameter
```
debug_level = info
debug_file = Client_Tracker_debug.txt
```
To see the output in real time , stop the client and run from console 
```
sudo ./opt/raspi_tracker/client/client_tracker.pwc
```


# Usage

Raspi_tracker.py is install as service unther raspi_tracker.service and comming run after the system is up. 
After configured the conf files reboot the system to run the service automatically or you can start the service manually.
```
sudo service raspi_tracker start
```
To check if the services is running 
```
sudo service raspi_tracker status
```
To upload the coordinates on cloud  is need an internet connection, you can use a 3g connection or other type.
See https://github.com/amerinoj/3gconnect


