#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#sudo apt-get install python python-tk
#pip2 install pynmea2 cPickle
from math import sin, cos, sqrt, atan2, radians
from time import sleep
from os import path
import threading
import datetime
import serial, string, io
import logging, sys, os, configparser
import requests 
import socket, pynmea2, cPickle, hashlib 


################### Config Read ############################
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
config = configparser.SafeConfigParser()
config.read(SCRIPT_PATH + '/raspi_tracker.conf')
################ Setup thingspeak  #########################
#Setup the Initialstate stream, give it a bucket name and the access key
URL=config.get('upload', 'url') # URL and Thingspeak Write API Key
REFRESS_TIME = config.getfloat('upload', 'refress_time') # How many seconds to upload position
##################  Miscellanea  ###########################
MIN_UPLOAD = config.getboolean('miscellanea', 'minimum_upload') #no send data if the position is the same [position +/- (  GPS_PRECISION ** 'Hdop')+Hdop  ]
#################  Adaptative time  #########################
ADAPTATIVE_TIME = config.getboolean('adaptative', 'adaptative_time')  #if is enable the [REFRESS_TIME] is omite
MINIMUN_TIME = config.getfloat('adaptative', 'minimum_time') # minimum check time for adaptive time, recommended value 2s
REFERENCE_METERS = config.getfloat('adaptative', 'reference_meters')   # in meters 

################# GPS Serial Port ###########################
DEVICE_PATH=config.get('gps', 'device_path')
DEVICE_BAUDRATE = config.getint('gps', 'baudrate')  # Baud rate
DEVICE_TIMEOUT = config.getint('gps', 'timeout')
GPS_PRECISION = config.getfloat('gps', 'gps_precision') # GPS_PRECISION in meters calibrate to U-blox7
################# Share data ###########################
HOST = config.get('share', 'ip') #Ip address to bind a connection
PORT = config.getint('share', 'port')  #Port to listen
IFACE = config.get('share', 'dev')  # Interface name
############### Output level information ###################
LEVEL_NAME=config.get('debug', 'debug_level')
DEBUG_FILE=config.get('debug', 'debug_file') # only use when LEVEL_NAME='debug'
LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warning': logging.WARNING,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}
sys_logger = logging.getLogger('Raspi_Tracker')

#initiate GPS_var
gps_data = None
gps_save  =  dict(Lat=None , Lat_m=None , Lat_s=None , Lon=None , Lon_m=None , Lon_s=None , 
			 Time=None , Hdop=None , N_sat=None , Quality=None , WGS84=None , Alt=None , Alt_units=None , 
			 WGS84_units=None , Acc=None , Diff_p=None , Speed=None)
#Collector gps data thread 
class GPSDcollector(threading.Thread):
   def __init__(self, threadID,serial_path,serial_time_out,serial_baudrate):
      threading.Thread.__init__(self)
      self.threadID = threadID
      global gps_data #bring it in scope

      self.ser = serial.Serial()
      self.ser.port  =serial_path
      self.ser.baudrate = serial_baudrate
      self.ser.timeout = serial_time_out  
      self.running = True #Start running this thread	
	  
   def run(self ):
      global gps_data
      sys_logger.info("Running waiting data")
      while self.running: 
		try:
		  if path.exists(self.ser.port) and (not self.ser.is_open ):
		      self.ser.open()	 				
		  if (path.exists(self.ser.port) and self.ser.is_open) :
		      data = self.ser.readline()
		      if data.find('GGA') > 0:  #waiting for GPGGA msg
		        gps_data = pynmea2.parse(data) #update global var
		        sleep(0.1)
		  else:
		    sys_logger.debug("GPSDcollector Device " + str(self.ser.port)+" Closed")
		    sleep (2)		
			
		except pynmea2.ParseError as e:
		    sys_logger.debug('GPSDcollector Parse error: {}'.format(e))
		    if (gps_data != None):
		       gps_data.gps_qual = 0
		    pass
		except serial.SerialException as e:
		    sys_logger.error("GPSDcollector error " + str(e))
		    if (gps_data != None):
		       gps_data.gps_qual = 0
		    if self.ser.is_open :
		       self.ser.close()
		    sleep (2)			
		    pass
		
		except Exception,e:
		    sys_logger.error("GPSDcollector Exception  " + str(e))
		    gps_data.gps_qual = 0
		    if self.ser.is_open :
		       self.ser.close()
		    sleep (2)
		    pass
			
      if self.ser.is_open :
		self.ser.close()
		sys_logger.debug("GPSDcollector Closing port")
      self.running=False
      sys_logger.info("GPSDcollector End ")		    	


