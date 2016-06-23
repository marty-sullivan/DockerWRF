#!/usr/bin/env python

from __future__ import print_function

from datetime import datetime, timedelta
from os import makedirs, path
from posixpath import basename
from shutil import copyfileobj
from sys import argv
from tempfile import gettempdir
from threading import Thread
from urllib2 import urlopen
from urlparse import urlsplit

GFS_PATH = argv[1] + path.sep
GFS_FILE = 'http://www.ftp.ncep.noaa.gov/data/nccf/com/gfs/prod/gfs.{0}/gfs.t{1}z.pgrb2.1p00.f{2:03d}'
GFS_CYCLE_BUFFER = 5

if not path.exists(GFS_PATH):
  makedirs(GFS_PATH)

def download_grib(path_remote):
  grib_remote = urlopen(path_remote)
  path_local = GFS_PATH + basename(urlsplit(grib_remote.geturl()).path)
  with open(path_local, 'wb') as grib_local:
    copyfileobj(grib_remote, grib_local)

cycle = datetime.utcnow() - timedelta(hours=GFS_CYCLE_BUFFER)
    
if 0 <= cycle.hour < 6:
  cycle = cycle.replace(hour=0)
elif 6 <= cycle.hour < 12:
  cycle = cycle.replace(hour=6)
elif 12 <= cycle.hour < 18:
  cycle = cycle.replace(hour=12)
else:
  cycle = cycle.replace(hour=18)
       
gribs = []
for hour in range(0, 243, 3):
  gribs.append(GFS_FILE.format(cycle.strftime('%Y%m%d%H'), cycle.strftime('%H'), hour))
#for hour in range(252, 396, 12):
#  gribs.append(GFS_FILE.format(cycle.strftime('%Y%m%d%H'), cycle.strftime('%H'), hour))
    
threads = []
for grib in gribs:
  t = Thread(target=download_grib, args=(grib,))
  t.daemon = True
  t.start()
  threads.append(t)
for t in threads:
  t.join()
