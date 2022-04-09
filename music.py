#!/bin/env python3

# music.py
#
# This script is for processing, transcoding, and tagging music files
# Version 3.0
# Last updated April 2, 2022

#import sys
#import os
#import glob
import argparse
import re
import json
import math
import subprocess
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

# Control parameters
mp3_cbr_bitrates = ['32', '40', '48', '56', '64', '80', '96', '112', '128', '160', '192', '224', '256', '320']
aac_vbr_bitrates = ['1', '2', '3', '4', '5']

# Parse arguments
parser = argparse.ArgumentParser(description='Process a set of music files.')
parser.add_argument('-e','--edition',metavar='ALBUM_EDITION',dest='edition',
                    default='default',choices={'default','original','optimized','all'},
                    help='Which edition of the album should be processed. (Default: default)')
parser.add_argument('-c','--codec',metavar='CODEC',dest='codec',
                    default='mp3',choices={'mp3','aac'},
                    help='Output codec to use for transcoding. (Default: mp3)')
parser.add_argument('-b','--bitrate',metavar='BITRATE',dest='bitrate',
                    help='Specify the output bitrate (CBR) or quality (VBR).')
parser.add_argument('-r','--run',action='store_true',dest='run',
                    help='Actually run the transcode.')
parser.add_argument('-t','--test',action='store_true',dest='test',
                    help='Only show the constructed commands, do not execute anything.')
parser.add_argument('-v','--verbose',action='store_true',dest='verbose',
                    help='Verbose mode.')
args=parser.parse_args()

# Validate requested bitrate
codec = args.codec

if args.bitrate == None and codec == 'mp3':
  bitrate = 'V2'
elif args.bitrate == None and codec == 'aac':
  bitrate = '256'
else:
  bitrate = args.bitrate

if bitrate[0].upper() == "V":
  mode = 'vbr'
else:
  mode = 'cbr'

if codec == 'mp3' and mode == 'cbr':
  mp3_cbr_bitrate = bitrate
  encoding = 'LAME MP3 CBR {}kbps'.format(mp3_cbr_bitrate)
  if not mp3_cbr_bitrate in mp3_cbr_bitrates:
    raise argparse.ArgumentTypeError("Invalid CBR bitrate '{}'. Valid MP3 CBR bitrates are {}. Higher is better.".format(mp3_cbr_bitrate,mp3_cbr_bitrates))
elif codec == 'mp3' and mode == 'vbr':
  try:
    mp3_vbr_quality = float(bitrate[1:])
  except:
    mp3_vbr_quality = float(-1)
  encoding = 'LAME MP3 VBR {}'.format(mp3_vbr_quality)
  if mp3_vbr_quality < 0 or mp3_vbr_quality > 9.999:
    raise argparse.ArgumentTypeError("Invalid VBR quality '{}'. MP3 VBR quality must be between 0 and 9.999. Lower is better.".format(bitrate))
elif codec == 'aac' and mode == 'cbr':
  try:
    aac_cbr_bitrate = float(bitrate)
  except:
    aac_cbr_bitrate = float(-1)
  encoding = 'Fraunhofer FDK AAC CBR {}kbps'.format(aac_cbr_bitrate)
  if aac_cbr_bitrate < 112 or aac_cbr_bitrate > 320:
    raise argparse.ArgumentTypeError("Invalid CBR bitrate '{}'. AAC CBR bitrate must be between 112 and 320. Higher is better.".format(bitrate))
elif codec == 'aac' and mode == 'vbr':
  if len(bitrate)>1:
    aac_vbr_quality = bitrate[1:]
  else:
    aac_vbr_quality = ''
  encoding = 'Fraunhofer FDK AAC VBR {}'.format(aac_vbr_quality)
  if not aac_vbr_quality in aac_vbr_bitrates:
    raise argparse.ArgumentTypeError("Invalid VBR quality '{}'. Valid AAC VBR qualities are {}. Higher is better.".format(bitrate,aac_vbr_bitrates))
else:
  raise Exception("Unknown codec/mode {}/{}.".format(codec,mode))
  

