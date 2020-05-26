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

# Read metadata from source files using ffprobe (part of ffmpeg)
for ff in files:
  ffprobe = ['ffprobe', ff['name']]
  ffprobe_data = subprocess.run(ffprobe,capture_output=True,text=True).stderr.split('Metadata:')[1].split('\n')
  for d in ffprobe_data:
    if 'album_artist'==d.strip()[:12]:
      dd=re.split(r'^([^:]+):(.+)$',d)
      ff.update({'album_artist':dd[2].strip()})
    if 'artist '==d.strip()[:7]:
      dd=re.split(r'^([^:]+):(.+)$',d)
      ff.update({'artist':dd[2].strip()})
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
  if not 'title' in ff:
    ff.update({'title':''})
  if not 'artist' in ff:
    ff.update({'artist':''})
  if not 'album_artist' in ff:
    ff.update({'album_artist':''})
  if not 'album' in ff:
    ff.update({'album':''})

  if not 'track' in ff:
    ff.update({'track':['0']})
  if len(ff['track'])<2:
    ff['track'].extend(['0'])

  if not 'disc' in ff:
    ff.update({'disc':['0']})
  if len(ff['disc'])<2:
    ff['disc'].extend(['0'])

  if len(ff['track'])!=2:
    raise Exception("Error reading track number {}".format(ff['track']))
  if len(ff['disc'])!=2:
    raise Exception("Error reading disc number {}".format(ff['disc']))

# Convert tracks and discs from string to int
for ff in files:
  ff['track']=[int(x) for x in ff['track']]
  ff['disc']=[int(x) for x in ff['disc']]

# Determine destination file name
for ff in files:
  artist = ff['album_artist']
  if artist == '':
    artist = ff['artist']
  if artist == '':
    artist = 'Unknown'
  
  album = ff['album']
  if album == '':
    album = 'Unknown'

  title = ff['title']
  if title == '':
    title = 'Untitled'
 
  if ff['track'][0] > 0:
    track = '{:02}'.format(ff['track'][0]) 
  else:
    track = ''

# Debug
print(json.dumps(files,indent=2))


