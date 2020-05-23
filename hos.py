#!/bin/env python3

import re
import json
import datetime
import math
from pathlib import Path

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
#print "Encoding: LAME MP3 " + _encoding_
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

# Output JSON for debug purposes
with open('debug.json', 'w') as debug:
#  debug.writelines(json.dumps(program['albums'],indent=2))
  debug.writelines(json.dumps(tracks,indent=2))