# If doing AAC encoding, then figure out the libfdk_aac version being used.
# This section ends up with a string, for example, libfdk_aac_version='0.1.6'
libfdk_aac_version=''
if codec == 'aac':
  ffmpeg_path=subprocess.run(['which','ffmpeg'],capture_output=True,text=True).stdout.strip()
  ldd_output=[x.strip() for x in subprocess.run(['ldd',ffmpeg_path],capture_output=True,text=True).stdout.split('\n')]
  for x in ldd_output:
    a=x.split('=>')
    if 'libfdk-aac.so' in a[0]:
      libfdk=a[1].strip()
      libfdk_path=re.split(r'(.*/)(.*)',libfdk)[1]
  with open('{}/pkgconfig/fdk-aac.pc'.format(libfdk_path),'r') as pc:
    pkgconfig=pc.readlines()
  for line in pkgconfig:
    if 'Version:' in line:
      libfdk_aac_version=line.split()[1]
  if len(libfdk_aac_version)<2:
    raise Exception("Could not determine version of libfdk_aac library.")


def displayBanner(ii):
  print('#'*60)
  print('#'*25 + ' SUMMARY ' + '#'*26)
  print('#'*60)
  print('Album: "{}" by "{}" ({})'.format(ii['album_title'],ii['artist'],ii['year']))
  if ii['genre'] != None:
    print('Genre: "{}"'.format(ii['genre']))
  if ii['coverart'] != None:
    print('Cover Image: "{}"'.format(ii['coverart']))
  if ii['compilation']:
    print('Discs: {}  Tracks: {}  (Compilation)'.format(max(ii['discs']),len(ii['tracks'])))
  else:
    print('Discs: {}  Tracks: {}'.format(max(ii['discs']),len(ii['tracks'])))
  print('Encoding: {}'.format(encoding))
  print()

  # Determine maximum artist name length
  max_artist_length = 0
  max_title_length = 0
  for t in ii['tracks']:
    if len(t['artist'])>max_artist_length:
      max_artist_length = len(t['artist'])
    if len(t['title'])>max_title_length:
      max_title_length = len(t['title'])

  # Print out the track listing
  for d in ii['discs']:
    print('#'*25 + ' DISC {:2d} '.format(d) + '#'*26)
    for t in ii['tracks']:
      if t['disc'] == d:
        if args.verbose:
          print(('{:2d} {:' + '{}'.format(max_artist_length) + 's}  {:' + '{}'.format(max_title_length) + 's}  {}').format(t['track'],t['artist'],t['title'],t['file']))
        else:
          print(('{:2d} {:' + '{}'.format(max_artist_length) + 's}  {}').format(t['track'],t['artist'],t['title']))
    print('#'*60)
    print()



# Read metadata JSON
try:
  with open('metadata.json','r') as f:
    metadata = json.load(f)
except FileNotFoundError:
  with open('audio/metadata.json','r') as f:
    metadata = json.load(f)
    for m in metadata:
      if 'prefix' in m.keys():
        if m['prefix'] == None:
          m['prefix'] = 'audio'
        else:
          m['prefix'] = '/'.join(['audio',m['prefix']])
#print(json.dumps(metadata,indent=2))
  

# Determine active indices
active = []
if args.edition in ('default','original','optimized'):
  active.extend(metadata[[i for i, x in enumerate(metadata) if x['index'] == -1][0]][args.edition])
  if len(active) == 0:
    active.extend(metadata[[i for i, x in enumerate(metadata) if x['index'] == -1][0]]['default'])
if len(active) == 0 or args.edition == 'all':
  active.extend([x['index'] for i, x in enumerate(metadata) if x['index'] != -1])

if len(active) < 1:
  raise Exception('Could not identify any album editions to load.')


# Iterate through album editions
cmds = []
temp_files = []

