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
import mutagen
from pathlib import Path

# Define terminal colors
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
  remove_list = (':',';','/','\\','?','"','<','>','|','*','‘','’')
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

## Determine destination file name
def path_create(metadata):
  # Artist
  artist = metadata['album_artist']
  if artist == '':
    artist = metadata['artist']
  if metadata['compilation']:
    artist = 'Compilations'
  if artist == '':
    artist = 'Unknown'
  # Album
  album = metadata['album']
  if album == '':
    album = 'Unknown Album'
  # Track Title
  title = metadata['title']
  if title == '':
    title = 'Untitled'
  # Track Number 
  if metadata['track'][0] > 0:
    track = '{:02}'.format(metadata['track'][0]) 
  else:
    track = ''
  # Disc Number
  if metadata['disc'][0] > 0 and metadata['disc'][1] > 1:
    disc = '{}'.format(metadata['disc'][0])
  else:
    disc = ''

  if track!='' and disc!='':
    filename='{}-{} {}'.format(disc,track,title)
  elif track!='':
    filename='{} {}'.format(track,title)
  else:
    filename='{}'.format(title)
  filename=clean(filename[:36])
  outfile='{}/{}/{}.{}'.format(clean_dir(artist[:40]),clean_dir(album[:40]),filename,metadata['type'])
  return outfile

# Get metadata using ffprobe method
def get_metdata_ffprobe(audiofile):
  ffprobe = ['ffprobe', audiofile]
  raw_data = subprocess.run(ffprobe,capture_output=True,text=True,errors='ignore').stderr.split('\n')
  metaflag = False
  metadata = {}
  audiotype = ''
  for d in raw_data:
    if 'Stream' in d and 'Audio:' in d:
      meta = re.split(r'^(.*Audio: )(\S+)(.*)$',d)
      if len(meta)>2:
        audiotype=meta[2]
    if d[2:3] != ' ':
      metaflag = False
    if metaflag:
      meta = re.split(r'^([^:]+): (.*)$',d)
      if len(meta)>2 and meta[1].strip() not in metadata.keys():
        metadata.update({meta[1].strip(): meta[2].rstrip()})
    if 'Metadata:' in d:
      metaflag = True
  if audiotype=="mp3,":
    audiotype="mp3"
  if audiotype=="aac":
    audiotype="m4a"
  if audiotype not in ('mp3','m4a'):
    raise Exception("{}Unrecognized audio file type '{}'.{}".format(bcolors.FAIL,audiotype,bcolors.ENDC))
  return [audiotype,metadata]

# Get metadata using mutagen method
def get_metdata_mutagen(audiofile):
  raw_data = mutagen.File(audiofile)
  if raw_data == None:
    raise Exception("{}Unable to interpret file {}.{}".format(bcolors.FAIL,audiofile,bcolors.ENDC))
  audiotype = ''
  if 'audio/mp1' in raw_data.mime:
    audiotype='mp3'
  elif 'audio/mp2' in raw_data.mime:
    audiotype='mp3'
  elif 'audio/mp3' in raw_data.mime:
    audiotype='mp3'
  elif 'audio/mp4' in raw_data.mime:
    audiotype='m4a'
  else:
    raise Exception("{}Unrecognized audio type: {}{}".format(bcolors.FAIL,raw_data.mime,bcolors.ENDC))
  return [audiotype,raw_data.tags]
  
