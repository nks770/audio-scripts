#!/bin/env python3

# hos.py
#
# This script is for processing downloaded stream data for
# Hearts of Space (https://www.hos.com)

import argparse
import re
import json
import datetime
import math
from pathlib import Path

# Parse arguments
parser = argparse.ArgumentParser(description='Process a Hearts of Space audio stream.')
parser.add_argument('-c','--codec',metavar='CODEC',dest='codec',
                    default='mp3',choices={'mp3','aac'},
                    help='Output codec to use for transcoding. (Default: mp3)')
parser.add_argument('-b','--bitrate',metavar='BITRATE',dest='bitrate',
                    help='Specify the output bitrate (CBR) or quality (VBR).')
parser.add_argument('-r','--run',action='store_true',dest='run',
                    help='Actually run the transcode.')
args=parser.parse_args()

# Validate requested bitrate
mp3_cbr_bitrates = ['32', '40', '48', '56', '64', '80', '96', '112', '128', '160', '192', '224', '256', '320']
aac_vbr_bitrates = ['1', '2', '3', '4', '5']
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
  encoding = 'libfdk_aac AAC CBR {}kbps'.format(aac_cbr_bitrate)
  if aac_cbr_bitrate < 112 or aac_cbr_bitrate > 320:
    raise argparse.ArgumentTypeError("Invalid CBR bitrate '{}'. AAC CBR bitrate must be between 112 and 320. Higher is better.".format(bitrate))
elif codec == 'aac' and mode == 'vbr':
  if len(bitrate)>1:
    aac_vbr_quality = bitrate[1:]
  else:
    aac_vbr_quality = ''
  encoding = 'libfdk_aac AAC VBR {}'.format(aac_vbr_quality)
  if not aac_vbr_quality in aac_vbr_bitrates:
    raise argparse.ArgumentTypeError("Invalid VBR quality '{}'. Valid AAC VBR qualities are {}. Higher is better.".format(bitrate,aac_vbr_bitrates))
else:
  raise Exception("Unknown codec/mode {}/{}.".format(codec,mode))
  

# Read play JSON, get program number
with open('api.hos.com/api/v1/player/play','r') as f:
  play = json.load(f)

pgm=re.split(r'(.+pgm)(\d{4})(.*)',play['signedUrl'])[2]

# Read program metadata JSON
with open('api.hos.com/api/v1/programs/{}'.format(pgm),'r') as f:
  program = json.load(f)

# Read program master M3U playlist
with open('api.hos.com/vo-intro/pgm{}.m3u8'.format(pgm),'r') as f:
  for x in f:
    if "256k" in x:
      m3u_url=x.rstrip()

# Read 256k M3U playlist
m3u = []
with open('api.hos.com/vo-intro/{}'.format(m3u_url),'r') as f:
  for x in f:
    if '.ts' in x:
      m3u.extend([x.rstrip()])

# Validate to make sure no TS files are missing from the sequence
# This should never happen, but just want to make sure
for i in range(0,len(m3u)):
  if "s{:05}.ts".format(i) != m3u[i]:
    raise Exception("File s{:05}.ts is missing from the playlist sequence.".format(i))

# Check to make sure we have all the TS files.
vo_intro = [str(x) for x in list(Path('api.hos.com/vo-intro').rglob('*')) if x.is_file()]

vo_intro_chk = ['api.hos.com/vo-intro/pgm{}.m3u8'.format(pgm),
                'api.hos.com/vo-intro/{}'.format(m3u_url)]
vo_intro_chk.extend(['api.hos.com/vo-intro/pgm{}/256k/{}'.format(pgm,ts) for ts in m3u])

for x in vo_intro_chk:
  if not x in vo_intro:
    raise Exception("{} is missing.".format(x))
for x in vo_intro:
  if not x in vo_intro_chk:
    print("WARNING: Extra file {} is not needed.".format(x))

# Get Album IDs
album_ids = {album['id'] for album in program['albums']}

