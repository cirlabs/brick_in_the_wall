# import csv
import psycopg2
import math
from math import floor
from datetime import datetime
from miditime.miditime import MIDITime

from lib.fence_segment_notes import FENCE_SEGMENT_NOTES

import local_settings


class postgis_to_midi(object):
    ''' For each segment of fence, need the distance from the start along the border line, and the length of the segment. '''

    epoch = datetime(2008, 1, 1)  # Not actually necessary, but optional to specify your own
    mymidi = None

    tempo = 120

    min_attack = 30
    max_attack = 255

    seconds_per_mile = 0.1

    base_octave = 3
    octave_range = 5

    conn = False
    cursor = False

    # If needed, insert equidistant project into spatial_ref_sys table of PostGIS
    # """INSERT into spatial_ref_sys (srid, auth_name, auth_srid, proj4text, srtext) values ( 102005, 'esri', 102005, '+proj=eqdc +lat_0=0 +lon_0=0 +lat_1=33 +lat_2=45 +x_0=0 +y_0=0 +ellps=GRS80 +datum=NAD83 +units=m +no_defs ', 'PROJCS["USA_Contiguous_Equidistant_Conic",GEOGCS["GCS_North_American_1983",DATUM["North_American_Datum_1983",SPHEROID["GRS_1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]],PROJECTION["Equidistant_Conic"],PARAMETER["False_Easting",0],PARAMETER["False_Northing",0],PARAMETER["Central_Meridian",-96],PARAMETER["Standard_Parallel_1",33],PARAMETER["Standard_Parallel_2",45],PARAMETER["Latitude_Of_Origin",39],UNIT["Meter",1],AUTHORITY["EPSG","102005"]]');"""

    def __init__(self):
        self.conn = self.get_connection()
        if self.conn:
            segment_note_info = self.extract_from_spatial_data()
            self.list_to_miditime(segment_note_info, 'brick_in_the_wall_ped_vehicle.mid', 3)


        self.conn.close()

    def extract_from_spatial_data(self):
        note_info = []
        self.cursor = self.conn.cursor()
        seg_data = self.get_seg_start_end()
        for segment in seg_data:
            print segment
            start_pct = self.get_distance_from_start(segment)
            note_info.append({'start_pct': start_pct, 'length_m': segment[2], 'type': segment[3]})
        return sorted(note_info, key=lambda k: k['start_pct'])  # Sort by start_pct just in case the segments are out of order

    def get_connection(self):
        try:
            conn = psycopg2.connect("dbname='%s' user='%s' host=''" % (local_settings.DB_NAME, local_settings.DB_USER,))
            return conn
        except:
            print "I am unable to connect to the database"
            return False

    def border_full_length(self):
        self.cursor.execute("""
                SELECT ST_Length(geom) as length
                FROM us_mexico_boundary_equidistant_landonly;
            """)
        return self.cursor.fetchone()[0]

    def get_seg_start_end(self):
        ''' Get component linestrings from original multilinestring, extract start and end points, then length '''
        self.cursor.execute("""
                SELECT ST_AsText(ST_StartPoint(ST_LineMerge(geom))) AS start_point,
                ST_AsText(ST_EndPoint(ST_LineMerge(geom))) AS end_point,
                ST_Length(geom) AS seg_length,
                gen_type
                FROM border_that_is_fenced_equidistant_single;
            """)
        return self.cursor.fetchall()

    def get_distance_from_start(self, segment):
        ''' Find the distance from the start of the border line for the starting point of each segment. Determine starting point by which endpoint is a lower percentage along the line. NOTE: In this case had to reverse border to make it west-east.'''
        self.cursor.execute("""
            SELECT ST_Line_Locate_Point(ST_LineMerge(ST_Reverse(geom)), ST_GeomFromText('%s', 102005)) AS start_pct,
            ST_Line_Locate_Point(ST_LineMerge(ST_Reverse(geom)), ST_GeomFromText('%s', 102005)) AS end_pct
            FROM us_mexico_boundary_equidistant_landonly;
        """ % (segment[0], segment[1]))
        return min(self.cursor.fetchone())

    def just_one_note(self, start_beat, num_beats, pitch, miditime_instance, octave):
        channel = 0
        midi_pitch = miditime_instance.note_to_midi_pitch(pitch)
        print list([[start_beat, midi_pitch, 100, num_beats], channel])
        return [[[start_beat, midi_pitch, 100, num_beats], channel]]

    def bigger_boat(self, start_beat, num_beats, miditime_instance, octave):
        ''' This is vestigial to the final piece -- we went with the one-note option, but might be fun to play with. May need cleaning up, so use at your own risk. '''
        rest_between_loops = 0.5
        note_series = FENCE_SEGMENT_NOTES
        looped_note_series = list(note_series)

        # figure out how many times you'll need to repeat sequence in case there's not enough notes to fill space.
        # Get last beat of song plus duration
        last_jaws_beat = note_series[-1][0]
        if num_beats >= last_jaws_beat:
            num_reps = math.ceil(num_beats / last_jaws_beat)
            print num_reps
            rep = 1
            while rep < num_reps:
                looped_note_series.extend([[n[0] + (rep*last_jaws_beat) + (rep*rest_between_loops), n[1], n[2], n[3]] for n in list(note_series)])
                rep += 1
            print looped_note_series

        notes = []
        for r in looped_note_series:
            if r[0] <= num_beats:
                try:
                    octavated_pitch = '%s%s' % (r[1], octave + r[4],)
                except:
                    octavated_pitch = '%s%s' % (r[1], octave,)
                try:
                    channel = r[5]
                except:
                    channel = 0
                adjusted_beat = r[0] + start_beat
                midi_pitch = miditime_instance.note_to_midi_pitch(octavated_pitch)
                notes.append([[adjusted_beat, midi_pitch, r[2], r[3]], channel])

        print notes
        return notes

    def bigger_boat_2(self, start_beat, next_note_index, num_beats, miditime_instance, octave):
        ''' This is vestigial to the final piece -- we went with the one-note option, but might be fun to play with. May need cleaning up, so use at your own risk. Play through the song, x notes at a time (rather than starting over.)'''

        # Make list of possible beats
        beats_list = sorted(list(set([j[0] for j in FENCE_SEGMENT_NOTES])))
        # print beats_list

        notes = []
        print next_note_index, len(beats_list)
        if next_note_index >= len(beats_list):
            next_note_index = 0
        print FENCE_SEGMENT_NOTES[next_note_index]
        first_jaws_beat = beats_list[next_note_index]
        adjusted_start_beat = start_beat - first_jaws_beat
        print adjusted_start_beat
        print 'First jaws beat: %s   adjusted_start_beat: %s   num_beats: %s' % (first_jaws_beat, adjusted_start_beat, num_beats)
        for note_index, r in enumerate(FENCE_SEGMENT_NOTES):
            if r[0] >= first_jaws_beat and r[0] <= first_jaws_beat + num_beats:
                try:
                    octavated_pitch = '%s%s' % (r[1], octave + r[4],)
                except:
                    octavated_pitch = '%s%s' % (r[1], octave,)
                try:
                    channel = r[5]
                except:
                    channel = 0
                adjusted_beat = r[0] + start_beat
                midi_pitch = miditime_instance.note_to_midi_pitch(octavated_pitch)
                notes.append([[adjusted_beat, midi_pitch, r[2], r[3]], channel])
                next_note_index = beats_list.index(r[0]) + 1
        print notes

        return (notes, next_note_index)

    def beat_meters(self, num_meters):
        beats_per_second = self.tempo / 60.0
        beats_per_meter = self.seconds_per_mile / 1609.34 * beats_per_second
        return round(beats_per_meter * num_meters, 2)

    def nearest_nth_beat(self, float_beat, round_to=16):
        ''' Round to a fraction besides 10ths '''
        # Get floor to handle numbers greater than 1
        whole_remainder = floor(float_beat)
        decimal_part = float_beat - whole_remainder
        nths = (round_to * decimal_part * 10) / 10
        nearest_nth_in_tenths = round(nths) / round_to
        return whole_remainder + nearest_nth_in_tenths

    def list_to_miditime(self, raw_data, outfile, octave):
        mymidi = MIDITime(self.tempo, outfile, self.seconds_per_mile, self.base_octave, self.octave_range, self.epoch)

        note_list = []
        start_note_index = 0

        border_full_length = self.border_full_length()
        print border_full_length

        for r in raw_data:
            segment_start_meters = r['start_pct'] * border_full_length

            segment_start_beat = self.nearest_nth_beat(self.beat_meters(segment_start_meters), 16)
            segment_end_beat = self.nearest_nth_beat(self.beat_meters(segment_start_meters + r['length_m']), 16)
            duration_in_beats = segment_end_beat - segment_start_beat
            if duration_in_beats == 0:
                duration_in_beats = float(1)/float(16)  # Minimum duration of 1/16
            if r['type'] == 'pedestrian':
                pitch = 'E5'
            elif r['type'] == 'vehicle':
                pitch = 'F6'

            # I've left a few other options commented out here. The live version just plays one long note for the duration of the fence segment, but the othres play through a melody. We ended up doing all of our melodic stuff in Live once we had a raw midi file.
            # new_notes, start_note_index = self.bigger_boat_2(segment_start_beat, start_note_index, duration_in_beats, mymidi, octave)
            # new_notes = self.bigger_boat(segment_start_beat, duration_in_beats, mymidi, octave)
            new_notes = self.just_one_note(segment_start_beat, duration_in_beats, pitch, mymidi, octave)
            note_list = note_list + new_notes

        # Add a track with those notes
        mymidi.add_track(note_list)

        # Output the .mid file
        mymidi.save_midi()

if __name__ == "__main__":
    mymidi = postgis_to_midi()
