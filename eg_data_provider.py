import sqlite3
import logging
import os

logger = logging.getLogger("EG_Data_Provider")

class EG_Data_Provider:
    def __init__(self, database: str) -> None:
        self.db_path = database
        logger.info("Database file: %s" % (database))
        self.db_conn = sqlite3.connect(database)
        self.db_version = "1.01"
        self.prepare_database()

    
    def prepare_database(self):
        reinit = True
        try:
            cur = self.db_conn.cursor()
            version = cur.execute("SELECT * FROM version").fetchone()
            if version[0] != self.db_version:
                logger.warning("Incorrect database version: %s. Reinit" % (str(version)))
            else:
                logger.info("Database version: %s" % (self.db_version))
                reinit = False
                
        except:
            pass

        if reinit:
            self.db_conn.close()
            os.remove(self.db_path)
            self.db_conn = sqlite3.connect(self.db_path)
            cur = self.db_conn.cursor()
            cur.execute("CREATE TABLE version(ver TEXT)")
            cur.execute("INSERT INTO version VALUES(%s)" % (self.db_version))
            self.db_conn.commit()
            cur.execute("CREATE TABLE users(user_id TEXT, username TEXT, UNIQUE(user_id, username))")
            version = cur.execute("SELECT * FROM version").fetchone()
            logger.debug("Database version: %s" % (str(version)))
            
    
    def get_user_data(self, user_id):
        cur = self.db_conn.cursor()
        cur.execute("SELECT username FROM users")
        res = cur.fetchone()

        logger.debug("Get user data for user id: %d result: %s", (user_id, str(res)))

        return res
    
    def store_user_data(self, user_id, callsign):
        cur = self.db_conn.cursor()
        try:
            cur.execute("INSERT INTO users VALUES(?, ?)", (user_id, callsign))
            self.db_conn.commit()
        except sqlite3.IntegrityError:
            logger.error("Can't store user data - user already exist")
        except:
            logger.error("Unknown error during store user data")