# Get list of album artwork files
images_repo = [str(x) for x in list(Path('api.hos.com/api/v1/images-repo').rglob('*')) if x.is_file()]

# Check to make sure we have all the files, and that we don't have any extraneous ones
images_repo_chk = []
for r in (80, 150):
  images_repo_chk.extend(['api.hos.com/api/v1/images-repo/albums/w/{}/{}.jpg'.format(r,x) for x in album_ids])
for r in (180, 550, 1024):
  images_repo_chk.extend(['api.hos.com/api/v1/images-repo/programs/w/{}/{}.jpg'.format(r,pgm)])

for x in images_repo_chk:
  if not x in images_repo:
    raise Exception("{} is missing.".format(x))
for x in images_repo:
  if not x in images_repo_chk:
    print("WARNING: Extra file {} is not needed.".format(x))

# Extract track list, preserve album ID from parent object
tracks = []
for album in program['albums']:
  for track in album['tracks']:
    track.update({'album_id':album['id']})
  tracks.extend(album['tracks'])

# For each track, combine artist lists into single artist value
for track in tracks:
  track.update({'artist':' & '.join([artist['name'] for artist in track['artists']]).title()})

# Ensure tracks are sorted by startPositionInStream
# Check to make sure there are no gaps unaccounted for
tracks.sort(key=lambda x: x.get('startPositionInStream'))
for i in range(len(tracks)):
  if i>0:
    if tracks[i]['startPositionInStream'] != ( tracks[i-1]['startPositionInStream'] + tracks[i-1]['duration'] ):
      raise Exception("Illegal gap in metadata. Track {} ends at {:,} and track {} starts at {:,}.".format(
        i-1,( tracks[i-1]['startPositionInStream'] + tracks[i-1]['duration'] ),
        i,tracks[i]['startPositionInStream']))

# List the tracks
print("############################################################")
print("##################### HEARTS OF SPACE ######################")
print("############################################################")
print('Program {}: "{}" ({})'.format(pgm,program['title'].title(),program['date']))
print('Genre: "{}"'.format(program['genres'][0]['name']))
print('Number of tracks: {}'.format(len(tracks)))
print('Encoding: {}'.format(encoding))
print("############################################################")
max_title=max(len(track['title']) for track in tracks)
max_artist=max(len(track['artist']) for track in tracks)
max_tid=math.floor(math.log10(len(tracks)))+1
track_format='{:'+str(max_tid)+'} {:'+str(max_artist)+'}  {:'+str(max_title)+'}  {}'

for i in range(len(tracks)):
  print(track_format.format(i+1,
                            tracks[i]['artist'],
                            tracks[i]['title'],
                            datetime.timedelta(seconds=tracks[i]['duration'])))
print("############################################################")
print("\n")

# Concatenate all the TS files together into one
if args.run:
  with open("pgm{}.ts".format(pgm),"wb") as out:
    for ts in m3u:
      with open('api.hos.com/vo-intro/pgm{}/256k/{}'.format(pgm,ts),'rb') as inp:
        out.write(inp.read())


#	_lamecmd_ = ['lame', '-m', 'j', _mode_flag_, _quality_, '-q', '0', _tempwav_, _tempmp3_, '--id3v2-only', '--tt', _track_[t], '--ta', _artist_[t], '--tl', _album_, '--tv', 'TPE2='+_albumartist_, '--ty', _year_, '--tn', str(t+1)+'/'+str(len(_track_))]
#	if _discnum_!="" and _disctot_!="":
#		_lamecmd_.extend(['--tv TPOS=1/1'])
#	if _genre_!="":
#		_lamecmd_.extend(['--tv', 'TCON='+_genre_])
#	if _compilation_flag_==1:
#		_lamecmd_.extend(['--tv', 'TCMP=1'])
#	if _image_!="":
#		_lamecmd_.extend(['--ti', _image_])

# Output JSON for debug purposes
with open('debug.json', 'w') as debug:
#  debug.writelines(json.dumps(program['albums'],indent=2))
  debug.writelines(json.dumps(tracks,indent=2))
