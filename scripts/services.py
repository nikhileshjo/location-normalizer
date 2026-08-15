import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ResourceClosedError
import pandas as pd

from dotenv import load_dotenv

load_dotenv()
LOCATION_CSV = os.getenv("LOCATION_CSV")
ALIAS_CSV = os.getenv("ALIAS_CSV")
DB_LOCATION = os.getenv("DB_LOCATION")

class Housekeeping():
    def _query_exec(self, query:str) -> list[tuple]:
        """
            This is a helper function that executes a query and returns the result
                Input: requeries 1 input string
                Output: List of tuples, where each tuple represents a row
        """
        try:
            if os.path.isfile(DB_LOCATION):
                engine = create_engine(f"sqlite+pysqlite:///{DB_LOCATION}")
                with engine.connect() as conn:
                    result = conn.execute(text(query))
                return result.all()
            else:
                raise FileNotFoundError(f"{DB_LOCATION} not found")
        except ResourceClosedError:
            return []
        except:
            raise
        
    
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
            db_dir = os.path.join("/".join(db_dir_folders))
            os.makedirs(db_dir, exist_ok=True)
            engine = create_engine(f"sqlite+pysqlite:///{DB_LOCATION}")
            with engine.connect() as conn:
                with open("scripts/schema/ddl_order.txt", "r") as order_file:
                    for table in order_file:
                        # table = table_1.sql\n, table_2.sql\n, table_3.sql\n...
                        with open(f"scripts/schema/{table.strip()}") as sql_ddl:
                            self._query_exec(sql_ddl.read())
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
            if not os.path.isfile(ALIAS_CSV):
                raise FileNotFoundError(f"{ALIAS_CSV} file not found")
            elif not os.path.isfile(LOCATION_CSV):
                raise FileNotFoundError(f"{LOCATION_CSV} file not found")
            else:
                try:
                    hash_val = {}
                    hashes = self.__query_exec("SELECT file_name, hash_value FROM csv_hash")
                    for file_name, hash_value in hashes:
                        hash_val[file_name] = hash_value
                except:
                    # delete existing db file and recreate the DB from the available CSV
                    os.remove(DB_LOCATION)
                    engine = create_engine(f"sqlite+pysqlite:///{DB_LOCATION}")

                    with engine.connect() as conn:
                        location_hash = conn.execute(text(f"SELECT hash_value FROM csv_hash WHERE file_name = 'location'")).all()[0][0]
                        location_hash = conn.execute(text(f"SELECT hash_value FROM csv_hash WHERE file_name = 'alias'")).all()[0][0]
                    pass
                # if location_db_hash == location_file_hash and alias_db_hash == alias_file_hash:
                #     return None
                # else:

            pass
        else:
            pass
        pass

    def shallow_sync_check(self):
        pass

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