#!/usr/local/bin/python

import ftp

from argparse import ArgumentParser
from datetime import datetime, timedelta
from os import chdir, getcwd, mkdir, system
from shutil import rmtree
from socket import gethostname
from subprocess import call
from sys import exit
from time import localtime, strftime, strptime, time

arg = ArgumentParser()
#arg.add_argument('-s', help="Start Date")
#arg.add_argument('-e', help="End Date")
arg.add_argument('-d', help="Max Domains")
arg.add_argument('-t', help="Namelist Template Directory")
arg.add_argument('-H', help="Path to host list file")
args = arg.parse_args()

NOW = datetime.now()

DIR_OUT = getcwd() + '/'
DIR_LOG = DIR_OUT + 'logs/'
DIR_LOCAL_TMP = '/tmp/%s/' % NOW.strftime('%Y-%m-%d_%H-%M-%S')
DIR_REMOTE_TMP = '/usr/local/wrf/tmp/%s/' % NOW.strftime('%Y-%m-%d_%H-%M-%S')
DIR_GFS = DIR_LOCAL_TMP + 'gfs/'
DIR_WRF_ROOT = '/usr/local/wrf/%s/'
DIR_WPS = DIR_WRF_ROOT % 'WPS'
DIR_WRF = DIR_WRF_ROOT % 'WRFV3/test/em_real'
DIR_WPS_GEOG = DIR_WRF_ROOT % 'WPS_GEOG'

if args.t != None:
    DIR_TEMPLATES = args.t + '/'
else:
    DIR_TEMPLATES = DIR_WRF_ROOT % 'templates'

CMD_LN = 'ln -sf %s %s'
CMD_CP = 'cp %s %s'
CMD_MV = 'mv %s %s'
CMD_CHMOD = 'chmod -R %s %s'
CMD_LINK_GRIB = DIR_WPS + 'link_grib.csh ./gfs/gfs.' 
CMD_GEOGRID = DIR_WPS + 'geogrid.exe >& geogrid.exe.log'
CMD_UNGRIB = DIR_WPS + 'ungrib.exe >& ungrib.exe.log'
CMD_METGRID = DIR_WPS + 'metgrid.exe >& metgrid.exe.log'
CMD_REAL = DIR_WRF + 'real.exe >& real.exe.log'
CMD_WRF = 'time /usr/local/wrf/LIBRARIES/mpich/bin/mpiexec -f %s %swrf.exe >& wrf.exe.log' % (DIR_TEMPLATES + 'hosts', DIR_WRF)

FTP_PATH = 'ftp://ftpprd.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.%s/'

if args.d != None and args.d > 0:
    MAX_DOMAINS = int(args.d)
else:
    MAX_DOMAINS = 1

try:
    with open(DIR_TEMPLATES + 'namelist.wps', 'r') as namelist:
        NAMELIST_WPS = namelist.read()
    with open(DIR_TEMPLATES + 'namelist.input', 'r') as namelist:
        NAMELIST_WRF = namelist.read()
except:
    print 'Error reading namelist files'
    exit()

try: rmtree(DIR_LOCAL_TMP)
except: pass
mkdir(DIR_LOCAL_TMP)
try: rmtree(DIR_LOG)
except: pass
mkdir(DIR_LOG)
mkdir(DIR_GFS)
chdir(DIR_LOCAL_TMP)


# WPS Links
cmd = CMD_LN % (DIR_WPS + 'geogrid', './')
cmd = cmd + '; ' + CMD_LN % (DIR_WPS + 'metgrid', './')
cmd = cmd + '; ' + CMD_LN % (DIR_WPS + 'ungrib/Variable_Tables/Vtable.GFSPARA', 'Vtable')
system(cmd)

# WRF Links
cmd = CMD_LN % (DIR_WRF + '*.TBL', './')
cmd = cmd + '; ' + CMD_LN % (DIR_WRF + '*_DATA', './')
system(cmd)

# Insert Dates into Namelists
cur_hour = NOW.hour
if cur_hour >= 0 and cur_hour < 6: z = 0
elif cur_hour >= 6 and cur_hour < 12: z = 6
elif cur_hour >= 12 and cur_hour < 18: z = 12
else: z = 18

run_date = NOW.replace(hour = z,minute = 0,second = 0,microsecond = 0)
forecast_start = run_date.replace(day = run_date.day + 1,hour = 6)
forecast_end = forecast_start.replace(day = forecast_start.day + 1, hour = 9)

