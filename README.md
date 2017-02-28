# brick_in_the_wall

This requires a PostGIS database with a table for the border in an equidistant projection and a table, derived from that same border line, representing border 
that is fenced. Neither is included in this repo, so this is useful mostly as an example of how to go from PostGIS to a midi file.

The DB name and username are kept in a separate file called local_settings.py, which for security reasons is also not included in this repo. Just create your own with your own DB info.