#Share data between daemon and GUI
class SHAREdata(threading.Thread):
   def __init__(self,threadID,HOST,PORT,IFACE):
      threading.Thread.__init__(self)
      self.threadID = threadID
      global gps_save #bring it in scope
      sys_logger.debug("SHAREdata listen IP:"+str(HOST)+" PORT:"+str(PORT)+" IFACE:"+str(IFACE))
      self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.sock.setsockopt(socket.SOL_SOCKET, 25, IFACE +'\0')
      self.sock.settimeout(3) 
      self.sock.bind((HOST , PORT))
      self.sock.listen(1) # listen connection
      self.running = True #Start running this thread
   def run(self):
      self.connection=None
      global gps_save #bring it in scope
      while self.running:
		try:
		   while (self.connection == None) and self.running :# Wait for a connection
		      sys_logger.debug("SHAREdata Wait for a connection")
		      self.connection, self.client_address = self.sock.accept()
		      self.connection.settimeout(3) 			  
		   sys_logger.debug("SHAREdata Client connect:" + str(self.client_address))	   
		   while self.running :# Wsend continous data
		      payload_att =list()
		      payload=cPickle.dumps(gps_save) #  dictionary
		      payload_att.append(len(payload))
		      payload_att.append(hashlib.md5(payload).hexdigest()) # calc hash	 		  
		      self.connection.sendall(cPickle.dumps(payload_att)) # send payload len and hash 
		      sys_logger.debug("SHAREdata payload_len:" + str(payload_att[0]) + " payload_hash:" + str(payload_att[1] ))
		      recv_len=cPickle.loads(self.connection.recv(1024))
		      if payload_att[0] == recv_len : # check if message is received and is waiting a packet
		         sys_logger.debug("SHAREdata Reveiver payload_len:" + str(recv_len)) # the connection is stable
		         self.connection.sendall(payload) # send payload
		         recv_hash=cPickle.loads(self.connection.recv(1024))
		         if payload_att[1] == recv_hash: #check if the hash is correct
		            sys_logger.debug("SHAREdata Reveiver hash:" + str(recv_hash) + " Hash correct") # the hash is correct
		         else:
		            sys_logger.debug("SHAREdata Reveiver hash:" + str(recv_hash) + " No match ") # the report hash no match
		            self.stop()
		      else:
		         sys_logger.debug("SHAREdata Reveiver payload_len:" + str(recv_len) + " No match ") # the connection no stable
		         self.stop()
				 
				 
		      sleep(0.25) #time sleep between packets

		except  socket.timeout as e:
		   if self.connection!= None :
		      self.connection.close()
		      self.connection=None		  
		   #sys_logger.debug("SHAREdata timeout  "+ str(e))
		   sleep(0.5)
		   pass
		except Exception,e:
		   sys_logger.debug("Exception SHAREdata " + str(e))
		   if self.connection!= None :
		      self.connection.close()
		      self.connection=None	
		   sleep(1)
		   pass
      self.stop()
      self.sock.close()
      sys_logger.info("End SHAREdata closed socket")
	  
   def stop(self):
      self.running = False
      try:
		   self.connection.shutdown(socket.SHUT_RDWR)
      except:
        pass
      try:
		   self.connection.close()
      except:
        pass	  