# Standardize raw metadata structures
def standardize(metadata_raw):
  metadata_s = {'sense_type':metadata_raw[0]}
  metadata = metadata_raw[1] 
  try:
    for m in metadata.keys():
      if m in ('artist','©ART','TPE1'):
        metadata_s.update({'artist':''.join(metadata[m])})
      if m in ('album_artist','aART','TPE2'):
        metadata_s.update({'album_artist':''.join(metadata[m])})
      if m in ('album','©alb','TALB'):
        metadata_s.update({'album':''.join(metadata[m])})
      if m in ('title','©nam','TIT2'):
        metadata_s.update({'title':''.join(metadata[m])})
      if m in ('genre','©gen','TCON'):
        metadata_s.update({'genre':''.join(metadata[m])})
      if m in ('encoder','©too','TSSE'):
        metadata_s.update({'encoder':''.join(metadata[m])})
      if m in ('date','©day'):
        metadata_s.update({'date':''.join(metadata[m])})
      if m in ('TDRC'):
        metadata_s.update({'date':str(metadata[m])})
      if m in ('track','TRCK'):
        d=''.join(metadata[m]).split('/')
        try:
          d1=int(d[0])
        except Exception:
          d1=0
        try:
          d2=int(d[1])
        except Exception:
          d2=0
        metadata_s.update({'track':[d1,d2]})
      if m=='trkn':
        d=metadata[m]
        try:
          d1=d[0][0]
        except Exception:
          d1=0
        try:
          d2=d[0][1]
        except Exception:
          d2=0
        metadata_s.update({'track':[d1,d2]})
      if m in ('disc', 'TPOS'):
        d=''.join(metadata[m]).split('/')
        try:
          d1=int(d[0])
        except Exception:
          d1=0
        try:
          d2=int(d[1])
        except Exception:
          d2=0
        metadata_s.update({'disc':[d1,d2]})
      if m=='disk':
        d=metadata[m]
        try:
          d1=d[0][0]
        except Exception:
          d1=0
        try:
          d2=d[0][1]
        except Exception:
          d2=0
        metadata_s.update({'disc':[d1,d2]})
      if m in ('cpil'):
        if metadata[m]:
          metadata_s.update({'compilation':True})
        else:
          metadata_s.update({'compilation':False})
      if m in ('compilation','TCMP'):
        if ''.join(metadata[m])=='1':
          metadata_s.update({'compilation':True})
        else:
          metadata_s.update({'compilation':False})
      if m in ('comment','©cmt','COMM::eng') and ''.join(metadata[m]) != 'Other':
        metadata_s.update({'comment':''.join(metadata[m])})
  except Exception:
    pass

  for m in ('artist','album_artist','album','title','genre','encoder','date','comment'):
    if m not in metadata_s.keys():
      metadata_s.update({m:''})
  for m in ('disc','track'):
    if m not in metadata_s.keys():
      metadata_s.update({m:[0,0]})
  if 'compilation' not in metadata_s.keys():
    metadata_s.update({'compilation':False})
  return metadata_s


# Parse arguments
parser = argparse.ArgumentParser(description='Organize music files similar to iTunes.')
parser.add_argument('source', metavar='source', nargs='*',
                    help='One or more music files that need to be organized.')
parser.add_argument('destination', metavar='destination', nargs=1,
                    help='Destination directory where the files will be copied [REQUIRED].')
parser.add_argument('-a','--all', action='store_true', dest='all',
                    help='Operate recursively on all files in the current working directory.')
parser.add_argument('-t','--test', action='store_true', dest='test',
                    help='Show the constructed mkdir and copy commands, but do not actually do anything.')
parser.add_argument('-r','--run',action='store_true',dest='run',
                    help='Actually copy the files.')
parser.add_argument('-m','--move',action='store_true',dest='move',
                    help='Move the files instead of copying them (copy is the default).')
parser.add_argument('-c','--cleanup',action='store_true',dest='clean_empty_dirs',
                    help='Use "rmdir" to clean up extraneous empty directories.')
args=parser.parse_args()

destination=args.destination[0]

# The destination directory should already exist
if not Path(destination).is_dir():
  if not args.run:
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
if len(source)<1 and not args.clean_empty_dirs:
  raise Exception(f"{bcolors.FAIL}ERROR: Please specify one or more mp3/m4a files, or use the --all option.{bcolors.ENDC}")

