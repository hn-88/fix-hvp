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
            # REGEX FIND & REPLACE VERSIONS (was missing here)
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

            # SQL for restoring file records (was missing here)
            insert_files_sql = """
                INSERT IGNORE INTO vv_files 
                (contenthash, pathnamehash, contextid, component, filearea, 
                 itemid, filepath, filename, userid, filesize, mimetype, 
                 status, source, author, license, timecreated, timemodified, sortorder, referencefileid)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            # ==========================================
            # FIND ALL WIPED ACTIVITIES IN LIVE DB
            cur_live.execute("""
                SELECT id 
                FROM vv_hvp 
                WHERE json_content LIKE '%"content":{"params":{}}}%'
            """)
            broken_hvp_ids = [row[0] for row in cur_live.fetchall()]
            
            print(f"Found {len(broken_hvp_ids)} wiped H5P activities to fix.")

            for hvp_id in broken_hvp_ids:
                print(f"--- Fixing HVP ID: {hvp_id} ---")
                
                # 1. Fetch JSON from backup
                cur_backup.execute("SELECT json_content FROM vv_hvp WHERE id = %s", (hvp_id,))
                backup_result = cur_backup.fetchone()
                
                if not backup_result or not backup_result[0]:
                    print(f"  Skipping: No backup JSON found.")
                    continue
                
                # 2. Regex replace versions
                new_json = re.sub(pattern, update_version, backup_result[0])
                
                # 3. Update Live DB
                cur_live.execute("UPDATE vv_hvp SET json_content = %s, filtered = NULL WHERE id = %s", (new_json, hvp_id))
                
                # 4. Restore files
                cur_backup.execute("""
                    SELECT contenthash, pathnamehash, contextid, component, filearea, 
                           itemid, filepath, filename, userid, filesize, mimetype, 
                           status, source, author, license, timecreated, timemodified, sortorder, referencefileid
                    FROM vv_files 
                    WHERE component = 'mod_hvp' AND itemid = %s
                """, (hvp_id,))
                
                backup_files = cur_backup.fetchall()
                if backup_files:
                    cur_live.executemany(insert_files_sql, backup_files)
                    print(f"  Restored JSON and {len(backup_files)} files.")
                else:
                    print(f"  Restored JSON (0 files needed).")

                # Commit after each activity so progress isn't lost if a later one fails
                conn_live.commit()

            print("Finished fixing all wiped activities!")


    finally:
        conn_live.close()
        conn_backup.close()

if __name__ == "__main__":
    main()