for a in active:
  # Get index item
  b = metadata[[i for i, x in enumerate(metadata) if x['index'] == a][0]]

  # Format the album title and edition for display
  b['album_title'] = '{} [{}]'.format(b['title'],b['edition'])
  if b['edition'] == None:
    b['album_title'] = b['title']

  # Determine maximum number of discs
  b['discs'] = list(set([x['disc'] for x in b['tracks']]))

  # Print info banner
  displayBanner(b)

  # Set up formats for file names 
  max_tid=math.floor(math.log10(len(b['tracks'])))+1
  wav_format='index{}'.format(b['index']) + 'disc{:02}track{:0' + str(max_tid)+'}.wav'
  mp3_format='index{}'.format(b['index']) + 'disc{:02}track{:0' + str(max_tid)+'}.mp3'
  m4a_format='index{}'.format(b['index']) + 'disc{:02}track{:0' + str(max_tid)+'}.m4a'

  # Loop through discs
  for di in b['discs']:
    print('Processing disc {}...'.format(di))
    tracklist = [t for t in b['tracks'] if t['disc'] == di]
    numtracks = max([t['track'] for t in tracklist])

    for tr in tracklist:

      # Step 1: Decode the flac file to wave
      if b['prefix'] == None:
        flacd = ['flac','-f','-d',tr['file'],'--output-name={}'.format(wav_format.format(tr['disc'],tr['track']))]
      else:
        flacd = ['flac','-f','-d','/'.join([b['prefix'],tr['file']]),'--output-name={}'.format(wav_format.format(tr['disc'],tr['track']))]
      cmds.extend([flacd])
      temp_files.extend([wav_format.format(tr['disc'],tr['track'])])

      # Step 2a: Encode the wave to MP3
      if codec=='mp3':
        lame=['lame','-m','j']
        if mode=="cbr":
          lame.extend(['-b',mp3_cbr_bitrate])
        if mode=="vbr":
          lame.extend(['-V',str(mp3_vbr_quality)])
        lame.extend(['-q','0',wav_format.format(tr['disc'],tr['track']),mp3_format.format(tr['disc'],tr['track']),
                     '--id3v2-only','--tt',tr['title'],
                     '--ta',tr['artist'],
                     '--tl',b['album_title'],
                     '--tv','TPE2={}'.format(b['artist']),
                     '--ty','{}'.format(b['year']),
                     '--tn','{}/{}'.format(tr['track'],numtracks),
                     '--tv','TPOS={}/{}'.format(di,max(b['discs'])),
                     '--tv','TCON={}'.format(b['genre'])])
        if b['compilation']:
          lame.extend(['--tv','TCMP=1'])
        lame.extend(['--tc','{} {}'.format(b['label'],b['catalog'])])
        lame.extend(['--tv','TPUB={}'.format(b['label'])])
        if b['coverart'] != None:
          if b['prefix'] == None:
            lame.extend(['--ti',b['coverart']])
          else:
            lame.extend(['--ti','/'.join([b['prefix'],b['coverart']])])
        cmds.extend([lame])
      if codec=='aac':
        ffmpeg=['ffmpeg','-i',wav_format.format(tr['disc'],tr['track']),'-acodec','libfdk_aac']
        if mode=="cbr":
          ffmpeg.extend(['-b:a','{}k'.format(aac_cbr_bitrate)])
        if mode=="vbr":
          ffmpeg.extend(['-vbr',aac_vbr_quality])
        ffmpeg.extend(['-f','mp4',m4a_format.format(tr['disc'],tr['track'])])
        mp4tags=['mp4tags','-song',tr['title'],'-artist',tr['artist'],
                 '-album',b['album_title'],
                 '-albumartist',b['artist'],
                 '-year','{}'.format(b['year']),
                 '-track',str(tr['track']),'-tracks',str(numtracks),
                 '-disk',str(di),'-disks',str(max(b['discs'])),
                 '-genre',b['genre']]
        if b['compilation']:
          mp4tags.extend(['-compilation','1']),
        mp4tags.extend(['-comment','{} {}'.format(b['label'],b['catalog'])])
        mp4tags.extend(['-tool','Fraunhofer FDK AAC {}'.format(libfdk_aac_version)])
        mp4tags.extend([m4a_format.format(tr['disc'],tr['track'])])
        cmds.extend([ffmpeg,mp4tags])

        if b['coverart'] != None:
          if b['prefix'] == None:
            mp4art=['mp4art','-z','--add',b['coverart']]
          else:
            mp4art=['mp4art','-z','--add','/'.join([b['prefix'],b['coverart']])]
          mp4art.extend([m4a_format.format(tr['disc'],tr['track'])])
          cmds.extend([mp4art])
    
# Test run - only show the constructed commands, but don't actually run anything.
if args.test:
  for cmd in cmds:
    print('{}{}{}'.format(bcolors.OKGREEN,cmd,bcolors.ENDC))

# Run the full job
elif args.run:

  # Run each of the constructed commands one by one
  for cmd in cmds:
    print('{}{}{}'.format(bcolors.OKGREEN,cmd,bcolors.ENDC))
    subprocess.run(cmd,check=True)

  # Delete temporary files
  if args.verbose:
    print("Cleaning up...")
  for i in temp_files:
    if args.verbose:
      print(i)
    Path(i).unlink(missing_ok=False)