#Print GPS debug data
def print_data_gps(data):
  sys_logger.debug("####### [GPS time]: "+ str(data['Time'])+
                  " [N_Sat]: "+ str(data['N_sat']) +
				  " [GPS quality]: " + str(data['Quality'])+"  #######" )
  sys_logger.debug('[Horizontal Precision HDOP]: ' + str(data['Hdop']) +
                    '   [WGS84]: ' + str(data['WGS84']) + str(data['WGS84_units']))
  sys_logger.debug('[Alt]:' + str(data['Alt'])+str(data['Alt_units']))
  sys_logger.debug('[Lat:] ' + str(data['Lat'])+'   [Long:] ' + str(data['Lon']))
  
  Lat_g=str("%02d°%02d'%07.4f\"" % (data['Lat'], data['Lat_m'], data['Lat_s']))
  Lon_g=str("%02d°%02d'%07.4f\"" % (data['Lon'], data['Lon_m'], data['Lon_s']))	  
  sys_logger.debug('[Lat °:] ' + Lat_g +'   [Long °: ] ' + Lon_g)
  sys_logger.debug( "Gps Accuracy : " + str(data['Acc']) +" Meters")
  sys_logger.debug( "Reference position diference: " + str(data['Diff_p'])+" Meters")
  sys_logger.debug( "Speed " + str(data['Speed'])+" m/s")
  sys_logger.debug( "Speed " + str("%06.2f" % (data['Speed']*3.6))+" Km/h")

		
#Calculate the diference in meter between coordenates
def calc_diff_postion(lat_ref,lon_ref,new_lat,new_lon):
  R = 6378.137 # approximate radius of earth in km
  lat1 = radians(lat_ref)
  lon1 = radians(lon_ref)
  lat2 = radians(new_lat)
  lon2 = radians(new_lon)
  dlon = lon2 - lon1
  dlat = lat2 - lat1
  a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
  c = 2 * atan2(sqrt(a), sqrt(1 - a))
  diff_distance = (R * c) * 1000 # in meters
  return float(diff_distance)

def fix_time_zone(tim,T_Z):			
  delta =datetime.timedelta(hours = T_Z)
  return (datetime.datetime.combine(datetime.date(1,1,1),tim) + delta ).time()
  
#upload data to cloud
def upload_cloud(data,U_URL): 
  # defining a params dict for the parameters to be sent to the API 
  Altitude=str(data['Alt'])+str(data['Alt_units'])
  PARAMS = {'field1': data['Lat'],
  'field2': data['Lon'],
  'field3': Altitude,
  'field4': data['Time']}
  try:
    sys_logger.debug( "Uploading data to " + str(U_URL))
    # sending get request and saving the response as response object
    response = requests.get(url = U_URL, params = PARAMS) 
    sys_logger.debug( "Http response:" + str(response.status_code))
  except Exception,e: 
    sys_logger.error("Excepcion in upload_cloud :"+ str(e))
    sys_logger.error( "Connection failed" )

#Init GPS Dummy values to share_data
def init_gps_dummy_values (gps_save):
  gps_save['Lat']=float(99)
  gps_save['Lat_m']=float(99)
  gps_save['Lat_s']=float(99)
  gps_save['Lon']=float(99)
  gps_save['Lon_m']=float(99)
  gps_save['Lon_s']=float(99)	
  gps_save['Time']=datetime.datetime.now().strftime('%H:%M:%S')
  gps_save['Hdop']=float(9.9)
  gps_save['N_sat']=-1
  gps_save['Quality']=0
  gps_save['WGS84']=0
  gps_save['Alt']=0	
  gps_save['Alt_units']="M"	
  gps_save['WGS84_units']="M"
  gps_save['Acc']=0
  gps_save['Diff_p']=float(0.0)
  gps_save['Speed']=float(2777.775)
  

#Fix Gps error mesure distance
def fix_gps_mesure_error (diff_p,acc):
  fix_diff=0
  if acc <= diff_p : #control mesure error 
    fix_diff=round(diff_p - acc,2)
  else:
    fix_diff=float(0.0)
  return (fix_diff)
    
