import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ResourceClosedError
import pandas as pd
import hashlib

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

    def deep_sync_check(self):
        pass

    def csv_to_db_sync(self):
        pass

    def db_to_csv_sync(self, confirm=False):
        pass

class LocationService():
    def get_location(self, alias):
        pass

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