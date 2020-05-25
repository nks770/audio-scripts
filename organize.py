#!/bin/env python3

# hos.py
#
# This script is for processing downloaded stream data for
# Hearts of Space (https://www.hos.com)

import argparse
import re
import json
import subprocess
from pathlib import Path

class bcolors:
  HEADER = '\033[95m'
  OKBLUE = '\033[94m'
  OKGREEN = '\033[92m'
  WARNING = '\033[93m'
  FAIL = '\033[91m'
  ENDC = '\033[0m'
  BOLD = '\033[1m'
  UNDERLINE = '\033[4m'

# Parse arguments
parser = argparse.ArgumentParser(description='Organize music files similar to iTunes.')
parser.add_argument('source', metavar='source', nargs='+',
                    help='One or more music files that need to be organized.')
parser.add_argument('destination', metavar='destination', nargs=1,
                    help='Destination directory where the files will be copied.')
parser.add_argument('-t','--test', action='store_true', dest='test',
                    help='Show how the files will be processed, but do not actually do anything.')
args=parser.parse_args()

source=args.source
destination=args.destination[0]

# The destination directory should already exist
if not Path(destination).is_dir():
  if args.test:
    print(f"{bcolors.WARNING}WARNING: Destination directory '{destination}' does not exist!{bcolors.ENDC}")
  else:
    raise Exception(f"{bcolors.FAIL}ERROR: Destination directory '{destination}' does not exist!{bcolors.ENDC}")

# Validate list of source files and determine whether they are mp3 or m4a
files = []
for f in source:
  ff = {'name':f}
  if not Path(f).is_file():
    if args.test:
      print(f"{bcolors.WARNING}WARNING: Source file '{f}' does not exist!{bcolors.ENDC}")
    else:
      raise Exception(f"{bcolors.FAIL}ERROR: Source file '{f}' does not exist!{bcolors.ENDC}")
  else:
    if f[-3:] in ['mp3','m4a']:
      ff.update({'type':f[-3:]}) 
      files.extend([ff])
    else:
      if args.test:
        print(f"{bcolors.WARNING}WARNING: Cannot determine type of source file '{f}'!{bcolors.ENDC}")
      else:
        raise Exception(f"{bcolors.FAIL}ERROR: Cannot determine type of source file '{f}'!{bcolors.ENDC}")

# Read metadata from source files
for ff in files:
  ffprobe = ['ffprobe', ff['name']]
  ffprobe_data = subprocess.run(ffprobe,capture_output=True,text=True).stderr.split('Metadata:')[1].split('\n')
  for d in ffprobe_data:
    if 'album_artist'==d.strip()[:12]:
      dd=re.split(r'^([^:]+):(.+)$',d)
      ff.update({'album_artist':dd[2].strip()})
    if 'album '==d.strip()[:6]:
      dd=re.split(r'^([^:]+):(.+)$',d)
      ff.update({'album':dd[2].strip()})
    if 'title'==d.strip()[:5]:
      dd=re.split(r'^([^:]+):(.+)$',d)
      ff.update({'title':dd[2].strip()})
    if 'track '==d.strip()[:6]:
      dd=re.split(r'^([^:]+):(.+)$',d)
      ff.update({'track':dd[2].strip().split('/')})
    if 'disc '==d.strip()[:5]:
      dd=re.split(r'^([^:]+):(.+)$',d)
      ff.update({'disc':dd[2].strip().split('/')})
    if 'compilation'==d.strip()[:11]:
      dd=re.split(r'^([^:]+):(.+)$',d)
      if dd[2].strip()=='1':
        ff.update({'compilation':True})
  if not 'compilation' in ff:
    ff.update({'compilation':False})
#  print(ffprobe_data)
  print("############################################################################")

print(json.dumps(files,indent=2))