#Save now gps data
def save_gps_data (gps_save,gps_data):
  num_pass=0
  tmp_num_pass=num_pass
  
  tmp_Lat=float(gps_data.latitude)
  tmp_Lat_m=float(gps_data.latitude_minutes)
  tmp_Lat_s=float(gps_data.latitude_seconds)
  tmp_Lon=float(gps_data.longitude)
  tmp_Lon_m=float(gps_data.longitude_minutes)
  tmp_Lon_s=float(gps_data.longitude_seconds)
  tmp_Alt=float(gps_data.altitude)
  tmp_Hdop=float(gps_data.horizontal_dil)
  sleep (0.1)
  while tmp_num_pass>0 :
    tmp_Lat=(float(gps_data.latitude) + tmp_Lat)/2
    tmp_Lat_m=(float(gps_data.latitude_minutes) + tmp_Lat_m)/2
    tmp_Lat_s=(float(gps_data.latitude_seconds) + tmp_Lat_s)/2
    tmp_Lon=(float(gps_data.longitude) + tmp_Lon)/2
    tmp_Lon_m=(float(gps_data.longitude_minutes) + tmp_Lon_m)/2
    tmp_Lon_s=(float(gps_data.longitude_seconds) + tmp_Lon_s)/2
    tmp_Alt=(float(gps_data.altitude) + tmp_Alt)/2
    tmp_Hdop=(float(gps_data.horizontal_dil) + tmp_Hdop)/2	
    tmp_num_pass=tmp_num_pass-1
    if tmp_num_pass!=0 :
      sleep (0.1)	
    
  tmp_Hdop=round(tmp_Hdop,2)
  tmp_Alt=round(tmp_Alt,2)  

  Time_zone=round((( datetime.datetime.now() - datetime.datetime.utcnow() ).total_seconds() / 60 / 60) ,0 )
  gps_save['Lat']=tmp_Lat
  gps_save['Lat_m']=tmp_Lat_m
  gps_save['Lat_s']=tmp_Lat_s
  gps_save['Lon']=tmp_Lon
  gps_save['Lon_m']=tmp_Lon_m
  gps_save['Lon_s']=tmp_Lon_s
  gps_save['Time']=fix_time_zone(gps_data.timestamp,Time_zone).strftime('%H:%M:%S')	
  gps_save['Hdop']=tmp_Hdop
  gps_save['N_sat']=gps_data.num_sats
  gps_save['Quality']=gps_data.gps_qual
  gps_save['WGS84']=gps_data.geo_sep
  gps_save['Alt']=tmp_Alt
  gps_save['Alt_units']=gps_data.altitude_units	
  gps_save['WGS84_units']=gps_data.geo_sep_units
	
#Finish thread and exit
def close ():
  sys_logger.info("Killing Thread...")
  if GpsdThread.is_alive():
    GpsdThread.running = False
    GpsdThread.join() # wait for the thread to finish what it's doing
  if Share_Thead.is_alive():
    Share_Thead.running = False
    Share_Thead.join() # wait for the thread to finish what it's doing
  sys_logger.info("Done.Exiting.")  
			
