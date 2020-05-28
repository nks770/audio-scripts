#!/bin/env python3

# hos.py
#
# This script is for processing downloaded stream data for
# Hearts of Space (https://www.hos.com)

import argparse
import re
import json
import math
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

# Function to clean up file names
def clean(s):
  remove_list = [':',';','/','\\','?','"','<','>','|','*','’']
  clean_s = s
  for char in remove_list:
    clean_s = clean_s.replace(char,'_')
  return clean_s.rstrip()

# Function to clean up directory names
def clean_dir(s):
  clean_s = clean(s)
  if clean_s=='':
    clean_s='_'
  if clean_s[:1] in '. ':
    clean_s = '_'+clean_s[1:]
  if clean_s[-1:]=='.':
    clean_s = clean_s[:-1]+'_'
  return clean_s.rstrip()

# Parse arguments
parser = argparse.ArgumentParser(description='Organize music files similar to iTunes.')
parser.add_argument('source', metavar='source', nargs='*',
                    help='One or more music files that need to be organized.')
parser.add_argument('destination', metavar='destination', nargs=1,
                    help='Destination directory where the files will be copied.')
parser.add_argument('-a','--all', action='store_true', dest='all',
                    help='Operate recursively on all files in the current working directory.')
parser.add_argument('-t','--test', action='store_true', dest='test',
                    help='Show how the files will be processed, but do not actually do anything.')
args=parser.parse_args()

destination=args.destination[0]

# The destination directory should already exist
if not Path(destination).is_dir():
  if args.test:
    print(f"{bcolors.WARNING}WARNING: Destination directory '{destination}' does not exist!{bcolors.ENDC}")
  else:
    raise Exception(f"{bcolors.FAIL}ERROR: Destination directory '{destination}' does not exist!{bcolors.ENDC}")

# If the 'all' option was selected, then glob the files
if args.all:
  source = []
  for ext in ('mp3','m4a'):
    source.extend([str(x) for x in list(Path('.').rglob('*.{}'.format(ext))) if x.is_file()])
else:
  source=args.source

source.sort()

# Check whether there are any source files to operate on
if len(source)<1:
  raise Exception(f"{bcolors.FAIL}ERROR: Please specify one or more mp3/m4a files, or use the --all option.{bcolors.ENDC}")

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
i = 0
j = len(files)
digits=math.floor(math.log10(len(files)))+1
progress='Scanning metadata with ffprobe {:'+str(digits)+'}/{:'+str(digits)+'} -- {:7.2%} ...'

for ff in files:
  i = i + 1
  print(progress.format(i,j,i/j), end='\r')
  ffprobe = ['ffprobe', ff['name']]
  ffprobe_raw = subprocess.run(ffprobe,capture_output=True,text=True).stderr.split('Metadata:')
  if len(ffprobe_raw)>1:
    ffprobe_data=ffprobe_raw[1].split('\n')
  else:
#    print(ff['name'])
    ffprobe_data=['']
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
#for ff in files:
  ff['track']=[int(x) for x in ff['track']]
  ff['disc']=[int(x) for x in ff['disc']]

# Determine destination file name
#for ff in files:
  # Artist
  artist = ff['album_artist']
  if artist == '':
    artist = ff['artist']
  if ff['compilation']:
    artist = 'Compilations'
  if artist == '':
    artist = 'Unknown'
  # Album
  album = ff['album']
  if album == '':
    album = 'Unknown'
  # Track Title
  title = ff['title']
  if title == '':
    title = 'Untitled'
  # Track Number 
  if ff['track'][0] > 0:
    track = '{:02}'.format(ff['track'][0]) 
  else:
    track = ''
  # Disc Number
  if ff['disc'][0] > 0 and ff['disc'][1] > 1:
    disc = '{}'.format(ff['disc'][0])
  else:
    disc = ''

  if track!='' and disc!='':
    filename='{}-{} {}'.format(disc,track,title)
  elif track!='':
    filename='{} {}'.format(track,title)
  else:
    filename='{}'.format(title)
  filename=clean(filename[:36])
  outfile='{}/{}/{}.{}'.format(clean_dir(artist[:40]),clean_dir(album[:40]),filename,ff['type'])
  ff.update({'outfile':outfile}) 

  # Test
  if ff['name'] != ff['outfile']:
    print("\n")
    print("{}ITUNES: {}{}".format(bcolors.FAIL,ff['name'],bcolors.ENDC))
    print("{}PYTHON: {}{}".format(bcolors.FAIL,ff['outfile'],bcolors.ENDC))
    raise Exception(f"{bcolors.FAIL}Conflict error!{bcolors.ENDC}")
    
# Debug
#print(json.dumps(files,indent=2))


