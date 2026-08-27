import pymysql
import re

# ==========================================
# 1. DATABASE CONFIGURATIONS
# ==========================================
db_live_config = {
    'host': 'localhost',
    'port': 3316,
    'user': 'live_admin',
    'password': 'APassWord',
    'database': 'master_db'
}

db_backup_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'db_admin',
    'password': 'LocalPassWord',
    'database': 'master_db'
}

# The ID from the URL: mod/hvp/view.php?id=52348
#TARGET_CMID = 52348 # A  
#TARGET_CMID = 52353 # H
#TARGET_CMID = 52364 # O
#TARGET_CMID = 52370 # X
TARGET_CMID = 52368 # Z

def main():
    print(f"Connecting to databases...")
    conn_live = pymysql.connect(**db_live_config)
    conn_backup = pymysql.connect(**db_backup_config)

    try:

        with conn_live.cursor() as cur_live, conn_backup.cursor() as cur_backup:            
            # ==========================================
            # 2. GET LATEST LIBRARY VERSIONS (LIVE DB)
            # ==========================================
            cur_live.execute("""
                SELECT machine_name, major_version, minor_version 
                FROM vv_hvp_libraries
            """)
            
            libs_versions = {}
            for row in cur_live.fetchall():
                machine_name, major, minor = row[0], row[1], row[2]
                
                # Keep only the highest version of each library
                if machine_name not in libs_versions:
                    libs_versions[machine_name] = (major, minor)
                else:
                    if (major, minor) > libs_versions[machine_name]:
                        libs_versions[machine_name] = (major, minor)
            
            # Format to strings (e.g., {"H5P.Column": "1.22", ...})
            latest_libs = {k: f"{v[0]}.{v[1]}" for k, v in libs_versions.items()}

            # ==========================================
            # 3. MAP CMID TO HVP ID (LIVE DB)
            # ==========================================
            cur_live.execute("SELECT instance FROM vv_course_modules WHERE id = %s", (TARGET_CMID,))
            result = cur_live.fetchone()
            if not result:
                print(f"Error: Could not find course module id {TARGET_CMID}")
                return
            
            hvp_id = result[0]
            print(f"Mapped CMID {TARGET_CMID} to HVP ID {hvp_id}")

            # ==========================================
            # 4. GET OLD JSON FROM BACKUP
            # ==========================================
            cur_backup.execute("SELECT json_content FROM vv_hvp WHERE id = %s", (hvp_id,))
            backup_result = cur_backup.fetchone()
            
            if not backup_result or not backup_result[0]:
                print(f"Error: No json_content found in backup for HVP ID {hvp_id}")
                return
                
            old_json = backup_result[0]

            # ==========================================
            # 5. REGEX FIND & REPLACE VERSIONS
            # ==========================================
            def update_version(match):
                lib_name = match.group(1)
                # If we have a newer version on the live site, use it
                if lib_name in latest_libs:
                    return f"{lib_name} {latest_libs[lib_name]}"
                # Otherwise, leave it exactly as it was
                return match.group(0)

            # Finds strings like "H5P.Column 1.18"
            pattern = r'(H5P\.[A-Za-z0-9]+)\s+(\d+\.\d+)'
            new_json = re.sub(pattern, update_version, old_json)

            # ==========================================
            # 6. UPDATE LIVE DB
            # ==========================================
            # Update the JSON content and set filtered to NULL to force H5P to re-render it
            update_sql = """
                UPDATE vv_hvp 
                SET json_content = %s, filtered = NULL 
                WHERE id = %s
            """
            cur_live.execute(update_sql, (new_json, hvp_id))
            conn_live.commit()

            print(f"SUCCESS: Replaced wiped content and bumped library versions for CMID {TARGET_CMID} (HVP {hvp_id}).")
            # ==========================================
            # 7. RESTORE MISSING FILE RECORDS (vv_files)
            # ==========================================
            print(f"Checking for missing files in vv_files for HVP ID {hvp_id}...")
            
            # Fetch all files associated with this specific HVP activity from the BACKUP
            cur_backup.execute("""
                SELECT contenthash, pathnamehash, contextid, component, filearea, 
                       itemid, filepath, filename, userid, filesize, mimetype, 
                       status, source, author, license, timecreated, timemodified, sortorder, referencefileid
                FROM vv_files 
                WHERE component = 'mod_hvp' AND itemid = %s
            """, (hvp_id,))
            
            backup_files = cur_backup.fetchall()
            
            if backup_files:
                # INSERT IGNORE is used so we don't crash if some files are still in the live DB
                # The unique key in Moodle's file table is 'pathnamehash'
                insert_files_sql = """
                    INSERT IGNORE INTO vv_files 
                    (contenthash, pathnamehash, contextid, component, filearea, 
                     itemid, filepath, filename, userid, filesize, mimetype, 
                     status, source, author, license, timecreated, timemodified, sortorder, referencefileid)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur_live.executemany(insert_files_sql, backup_files)
                conn_live.commit()
                print(f"Restored {len(backup_files)} file records to the live database.")
            else:
                print("No files found in backup for this activity.")



    finally:
        conn_live.close()
        conn_backup.close()

if __name__ == "__main__":
    main()