# Validate list of source files and determine whether they are mp3 or m4a
files = []
for f in source:
  ff = {'name':f}
  if not Path(f).is_file():
    if not args.run:
      print(f"{bcolors.WARNING}WARNING: Source file '{f}' does not exist!{bcolors.ENDC}")
    else:
      raise Exception(f"{bcolors.FAIL}ERROR: Source file '{f}' does not exist!{bcolors.ENDC}")
  else:
    if f[-3:] in ['mp3','m4a']:
      ff.update({'type':f[-3:]}) 
      files.extend([ff])
    else:
      if not args.run:
        print(f"{bcolors.WARNING}WARNING: Cannot determine type of source file '{f}'!{bcolors.ENDC}")
      else:
        raise Exception(f"{bcolors.FAIL}ERROR: Cannot determine type of source file '{f}'!{bcolors.ENDC}")

# Read metadata from source files using ffprobe (part of ffmpeg)
i = 0
j = len(files)
try:
  digits=math.floor(math.log10(j))+1
except:
  digits=1
progress='Scanning metadata {:'+str(digits)+'}/{:'+str(digits)+'} -- {:7.2%} ...'

for ff in files:
  i = i + 1
  print(progress.format(i,j,i/j),ff['name'])
#  print(progress.format(i,j,i/j),end='\r')

## ffprobe (FFmpeg) method
#  metadata=standardize(get_metdata_ffprobe(ff['name']))

## Mutagen method
  metadata=standardize(get_metdata_mutagen(ff['name']))

  ff.update(metadata)
  if ff['type'] != ff['sense_type']:
    raise Exception("{}File contents ({}) do not match file extension ({}).{}".format(bcolors.FAIL,ff['sense_type'],ff['type'],bcolors.ENDC))

  ff.update({'outfile':path_create(ff)}) 

  # Test
#  if ff['name'].upper() != ff['outfile'].upper():
#    print("\n")
#    print("{}ITUNES: {}{}".format(bcolors.FAIL,ff['name'],bcolors.ENDC))
#    print("{}PYTHON: {}{}".format(bcolors.FAIL,ff['outfile'],bcolors.ENDC))
#    raise Exception(f"{bcolors.FAIL}Conflict error!{bcolors.ENDC}")

dirs = []
for ff in files:
  d = re.split(r'(.*/)(.+)',ff['outfile'])[1][:-1]
  if d not in dirs:
    dirs.extend([d])

cmds = []
for d in dirs:
  if not Path('{}/{}'.format(destination,d)).is_dir():
    cmds.extend([['mkdir','-pv','{}/{}'.format(destination,d)]])

for f in files:
  a=f['name']
  a2=f'./{a}'
  b='{}/{}'.format(destination,f['outfile'])
  if a!=b and a2!=b:
    if args.move:
      cmds.extend([['mv','-fv',a,b]])
    else:
      cmds.extend([['cp','-afv',a,b]])

# Test run - only show the constructed commands, but don't actually run anything.
if args.test:
  for cmd in cmds:
    print('\033[92m{}\033[0m'.format(cmd))

# Run the full job
elif args.run:

  # Run each of the constructed commands one by one
  for cmd in cmds:
    print('\033[92m{}\033[0m'.format(cmd))
    subprocess.run(cmd,check=True)


# Directory cleanup
if args.clean_empty_dirs:
  def contains_files(d):
    s = [str(x) for x in Path(d).rglob('*') if not x.is_dir()]
    return len(s)>0
  
  empty_dirs = [str(x) for x in Path(destination).rglob('*') if x.is_dir() and not contains_files(x)]
  empty_dirs.sort(key=lambda x: x.count('/'),reverse=True)
  
  cleanup_cmds = []
  for d in empty_dirs:
    cleanup_cmds.extend([['rmdir','-v',d]])
  
  # Test run
  if args.test:
    for cmd in cleanup_cmds:
      print('\033[92m{}\033[0m'.format(cmd))
  
  # Run the full job
  elif args.run:
  
    # Run each of the constructed commands one by one
    for cmd in cleanup_cmds:
      print('\033[92m{}\033[0m'.format(cmd))
      subprocess.run(cmd,check=True)


