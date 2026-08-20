# location-normalizer
This is a location API, that will accept a location name and normalize it. Example, an input like Bombay and Mumbai will both produce Mumbai as the output.

# Services offered by core file
This is regarding the file `scripts/services.py`, we'll learn what it can do
## Housekeeping services
Housekeeping services include:
* initiation of database: At all times, we consider the CSV files placed in `data/CSV` as the source of truth. So, when a database is initiated, we look at the files and compare it to the database placed `data/sqlite`, if we find any discrepencies, we purge the existing database and recreate the new one from scratch.
* Shallow Sync check: This is a quick but not a very reliable check to see if our database is in sync with the CSV files. It simply compares the hash values of the CSV against the hash values stored in the database of the files.
* Deep sync check: This is a more expensive check where the csv is uploaded to the database as a temperory table and a join is created between the tables, if the join count matches the original table count, it's the data is considered synced.
* there are 2 syncs provided too, make a copy of existing database and create a new database from the existing CSV, this is useful in the even something might have gone wrong somewhere and the table is not synced with the CSV or you can do the other way in case you consider the database as a more reliable source.