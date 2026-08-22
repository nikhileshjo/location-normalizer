import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ResourceClosedError
import pandas as pd
import hashlib
from fuzzywuzzy import fuzz

from dotenv import load_dotenv

load_dotenv()
CSV_LOCATION = os.getenv("CSV_LOCATION")
SCHEMA_LOCATION = os.getenv("SCHEMA_LOCATION")
DB_LOCATION = os.getenv("DB_LOCATION")
PROPERTY_FILE_LOCATION = os.getenv("PROPERTY_FILE_LOCATION")

PROPERTIES = {}
with open(PROPERTY_FILE_LOCATION, "r") as prop_file:
    for line in prop_file:
        key, value = line.split("=")
        if key == "DDL_ORDER":
            PROPERTIES[key] = [val.strip() for val in value.split(",")]
        else:
            PROPERTIES[key] = value
                        

class Housekeeping():
    def _query_exec(self, query:str, data: list[dict] = None) -> list[tuple]:
        """
            This is a helper function that executes a query and returns the result
                Input: requeries 1 input string, optional data list incase you're query has some had hard coded values
                Output: List of tuples, where each tuple represents a row
        """
        try:
            if os.path.isfile(DB_LOCATION):
                engine = create_engine(f"sqlite+pysqlite:///{DB_LOCATION}")
                with engine.connect() as conn:
                    if data!=None:
                        result = conn.execute(text(query), data)
                        return []
                    else:
                        result = conn.execute(text(query))
                        return result.all()
            else:
                raise FileNotFoundError(f"{DB_LOCATION} not found")
        except ResourceClosedError:
            return []
        except:
            raise
        

    def _file2sqlalchemy(self, file_path: str) -> tuple[list ,list[dict]]:
        """
            This is a helper function that will take any pandas dataframe and convert it
            to sqlalchemy consumable data
                Input: file path as string
                Output: List containing dictionary where each dictionary is a row
                    and each dictionary is a KV pair of column: value of the column in that row
        """ 
        with open(file_path, "r") as f:
            header = f.readline()
            columns = [col.strip() for col in header.split(",")]

            data_list = []
            for rows in f:
                tmp_dict = {}
                row_vals = [val.strip() for val in rows.split(",")]
                for col, val in zip(columns, row_vals):
                    tmp_dict[col] = val
                data_list.append(tmp_dict)

        return (columns, data_list)

    def _create_db(self) -> None:
        """
            This is a helper function that creates the db from the csv file
                Input: no inputs required
                Output: None 
        """
        # ALIAS_COLUMN_LIST = ["location_code", "alias"]
        # LOCATION_COLUMN_LIST = ["location_code", "country", "state", "city"]
        if os.path.isfile(DB_LOCATION):
            os.remove(DB_LOCATION)
        try:
            db_dir_folders = DB_LOCATION.split("/")[:-1]
            db_dir = "/".join(db_dir_folders)
            os.makedirs(db_dir, exist_ok=True)
            
            # create database
            engine = create_engine(f"sqlite+pysqlite:///{DB_LOCATION}")
            # with engine.connect() as conn:
            #     conn.execute(text("select 'hello world'"))


            for table in PROPERTIES["DDL_ORDER"]:
                # table = table1, table2, table3....
                # create schema
                with open(os.path.join(SCHEMA_LOCATION, f"{table}.sql")) as ddl:
                    with engine.connect() as conn:
                        conn.execute(text(ddl.read()))
                        conn.commit()
                    # self._query_exec(ddl.read())
                # load table
                columns, data = self._file2sqlalchemy(os.path.join(CSV_LOCATION, f"{table}.csv"))
                if len(data) > 0:
                    table_columns = ",".join(columns)
                    table_columns_val_args = ",".join([ f":{col}" for col in columns ])
                    with engine.connect() as conn:
                        conn.execute(text(f"INSERT INTO {table} ({table_columns}) VALUES ({table_columns_val_args})"), data)
                        conn.commit()
                    # self._query_exec(f"INSERT INTO {table} ({table_columns}) VALUES ({table_columns_val_args})", data)
            # store hash in database
            hash_table_ddl = open(os.path.join(SCHEMA_LOCATION, f"{PROPERTIES["HASH_DDL"]}.sql"), "r").read()
            with engine.connect() as conn:
                conn.execute(text(hash_table_ddl))
                conn.commit()
            # self._query_exec(hash_table_ddl)
            hash_data = []
            for file in PROPERTIES["DDL_ORDER"]:
                tmp_dict = {}
                with open(os.path.join(CSV_LOCATION, f"{file}.csv"), "rb") as f:
                    hash_digest = hashlib.file_digest(f, "sha256")
                file_hash = hash_digest.hexdigest() # will hold file hash
                tmp_dict["file_name"] = file
                tmp_dict["hash_value"] = file_hash
                hash_data.append(tmp_dict)
            with engine.connect() as conn:
                conn.execute(text(f"INSERT INTO {PROPERTIES["HASH_DDL"]} (file_name, hash_value) VALUES (:file_name, :hash_value)"), hash_data)
                conn.commit()
            # self._query_exec(f"INSERT INTO {PROPERTIES["HASH_DDL"]} (file_name, hash_value) VALUES (:file_name, :hash_value)", hash_data)
        except PermissionError:
            raise
        except:
            raise

    def initiate_db(self):
        """
        Performs necessary checks and sets up the database required for the app to function
            Inputs: No inputs required
            Output: None
        """
        if os.path.isfile(DB_LOCATION):
            raw_hashes = {}
            db_hashes = {}
            try:
                engine = create_engine(f"sqlite+pysqlite:///{DB_LOCATION}")
                for file in PROPERTIES["DDL_ORDER"]:
                    csv_file = os.path.join(CSV_LOCATION, f"{file}.csv")
                    if not os.path.isfile(csv_file):
                        raise FileNotFoundError(f"File not found:{csv_file}")
                    else:
                        with open(csv_file, "rb") as f:
                            hash_digest = hashlib.file_digest(f, "sha256")
                        raw_hashes[file] = hash_digest.hexdigest() # will hold file hash
                with engine.connect() as conn:
                    hash_vals = conn.execute(text("SELECT file_name, hash_value FROM csv_hash")).all()
                if len(hash_vals) < 2:
                    self._create_db()
                    return None
                for file, hash in hash_vals:
                    db_hashes[file] = hash
                if db_hashes != raw_hashes:
                    self._create_db()
            except:
                self._create_db()
                return None         
        else:
            self._create_db()

    def shallow_sync_check(self) -> bool:
        """
            This function will perform a sync check by matching hash stored in the database and the hash of the files
            Assumtion: This function assumes that all files exists, so it will break if a file doesn't exist
                Input: No inputs required
                Output: Boolean, True when in Sync and False otherwise
        """
        engine = create_engine(f"sqlite+pysqlite:///{DB_LOCATION}")
        raw_hashes = {}
        db_hashes = {}
        for file in PROPERTIES["DDL_ORDER"]:
            csv_file = os.path.join(CSV_LOCATION, f"{file}.csv")
            if not os.path.isfile(csv_file):
                raise FileNotFoundError(f"File not found:{csv_file}")
            else:
                with open(csv_file, "rb") as f:
                    hash_digest = hashlib.file_digest(f, "sha256")
                raw_hashes[file] = hash_digest.hexdigest() # will hold file hash
        with engine.connect() as conn:
            hash_vals = conn.execute(text("SELECT file_name, hash_value FROM csv_hash")).all()
            if len(hash_vals) < 2:
                return False
            for file, hash in hash_vals:
                db_hashes[file] = hash
            if db_hashes != raw_hashes:
                return False
            else:
                return True

    def deep_sync_check(self) -> bool:
        """
            This function will create a temperory table in the data base
            and perform a row wise check against the original tables.
            CAUTION: THIS IS AN EXPENSIVE CHECK
                Input: No input required
                Output: Boolean
        """
        engine = create_engine(f"sqlite+pysqlite:///{DB_LOCATION}")
        for table in PROPERTIES["DDL_ORDER"]:
            # table = table1, table2...
            create_query = f"""CREATE TEMP TABLE temp_{table} AS
                        SELECT * FROM {table}
                        WHERE 0"""
            # load table
            columns, data = self._file2sqlalchemy(os.path.join(CSV_LOCATION, f"{table}.csv"))
            if len(data) > 0:
                table_columns = ",".join(columns)
                table_columns_val_args = ",".join([ f":{col}" for col in columns ])
            insert_query = f"INSERT INTO temp_{table} ({table_columns}) VALUES ({table_columns_val_args})"
            join_condition = " AND ".join([f"temp_{table}.{col}={table}.{col}" for col in columns])
            compare_query = f"""SELECT
                                    t1.join_count=t2.table_count
                                FROM
                                    (
                                        SELECT
                                            COUNT(*) AS join_count
                                        FROM
                                            temp_{table}
                                            INNER JOIN {table} ON ({join_condition})
                                    ) t1,
                                    (
                                        SELECT
                                            COUNT(*) AS table_count
                                        FROM
                                            {table}
                                    ) t2"""
            with engine.connect() as conn:
                conn.execute(text(create_query))
                conn.execute(text(insert_query), data)
                is_synced = conn.execute(text(compare_query)).all()[0][0]
                conn.commit()

            if is_synced != 1:
                return is_synced==1

        return is_synced==1

    def csv_to_db_sync(self):
        """
            This will make a copy of existing database (if any).
            Then create a new database from the csv
                Input: no inputs required
                Output: None
        """
        if os.path.isfile(DB_LOCATION):
            os.rename(DB_LOCATION, f"{DB_LOCATION}_copy")
        self._create_db()

    def db_to_csv_sync(self, confirm=False):
        """
            This will make a copy of existing CSV (if any).
            Then create a new CSV from the database
            CAUTION: THIS MEANS YOU MAKE THE DATABASE AS SOURCE OF TRUTH
                Input: optionl boolean input, where passing True means the function will execute
                    False (default) means it won't.
                Output: None
        """
        if not confirm:
            return None
        engine = create_engine(f"sqlite+pysqlite:///{DB_LOCATION}")
        for table in PROPERTIES["DDL_ORDER"]:
            csv_file = os.path.join(CSV_LOCATION, f"{table}.csv")
            if os.path.isfile(csv_file):
                os.rename(csv_file, f"{csv_file}_copy")
            columns = [] # will hold column names
            with engine.connect() as conn:
                cursor = conn.execute(text(f"SELECT * FROM {table}"))
                conn.commit()
            columns = tuple(cursor.keys())
            output = cursor.all()
            df_dict = {}
            for row in output:
                # row = (val1, val2, val3...), (val4, val5, val6...)...
                for col, val in zip(columns, row):
                    if col in df_dict:
                        df_dict[col].append(val)
                    else:
                        df_dict[col] = [val]

            df = pd.DataFrame(df_dict)
            df.to_csv(csv_file, header=True, index=False)
            

