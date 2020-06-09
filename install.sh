#!/bin/bash +x
set -e

# This script has been tested with the "2020-02-05-raspbian-buster-lite" image.
#test super user
if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

# Install packets
echo "Installing dependencies..."
apt-get update
apt-get --yes --force-yes install git python2 pip2 python2-tk 
pip2 install pynmea2 cpickle
echo "done."

# Download raspi_tracker to /opt (or update if already present)
echo
cd /opt
if [ -d raspi_tracker ]; then
  echo "Updating raspi_tracker..."
  cd raspi_tracker && git pull && git checkout ${1:master}
else
  echo "Downloading raspi_tracker..."
  git clone https://github.com/amerinoj/raspi_tracker.git
  cd raspi_tracker && git checkout ${1:master}
fi
echo "done."

# Prepare files 
ln /opt/raspi_tracker/raspi_tracker.service /etc/systemd/system/raspi_tracker.service
cp /opt/raspi_tracker/raspi_client.desktop /home/pi/Desktop/
chmod +x /opt/raspi_tracker/client_tracker.pwc 
chmod +x /opt/raspi_tracker/raspi_tracker.py

# Install and start raspi_tracker daemon
echo
echo "Registering and starting raspi_tracker with systemd..."
systemctl daemon-reload  
systemctl enable raspi_tracker.service  
systemctl status raspi_tracker.service   --full --no-pager  


# Finished
echo
echo "raspi_tracker has been installed."
echo "Configure Api keys in files and reboot the system"