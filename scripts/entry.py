#!/usr/bin/env python

from datetime import datetime, timedelta
from glob import glob
from multiprocessing import cpu_count
from os import chdir, environ as env, getcwd, mkdir, path, symlink
from shutil import rmtree
from subprocess import call

DIR_DATA  = '/data/'
DIR_GFS   = '/data/gfs/'
DIR_GEOG  = '/data/WPS_GEOG/'
DIR_WPS   = '/opt/WPS/'
DIR_WRF   = '/opt/WRFV3/test/em_real/'
DIR_OLD   = getcwd()

cmd_gfs = './gfs_retrieve_latest.py {0}'.format(DIR_GFS)
call(cmd_gfs.split())

# Link the required WPS/WRF files to working directory
chdir(DIR_DATA)
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