class LocationService():
    def get_location(self, alias: str) -> tuple[str]:
        """
            This function takes a name and returns a tuple of normalized location
            The output is in this format: (country,state,city)
                Input: place name (string)
                Output: tuple of strings (country,state,city)
        """
        alias = alias.lower()
        engine = create_engine(f"sqlite+pysqlite:///{DB_LOCATION}")
        with engine.connect() as conn:
            query = "SELECT country, state, city FROM location l INNER JOIN alias a ON (a.location_code = l.location_code) WHERE LOWER(a.alias) = :alias"
            result = conn.execute(text(query), [{"alias" : alias}]).all()
        if len(result) < 1:
            filter_dict = {}
            conditions = []
            for ind in range(len(alias)):
                filter_dict[f"alias_{ind}"] = f"{alias[: ind + 1]}%"
                conditions.append(f"a.alias LIKE :alias_{ind}")
            conditions_str = " OR ".join(conditions)
            query = f"SELECT a.alias FROM alias a WHERE {conditions_str}"
            with engine.connect() as conn:
                candidate_alias = conn.execute(text(query), [filter_dict]).all()
            if len(candidate_alias) < 1:
                return ()

            max_ratio = 0
            match_candidate = None
            for candidate in candidate_alias:
                tmp_ratio = fuzz.ratio(alias, candidate[0])
                if tmp_ratio > max_ratio:
                    max_ratio = tmp_ratio
                    match_candidate = candidate[0].lower()
            if max_ratio == 0:
                return ()
            else:
                with engine.connect() as conn:
                    query = "SELECT country, state, city FROM location l INNER JOIN alias a ON (a.location_code = l.location_code) WHERE LOWER(a.alias) = :alias"
                    result = conn.execute(text(query), [{"alias" : match_candidate}]).all()
                return result
        else:
            return result[0]


    def set_alias(self, alias:str, loc_dict:dict):
        pass

    def add_location(self, alias:str, loc_dict:dict):
        pass

    def remove_location(self, loc_dict:dict):
        pass

    def remove_alias(self, alias:str, loc_dict:dict):
        pass

    def bulk_load(self, file_location, mode):
        pass

    def search_location(self, search_key):
        pass