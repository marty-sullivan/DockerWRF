#!/usr/bin/env python

from datetime import datetime, timedelta
from glob import glob
from multiprocessing import cpu_count
from os import chdir, environ as env, getcwd, mkdir, path, symlink
from shutil import rmtree
from subprocess import call, STDOUT
import json

DIR_WORK  = '/mnt/runs/' + datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S') + '/'
DIR_GFS   = DIR_WORK + 'gfs/'
DIR_GEOG  = '/mnt/shared/WPS_GEOG/'
DIR_WPS   = '/opt/WPS/'
DIR_WRF   = '/opt/WRFV3/test/em_real/'
DIR_OLD   = getcwd()

def writeNamelist(f, namelist):
  out = open(f, 'w')

  if 'share' in namelist:
    out.write("&share\n")
    for variable, values in namelist['share'].iteritems():
      out.write("{0} = ".format(variable))
      for value in values:
        out.write("{0}, ".format(value))
      out.write("\n")
    out.write("/\n\n")
    namelist.pop('share', None)
  for category, variables in namelist.iteritems():
    out.write("&{0}\n".format(category))
    for variable, values in variables.iteritems():
      out.write("{0} = ".format(variable))
      for value in values:
        out.write("{0}, ".format(value))
      out.write('\n')
    out.write('/\n\n')
  out.close()

with open('./wps.json') as tmpl:
  namelist_wps = json.loads(tmpl.read())

with open('./wrf.json') as tmpl:
  namelist_wrf = json.loads(tmpl.read())

cmd_gfs = './gfs_retrieve_latest.py {0}'.format(DIR_GFS)
call(cmd_gfs.split())

# Link the required WPS/WRF files to working directory
chdir(DIR_WORK)
symlink(DIR_WPS + 'geogrid', './geogrid')
symlink(DIR_WPS + 'metgrid', './metgrid')
symlink(DIR_WPS + 'ungrib/Variable_Tables/Vtable.GFSPARA', 'Vtable')
for f in glob(DIR_WRF + '*.TBL'):
  symlink(f, path.basename(f))
for f in glob(DIR_WRF + '*_DATA'):
  symlink(f, path.basename(f))

# Link the GFS Grib files
cmd_link_gfs = DIR_WPS + 'link_grib.csh ./gfs/gfs.'
call(cmd_link_gfs.split())

# Set WPS & WRF Dates
startTime = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=(3 - datetime.utcnow().hour % 3))
endTime   = startTime + timedelta(hours=72)

namelist_wps['share']['start_date'].append(startTime.strftime("'%Y-%m-%d_%H:%M:%S'"))
namelist_wps['share']['end_date'].append(endTime.strftime("'%Y-%m-%d_%H:%M:%S'"))

namelist_wrf['time_control']['start_year'].append(startTime.strftime("%Y"))
namelist_wrf['time_control']['start_month'].append(startTime.strftime("%m"))
namelist_wrf['time_control']['start_day'].append(startTime.strftime("%d"))
namelist_wrf['time_control']['start_hour'].append(startTime.strftime("%H"))
namelist_wrf['time_control']['start_minute'].append(startTime.strftime("%M"))
namelist_wrf['time_control']['start_second'].append(startTime.strftime("%S"))

namelist_wrf['time_control']['end_year'].append(endTime.strftime("%Y"))
namelist_wrf['time_control']['end_month'].append(endTime.strftime("%m"))
namelist_wrf['time_control']['end_day'].append(endTime.strftime("%d"))
namelist_wrf['time_control']['end_hour'].append(endTime.strftime("%H"))
namelist_wrf['time_control']['end_minute'].append(endTime.strftime("%M"))
namelist_wrf['time_control']['end_second'].append(endTime.strftime("%S"))

# Set WPS & WRF Coordinates
namelist_wps['geogrid']['e_we'].append(env['POINTS_WE'])
namelist_wps['geogrid']['e_sn'].append(env['POINTS_SN'])
namelist_wps['geogrid']['dx'].append(env['XSPACING'])
namelist_wps['geogrid']['dy'].append(env['YSPACING'])
namelist_wps['geogrid']['truelat1'].append(env['LATITUDE'])
namelist_wps['geogrid']['truelat2'].append(env['LATITUDE'])
namelist_wps['geogrid']['ref_lat'].append(env['LATITUDE'])
namelist_wps['geogrid']['ref_lon'].append(env['LONGITUDE'])
namelist_wps['geogrid']['geog_data_path'].append("'{0}'".format(DIR_GEOG))

namelist_wrf['domains']['e_we'].append(env['POINTS_WE'])
namelist_wrf['domains']['e_sn'].append(env['POINTS_SN'])
namelist_wrf['domains']['dx'].append(env['XSPACING'])
namelist_wrf['domains']['dy'].append(env['YSPACING'])

# Write Namelists
writeNamelist('namelist.wps', namelist_wps)
writeNamelist('namelist.input', namelist_wrf)

with open('output.log', 'w') as logfile:

  # Run Geogrid
  cmd_geogrid = DIR_WPS + 'geogrid.exe'
  call(cmd_geogrid.split(), stdout=logfile, stderr=STDOUT)

  # Run Ungrib
  cmd_ungrib = DIR_WPS + 'ungrib.exe'
  call(cmd_ungrib.split(), stdout=logfile, stderr=STDOUT)

  # Run Metgrid
  cmd_metgrid = DIR_WPS + 'metgrid.exe'
  call(cmd_metgrid.split(), stdout=logfile, stderr=STDOUT)

  # Run Real
  cmd_real = DIR_WRF + 'real.exe'
  call(cmd_real.split(), stdout=logfile, stderr=STDOUT)

  # Run WRF
  cmd_wrf = 'time mpiexec -n {0} {1}'.format(cpu_count(), DIR_WRF + 'wrf.exe')
  call(cmd_wrf.split(), stdout=logfile, stderr=STDOUT)

print 'DONE'