def main (argv): # main function
  try:	
    GpsdThread.start() # start it up
    sys_logger.info("Starting GPS")
    init_gps_dummy_values(gps_save)
    Share_Thead.start() # start info share
	
    init_gps_dummy_values(gps_save) #init dummy values
	
    while gps_data == None : #waiting  reader is ready minimum 1s        
      sys_logger.debug("Waiting signal")
      gps_save['Time']=datetime.datetime.now().strftime('%H:%M:%S')
      sleep(2)
	  
    while (gps_data.gps_qual == 0 )  or (float(gps_data.horizontal_dil) > 20.0):# waiting quality signal	mimmum 1s
      sys_logger.debug("No quality signal")
      gps_save['Time']=datetime.datetime.now().strftime('%H:%M:%S')
      sleep(1) 
	 
    time_to_check=datetime.datetime.now()
    lat_ref_p=gps_data.latitude #initiate reference and save the first position
    lon_ref_p=gps_data.longitude #initiate reference and save the first position	
    lat_stand=lat_ref_p
    lon_stand=lon_ref_p
	
    s_time=float(4.0)
    REF_TIME=36/REFERENCE_METERS
    sys_logger.info("GPS Running")	
	

    while True:

      sys_logger.debug( "Waiting to next check")
      while datetime.datetime.now() <= (time_to_check + datetime.timedelta(0,s_time))  :
        if (gps_data.gps_qual != 0 and float(gps_data.horizontal_dil) < 20.0) :
          sleep (0.25)		
          save_gps_data(gps_save,gps_data)
          time_for_speed=datetime.datetime.now()
          lat_ref_p=gps_save['Lat'] #save new latitude position  speed
          lon_ref_p=gps_save['Lon'] #save new longitude position  speed	
          sleep (0.25)
          save_gps_data(gps_save,gps_data)
          dif_time=(datetime.datetime.now() - time_for_speed).total_seconds()
          precision=round( ( GPS_PRECISION *float(gps_save['Hdop'])) ,2)
          if precision > 999 :
            precision=999
          gps_save['Acc']=precision
          gps_save['Diff_p']=calc_diff_postion(lat_ref_p,lon_ref_p,gps_save['Lat'],gps_save['Lon'])      
          gps_save['Speed']=gps_save['Diff_p']/dif_time
          print_data_gps(gps_save) # debug data information
        else:
          sys_logger.debug("No quality signal")
          gps_save['Time']=datetime.datetime.now().strftime('%H:%M:%S')
          gps_save['Quality']=0
          gps_save['Hdop']=float(50.0)
          sleep (0.25)		  
      if (gps_save['Quality'] != 0 and  gps_save['Hdop'] < 20.0) :  		  		
        if MIN_UPLOAD:#check if the diference between current position is diferent from last position reported
          diff_position_stand=calc_diff_postion(lat_stand,lon_stand,gps_save['Lat'],gps_save['Lon'])
          sys_logger.debug( "Diference from last static position: " +str(round(diff_position_stand,2))	)
          diff_position_stand=fix_gps_mesure_error(diff_position_stand,gps_save['Acc'])
          if int(diff_position_stand) > 0 : #check if the position is diferent
            sys_logger.debug( "Diference from last static position fixed: " +str(diff_position_stand)	)	  
            upload_cloud(gps_save,URL) # upload position to cloud
            sys_logger.debug( "Position changed was upload to cloud")
            lat_stand=gps_save['Lat'] #save new position
            lon_stand=gps_save['Lon'] #save new position
          else:
            sys_logger.debug( "Position is not changed will not upload to cloud")		  
        else:
          upload_cloud(gps_save,URL) # upload position to cloud
          
        if ADAPTATIVE_TIME:# check the diference in meters between the last two mesures to reduce the time check
          if gps_save['Speed']>0:
            s_time=round(gps_save['Speed']/REF_TIME,2)
            if s_time>REFRESS_TIME:
              s_time=REFRESS_TIME
            if s_time<MINIMUN_TIME:
              s_time=MINIMUN_TIME
          else:
            s_time=MINIMUN_TIME
        	
        time_to_check=datetime.datetime.now()	  
        sys_logger.debug( "Next report in: " + str(s_time)+" Seconds")	 
	  
      else :
        time_to_check=datetime.datetime.now() # waiting quality signal
        s_time=float(2.0)
        
        
  except Exception,e:    
    sys_logger.error("Excepcion in main:"+ str(e))
    close() 
  except (KeyboardInterrupt, SystemExit): #when you press ctrl+
    sys_logger.debug("KeyboardInterrupt  Exit...")
    close() 
  
if __name__=="__main__":
  level = LEVELS.get(LEVEL_NAME, logging.NOTSET)
  sys_logger.setLevel(level)
  if (DEBUG_FILE != "") and (level <= logging.DEBUG):
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(message)s')
    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(name)s %(message)s',filename=DEBUG_FILE,level=level)
  else:
    formatter = logging.Formatter('[%(levelname)s] %(name)s %(message)s')

  handler = logging.StreamHandler()
  handler.setLevel(level)
  handler.setFormatter(formatter)
  sys_logger.addHandler(handler)
  
  if not path.exists(DEVICE_PATH) :
    sys_logger.info(DEVICE_PATH+" no found")
    sys.exit(1)
  sys_logger.info("Tracker init...")
  #wait to run
  #sleep (2)
  # create a thread to collect data
  GpsdThread = GPSDcollector(1,DEVICE_PATH,DEVICE_TIMEOUT,DEVICE_BAUDRATE) 
  # create a thread to share gps data
  Share_Thead = SHAREdata(2,HOST,PORT,IFACE)
  main (sys.argv[1:])
