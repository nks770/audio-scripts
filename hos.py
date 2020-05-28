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
import subprocess
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
parser.add_argument('-t','--test',action='store_true',dest='test',
                    help='Only show the constructed commands, do not execute anything.')
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

# Read play JSON, get program number
try:
  with open('api.hos.com/api/v1/player/play','r') as f:
    play = json.load(f)
  pgm1=re.split(r'(.+pgm)(\d{4})(.*)',play['signedUrl'])[2]
except:
  pgm1='0'

# Alternative method to get the program number, cross check
jsonfiles = [str(x) for x in list(Path('api.hos.com/api/v1/programs').rglob('*')) if x.is_file()]
if len(jsonfiles)>1:
  raise Exception('More than one file found under api.hos.com/api/v1/programs')
pgm2=re.split(r'(.*\/)(\d+)$',jsonfiles[0])[2]
if pgm1 != '0' and pgm1 != pgm2:
  raise Exception('Conflict in determining the progran number ({} vs {}).'.format(pgm1,pgm2))
pgm=pgm2

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
print('#'*79)
print('{0} HEARTS OF SPACE {0}'.format('#'*31))
print('#'*79)
print('Program {}: "{}" ({})'.format(pgm,program['title'].title(),program['date']))
print('Genre: "{}"'.format(program['genres'][0]['name']))
print('Number of tracks: {}'.format(len(tracks)))
print('Encoding: {}'.format(encoding))
print('#'*79)
max_title=max(len(track['title']) for track in tracks)
max_artist=max(len(track['artist']) for track in tracks)
max_tid=math.floor(math.log10(len(tracks)))+1
display_format='{:'+str(max_tid)+'} {:'+str(max_artist)+'}  {:'+str(max_title)+'}  {}'
wav_format='track{:0'+str(max_tid)+'}.wav'
mp3_format='track{:0'+str(max_tid)+'}.mp3'
m4a_format='track{:0'+str(max_tid)+'}.m4a'

for i in range(len(tracks)):
  print(display_format.format(i+1,
                            tracks[i]['artist'],
                            tracks[i]['title'],
                            datetime.timedelta(seconds=tracks[i]['duration'])))
print('#'*79)
print("\n")

cmds = []
cmds.extend([['ffmpeg','-i','pgm{}.ts'.format(pgm),'-acodec','pcm_s16le','pgm{}.wav'.format(pgm)]])
for i in range(len(tracks)):
  if i==0:
    cmds.extend([['ffmpeg','-i','pgm{}.wav'.format(pgm),
      '-af','atrim=end={}'.format(
      tracks[i]['startPositionInStream']+tracks[i]['duration']),
      wav_format.format(i+1)]])
  elif i<len(tracks)-1:
    cmds.extend([['ffmpeg','-i','pgm{}.wav'.format(pgm),
      '-af','atrim={}:{}'.format(
      tracks[i]['startPositionInStream'],
      tracks[i]['startPositionInStream']+tracks[i]['duration']),wav_format.format(i+1)]])
  else:
    cmds.extend([['ffmpeg','-i','pgm{}.wav'.format(pgm),
      '-af','atrim=start={}'.format(
      tracks[i]['startPositionInStream']),
      wav_format.format(i+1)]])

for i in range(len(tracks)):
  if codec=='mp3':
    lame=['lame','-m','j']
    if mode=="cbr":
      lame.extend(['-b',mp3_cbr_bitrate])
    if mode=="vbr":
      lame.extend(['-V',str(mp3_vbr_quality)])
    lame.extend(['-q','0',wav_format.format(i+1),mp3_format.format(i+1),
                 '--id3v2-only','--tt',tracks[i]['title'],'--ta',tracks[i]['artist'],
                 '--tl','HoS {}: {}'.format(pgm,program['title'].title()),
                 '--tv','TPE2=Hearts of Space','--ty',program['date'][:4],
                 '--tn','{}/{}'.format(i+1,len(tracks)),'--tv','TPOS=1/1',
                 '--tv','TCON={}'.format(program['genres'][0]['name']),'--tv','TCMP=1',
                 '--tc','Produced by {}'.format(program['producer']),
                 '--ti','api.hos.com/api/v1/images-repo/albums/w/150/{}.jpg'.format(tracks[i]['album_id'])])
    cmds.extend([lame])
  if codec=='aac':
    ffmpeg=['ffmpeg','-i',wav_format.format(i+1),'-acodec','libfdk_aac']
    if mode=="cbr":
      ffmpeg.extend(['-b:a','{}k'.format(aac_cbr_bitrate)])
    if mode=="vbr":
      ffmpeg.extend(['-vbr',aac_vbr_quality])
    ffmpeg.extend(['-f','mp4',m4a_format.format(i+1)])
    mp4tags=['mp4tags','-song',tracks[i]['title'],'-artist',tracks[i]['artist'],
             '-album','HoS {}: {}'.format(pgm,program['title'].title()),
             '-albumartist','Hearts of Space','-year',program['date'][:4],
             '-track',str(i+1),'-tracks',str(len(tracks)),'-disk','1','-disks','1',
             '-genre',program['genres'][0]['name'],'-compilation','1',
             '-comment','Produced by {}'.format(program['producer']),
             '-tool','Fraunhofer FDK AAC {}'.format(libfdk_aac_version)]
    mp4art=['mp4art','-z','--add','api.hos.com/api/v1/images-repo/albums/w/150/{}.jpg'.format(tracks[i]['album_id'])]
    mp4tags.extend([m4a_format.format(i+1)])
    mp4art.extend([m4a_format.format(i+1)])
    cmds.extend([ffmpeg,mp4tags,mp4art])

# Test run - only show the constructed commands, but don't actually run anything.
if args.test:
  for cmd in cmds:
    print('\033[92m{}\033[0m'.format(cmd))

# Run the full job
elif args.run:

  # Concatenate all the TS files together into one
  with open('pgm{}.ts'.format(pgm),'wb') as out:
    for ts in m3u:
      with open('api.hos.com/vo-intro/pgm{}/256k/{}'.format(pgm,ts),'rb') as inp:
        out.write(inp.read())

  # Run each of the constructed commands one by one
  for cmd in cmds:
    print('\033[92m{}\033[0m'.format(cmd))
    subprocess.run(cmd,check=True)

  # Delete temporary files
  print("Cleaning up...")
  Path('pgm{}.ts'.format(pgm)).unlink(missing_ok=False)
  Path('pgm{}.wav'.format(pgm)).unlink(missing_ok=False)
  for i in range(len(tracks)):
    Path(wav_format.format(i+1)).unlink(missing_ok=False)

