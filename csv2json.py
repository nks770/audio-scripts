#!/bin/env python3

# csv2json.py
#
# This script is for preparing the metadata.json file which is needed for processing

import argparse
import csv
import json
from pathlib import Path


# Parse arguments
parser = argparse.ArgumentParser(description='Convert CSV metadata into JSON.')
parser.add_argument('albumdata',metavar='albumdata',nargs='*',default='',
                    help='CSV file(s) with album metadata.')
args=parser.parse_args()

print('#'*34)
print('# CSV to JSON Metadata Converter #')
print('#'*34)
print()

def ingestCSV(csvfile,index):
  print('Processing {}...'.format(csvfile))
  
  albumraw = []
  try:
    #with open(csvfile) as csvalbum:
    with open(csvfile,encoding='windows-1252') as csvalbum:
      albumfile = csv.reader(csvalbum, delimiter=',')
      for row in albumfile:
        albumraw.extend([row])
  except UnicodeDecodeError:
    with open(csvfile,encoding='ISO-8859-1') as csvalbum:
      albumfile = csv.reader(csvalbum, delimiter=',')
      for row in albumfile:
        albumraw.extend([row])
  
  current = {'index':index}
  tracks = []
  reading_tracklist = False
  ext_properties = []
  
  for e in albumraw:
    if reading_tracklist:
      ct={'disc':int(e[0]),'track':int(e[1]),'artist':e[2],'title':e[3],'file':e[4]}
      for i,p in enumerate(ext_properties):
        if e[5+i] != '':
          if p in ('start','end'):
            ct[p] = float(e[5+i])
          else:
            ct[p] = e[5+i]
      tracks.extend([ct])
    else:
      if e[0] == 'disc' and e[1] == 'track':
        reading_tracklist = True
        for i in range(len(e)-5):
          if e[5+i] != '':
            ext_properties.extend([e[5+i]])
      if e[0] in ('prefix','artist','title','edition','date','genre','label','barcode','catalog','coverart','source','torrent','url'):
        current[e[0]] = e[1]
        if e[1] == '':
          current[e[0]] = None
      if e[0] == 'year':
        current['year'] = int(e[1])
      if e[0] in ('compilation','original','optimized','default'):
        current[e[0]] = e[1] == 'true'
      if e[0] == 'cuesheet':
        if e[1] == 'disc':
          current['cuesheets'] = []
        else:
          current['cuesheets'].extend([{'disc':int(e[1]),'file':e[2]}])
      if e[0] == 'log':
        if e[1] == 'rip_date':
          current['logs'] = []
        else:
          current['logs'].extend([{'file':e[4],'disc':int(e[6]),'tool':e[2],'rip_date':e[1],'range_rip':e[3]=='true','score':int(e[5])}])
  current['tracks'] = tracks
  return current


metadata = [{'index':-1,'default':[],'original':[],'optimized':[]}]
counter = 0
for infile in args.albumdata:
  mdata = ingestCSV(infile,counter)
  for tag in ('default','original','optimized'):
    if mdata[tag]:
      metadata[[i for i, x in enumerate(metadata) if x['index'] == -1][0]][tag].extend([counter])
  metadata.extend([mdata])
  counter = counter + 1


# QC Checks
for j in metadata:
  if j['index'] >= 0:
    if j['edition'] == None:
      print('{}'.format(j['title']))
    else:
      print('{} [{}]'.format(j['title'],j['edition']))

    # Log files
    if j['logs'] != None:
      for log in j['logs']:
        if j['prefix'] == None:
          f = log['file']
        else:
          f = '/'.join([j['prefix'],log['file']])
        if Path(f).is_file():
          print('  Found log file {}'.format(f))
        else:
          raise Exception('Could not find {}'.format(f))

    # Cue sheets
    if j['cuesheets'] != None:
      for cue in j['cuesheets']:
        if j['prefix'] == None:
          f = cue['file']
        else:
          f = '/'.join([j['prefix'],cue['file']])
        if Path(f).is_file():
          print('  Found cue sheet {}'.format(f))
        else:
          raise Exception('Could not find {}'.format(f))

    # Torrent file
    if j['torrent'] != None:
      if j['prefix'] == None:
        f = j['torrent']
      else:
        f = '/'.join([j['prefix'],j['torrent']])
      if Path(f).is_file():
        print('  Found torrent file {}'.format(f))
      else:
        raise Exception('Could not find {}'.format(f))

    # Cover art
    if j['coverart'] != None:
      if j['prefix'] == None:
        f = j['coverart']
      else:
        f = '/'.join([j['prefix'],j['coverart']])
      if Path(f).is_file():
        print('  Found cover art image {}'.format(f))
      else:
        raise Exception('Could not find {}'.format(f))

    # Audio tracks
    for tt in j['tracks']:
      if j['prefix'] == None:
        f = tt['file']
      else:
        f = '/'.join([j['prefix'],tt['file']])
      if Path(f).is_file():
        print('  TRACK {:2d} {}'.format(tt['track'],f))
      else:
        raise Exception('Could not find {}'.format(f))

    # Nullify cuesheets and logs lists if there are none
    #if len(j['cuesheets']) == 0:
    #  j['cuesheets'] = None
    #if len(j['logs']) == 0:
    #  j['logs'] = None

# Output Metadata JSON
with open('metadata.json','w') as outjson:
  json.dump(metadata,outjson,indent=2)