# WPS Namelist
wps_dates = ' start_date = '
for i in range(0, MAX_DOMAINS):
    wps_dates = wps_dates + forecast_start.strftime("'%Y-%m-%d_%H:%M:%S', ")
wps_dates = wps_dates + '\n end_date = '
for i in range(0, MAX_DOMAINS):
    wps_dates = wps_dates + forecast_end.strftime("'%Y-%m-%d_%H:%M:%S', ")

with open('namelist.wps', 'w') as namelist:
    namelist.write(NAMELIST_WPS.replace('%DATES%', wps_dates))

# WRF Namelist
wrf_dates = ' start_year = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + forecast_start.strftime('%Y, ')
wrf_dates = wrf_dates + '\n start_month = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + forecast_start.strftime('%m, ')
wrf_dates = wrf_dates + '\n start_day = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + forecast_start.strftime('%d, ')
wrf_dates = wrf_dates + '\n start_hour = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + forecast_start.strftime('%H, ')
wrf_dates = wrf_dates + '\n start_minute = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + '00, '
wrf_dates = wrf_dates + '\n start_second = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + '00, '
wrf_dates = wrf_dates + '\n end_year = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + forecast_end.strftime('%Y, ')
wrf_dates = wrf_dates + '\n end_month = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + forecast_end.strftime('%m, ')
wrf_dates = wrf_dates + '\n end_day = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + forecast_end.strftime('%d, ')
wrf_dates = wrf_dates + '\n end_hour = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + forecast_end.strftime('%H, ')
wrf_dates = wrf_dates + '\n end_minute = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + '00, '
wrf_dates = wrf_dates + '\n end_second = '
for i in range(0, MAX_DOMAINS):
    wrf_dates = wrf_dates + '00, '

with open('namelist.input', 'w') as namelist:
    namelist.write(NAMELIST_WRF.replace('%DATES%', wrf_dates))

start_date = run_date.strftime('%Y%m%d%H')

local_gfs = DIR_GFS + 'gfs.' + start_date
remote_gfs = FTP_PATH % start_date

startTime = int(time())
ftpQueue = []
for i in range(0, 75, 3):
    hr = '%03d' % i
    #file_name = 'gfs.t%sz.pgrbf%s.grib2' % (start_date[-2:], hr)
    file_name = 'gfs.t%sz.pgrb2.1p00.f%s' % (start_date[-2:], hr)
    local_path = local_gfs + file_name
    remote_path = remote_gfs + file_name
    ftpQueue.append((remote_path, local_path))
ftp.getMulti(ftpQueue)

# Link the grib files
system(CMD_LINK_GRIB)

elapsed = int(time()) - startTime
print 'GFS retrieved in: ' + str(elapsed)

startTime = int(time())
system(CMD_GEOGRID)

elapsed = int(time()) - startTime
print 'Geogrid ran in: ' + str(elapsed)

startTime = int(time())
system(CMD_UNGRIB)

elapsed = int(time()) - startTime
print 'Ungrib ran in: ' + str(elapsed)

startTime = int(time())
system(CMD_METGRID)

elapsed = int(time()) - startTime
print 'Metgrid ran in: ' + str(elapsed)

startTime = int(time())
system(CMD_REAL)

elapsed = int(time()) - startTime
print 'Real ran in: ' + str(elapsed)

cmd = CMD_CP % (DIR_LOCAL_TMP + 'rsl.*', DIR_LOG + 'real/')
mkdir (DIR_LOG + 'real/')
system(cmd)

startTime = int(time())
system(CMD_MV % (DIR_LOCAL_TMP, DIR_REMOTE_TMP))
chdir(DIR_REMOTE_TMP)
system(CMD_CHMOD % ('777', DIR_REMOTE_TMP))

elapsed = int(time()) - startTime
print 'Files copied in: ' + str(elapsed)

startTime = int(time())
system(CMD_WRF)

elapsed = int(time()) - startTime
print 'WRF ran in: ' + str(elapsed)

cmd = CMD_CP % (DIR_REMOTE_TMP + 'wrfout*', DIR_OUT)
cmd = cmd + '; ' + CMD_CP % (DIR_REMOTE_TMP + '*.log rsl.*', DIR_LOG)
system(cmd)

#rmtree(DIR_REMOTE_TMP)
