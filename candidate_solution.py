# candidate_solution.py
import sqlite3
import os
import httpx
from fastapi import FastAPI, HTTPException, status
from typing import List, Optional
import uvicorn
from datetime import datetime

# --- Constants ---
DB_NAME = "pokemon_assessment.db"
POKEAPI_BASE = "https://pokeapi.co/api/v2/pokemon"

# --- Database Connection ---
def connect_db() -> Optional[sqlite3.Connection]:
    """
    Task 1: Connect to the SQLite database.
    Implement the connection logic and return the connection object.
    Return None if connection fails.
    """
    if not os.path.exists(DB_NAME):
        print(f"Error: Database file '{DB_NAME}' not found.")
        return None

    connection = None
    try:
        # --- Implement Here ---
        connection = sqlite3.connect(DB_NAME)
        connection.row_factory = sqlite3.Row
        # --- End Implementation ---
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

    return connection


# --- Data Cleaning ---
def clean_database(conn: sqlite3.Connection):
    """
    Task 2: Clean up the database using the provided connection object.
    Implement logic to:
    - Remove duplicate entries in tables (pokemon, types, abilities, trainers).
      Choose a consistent strategy (e.g., keep the first encountered/lowest ID).
    - Correct known misspellings (e.g., 'Pikuchu' -> 'Pikachu', 'gras' -> 'Grass', etc.).
    - Standardize casing (e.g., 'fire' -> 'Fire' or all lowercase for names/types/abilities).
    """
    if not conn:
        print("Error: Invalid database connection provided for cleaning.")
        return

    cursor = conn.cursor()
    print("Starting database cleaning...")

    try:
        # --- Implement Here ---

         # Safety: enforce FK support if schema uses it
        cursor.execute("PRAGMA foreign_keys = ON;")

        WORDS_TO_REMOVE = [
            "???",
            "---",
            "",
            "Remove This Ability"
        ]
         # Known misspellings -> corrected form (case-insensitive match)
        MISSPELLINGS = {
            # pokemon
            "pikuchu": "Pikachu",
            "charzard": "Charizard",
            "bulbasaurrr": "Bulbasaur",
            "bulbasuar": "Bulbasaur",
            "squirtel": "Squirtle",
            "charmanderr":"Charmander",
            # types
            "gras": "Grass",
            "eletric": "Electric",
            "psycic": "Psychic",
            "poisen": "Poison",
            "poision":"Poison",
            # abilities
            "overgroww": "Overgrow",
            "torrentt": "Torrent",
            "run away":"Run-away", #api friendly
            "keen eye":"Keen-eye", #api friendly
            "rock head":"Rock-head", #api friendly
            # trainers
            "ashh": "Ash",
            "misty ": "Misty",
        }

        TARGET_TABLES = ["pokemon", "types", "abilities", "trainers"]

        # quick safety check if table exist
        def table_exists(t):
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (t,)
            )
            return cursor.fetchone() is not None

        
        def get_id_and_name_cols(t):

            # Returns (id_col, name_col). Tries common patterns.
            
            cursor.execute(f"PRAGMA table_info({t})")
            cols = cursor.fetchall()
            col_names = [c[1] for c in cols]

            # id column
            id_candidates = [c for c in col_names if c.lower() in ("id", f"{t[:-1]}_id", f"{t}_id")]
            id_col = id_candidates[0] if id_candidates else col_names[0]

            # name column
            name_candidates = [c for c in col_names if c.lower() in ("name", f"{t[:-1]}_name", f"{t}_name", "type", "ability", "trainer", "pokemon_name")]
            name_col = name_candidates[0] if name_candidates else None

            return id_col, name_col

        def title_case(s: str) -> str:
            if s is None:
                return s
            s = s.strip()
            # keep special cases like "Mr. Mime" or "Ho-Oh" reasonably intact:
            return " ".join(part.capitalize() for part in s.split())
        

        def remap_foreign_keys(base_table, old_id, new_id):
            
            # For any table referencing base_table, update FK values old_id -> new_id.
            
            for t in all_tables:
                cursor.execute(f"PRAGMA foreign_key_list({t})")
                fks = cursor.fetchall()
                for fk in fks:
                    # fk columns: (id, seq, table, from, to, on_update, on_delete, match)
                    ref_table = fk[2]
                    from_col = fk[3]
                    to_col = fk[4]
                    if ref_table == base_table and to_col:
                        cursor.execute(
                            f"UPDATE {t} SET {from_col}=? WHERE {from_col}=?",
                            (new_id, old_id)
                        )

                        
        # Find all tables once for FK remapping
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = [r[0] for r in cursor.fetchall()]

        # Loop the target tables and and clean data
        for t in TARGET_TABLES:
            if not table_exists(t):
                continue

            id_col, name_col = get_id_and_name_cols(t)
            if not name_col:
                # Can't clean without a text/name-like column
                continue

            # 1) Standardize casing + strip whitespace + fix misspellings
            cursor.execute(f"SELECT {id_col}, {name_col} FROM {t}")
            rows = cursor.fetchall()
            for row_id, raw_name in rows:
                if raw_name is None:
                    continue
                cleaned = raw_name.strip()
                key = cleaned.lower()
                if key in MISSPELLINGS:
                    cleaned = MISSPELLINGS[key]
                else:
                    cleaned = title_case(cleaned)

                if cleaned != raw_name:
                    cursor.execute(
                        f"UPDATE {t} SET {name_col}=? WHERE {id_col}=?",
                        (cleaned, row_id)
                    )

            # 2) Remove duplicates by name (keep lowest ID)
            # We compare case-insensitively so "fire" and "Fire" collapse.
            cursor.execute(
                f"""
                SELECT LOWER(TRIM({name_col})) AS nm, MIN({id_col}) AS keep_id
                FROM {t}
                WHERE {name_col} IS NOT NULL
                GROUP BY LOWER(TRIM({name_col}))
                HAVING COUNT(*) > 1
                """
            )
            dup_groups = cursor.fetchall()

            for nm, keep_id in dup_groups:
                # find all ids in this dup group except keep_id
                cursor.execute(
                    f"""
                    SELECT {id_col}
                    FROM {t}
                    WHERE LOWER(TRIM({name_col})) = ?
                      AND {id_col} <> ?
                    """,
                    (nm, keep_id)
                )
                dup_ids = [r[0] for r in cursor.fetchall()]

                for dup_id in dup_ids:
                    # remap foreign keys from dup_id -> keep_id
                    remap_foreign_keys(t, dup_id, keep_id)

                if dup_ids:
                    cursor.execute(
                        f"DELETE FROM {t} WHERE {id_col} IN ({','.join('?' for _ in dup_ids)})",
                        dup_ids
                    )

            ### remove_list: list[str] of values to delete wherever they appear.

            # This deletes rows where ANY text column equals one of the remove_list values (case-insensitive, trimmed).
            
            # Normalize remove_list once
            WORDS_TO_REMOVE_lower = [v.strip().lower() for v in WORDS_TO_REMOVE ]
            if not WORDS_TO_REMOVE_lower:
                print("No removal values provided.")

            else:
                try:

                    # Inspect columns
                    cursor.execute(f"PRAGMA table_info({t})")
                    cols = cursor.fetchall()

                    # Pick likely text columns
                    text_cols = []
                    for c in cols:
                        col_name = c[1]
                        col_type = (c[2] or "").upper()
                        if ("CHAR" in col_type) or ("TEXT" in col_type) or ("CLOB" in col_type) or col_name.lower() in ("name", "type", "ability", "trainer", "pokemon_name"):
                            text_cols.append(col_name)

                    if not text_cols:
                        continue

                    # For each text column, delete rows matching any bad value
                    for col in text_cols:
                        # Build: LOWER(TRIM(col)) IN (?, ?, ...)
                        placeholders = ",".join("?" for _ in WORDS_TO_REMOVE_lower)
                        sql = f"""
                            DELETE FROM {t}
                            WHERE {col} IS NOT NULL
                              AND LOWER(TRIM({col})) IN ({placeholders})
                        """
                        cursor.execute(sql, WORDS_TO_REMOVE_lower)

                except sqlite3.Error as e:
                    print(f"Removal step failed: {e}")
                    return None
                
        # --- End Implementation ---
        conn.commit()
        print("Database cleaning finished and changes committed.")

    except sqlite3.Error as e:
        print(f"An error occurred during database cleaning: {e}")
        conn.rollback()  # Roll back changes on error


# --- FastAPI Application ---
def create_fastapi_app() -> FastAPI:
    """
    FastAPI application instance.
    Define the FastAPI app and include all the required endpoints below.
    """
    print("Creating FastAPI app and defining endpoints...")
    app = FastAPI(title="Pokemon Assessment API")

    # --- Define Endpoints Here ---
    @app.get("/")
    def read_root():
        """
        Task 3: Basic root response message
        Return a simple JSON response object that contains a `message` key with any corresponding value.
        """
        # --- Implement here ---
        now = datetime.now()
        return {"message": f"Status: Ready. The time is {now:%Y-%m-%d %H:%M:%S %Z}"}

        # --- End Implementation ---

    @app.get("/pokemon/ability/{ability_name}", response_model=List[str])
    def get_pokemon_by_ability(ability_name: str):
        """
        Task 4: Retrieve all Pokémon names with a specific ability.
        Query the cleaned database. Handle cases where the ability doesn't exist.
        """
        # --- Implement here ---

        # Developer note : Alot of the Api's could have been built inside one function making the code smaller and easier to read
        # but this would have required code outside the 'Impiment here zones' - so I did not do this.
        
        if not ability_name or not ability_name.strip():
            raise HTTPException(status_code=400, detail="Ability name cannot be empty.")
        conn = connect_db()
        cur = conn.cursor()
        abil = ability_name.strip()
        
        # 1) Find ability id (case-insensitive) - also check if the ability actually exists
        cur.execute(
            "SELECT id FROM abilities WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
            (abil,)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Ability '{ability_name}' not found.")

        ability_id = row[0]
        # Perform joins        
        results: List[str] = []

        # Simple group by to ensure no duplicate names
        cur.execute(
                    f"""
                    SELECT p.name
                    FROM  abilities a
                    INNER JOIN trainer_pokemon_abilities ta ON ta.ability_id = a.id
                    INNER JOIN pokemon p ON ta.pokemon_id = p.id
                    WHERE a.id = ?
                    GROUP BY p.name
                    ORDER BY p.name
                    """,
                    (ability_id,)
                )

        results = [r[0] for r in cur.fetchall()]

        # If ability exists but no pokemon reference it, return empty list (not an error)
        conn.close()
        return results
        # --- End Implementation ---

    @app.get("/pokemon/type/{type_name}", response_model=List[str])
    def get_pokemon_by_type(type_name: str):
        """
        Task 5: Retrieve all Pokémon names of a specific type (considers type1 and type2).
        Query the cleaned database. Handle cases where the type doesn't exist.
        """
        # --- Implement here ---
        if not type_name or not type_name.strip():
            raise HTTPException(status_code=400, detail="Type name cannot be empty.")
        conn = connect_db()
        cur = conn.cursor()
        type_ = type_name.strip()
        
        # 1) Find ty[e id (case-insensitive) - also check if the type actually exists
        cur.execute(
            "SELECT id FROM types WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
            (type_,)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Type '{type_name}' not found.")

        type_id = row[0]
        # Perform joins        
        results: List[str] = []

        # Simple group by to ensure no duplicate names
        cur.execute(
                    f"""
                    	SELECT * 
					FROM (
					
					SELECT p.name 
					FROM types t
					INNER JOIN pokemon p on p.type1_id=t.id
					WHERE t.id=?
					UNION
					SELECT p.name 
					FROM types t
					INNER JOIN pokemon p on p.type2_id=t.id
					WHERE t.id=?
					) as t
					GROUP BY name
                    """,
                    (type_id,type_id)  # feels redundant to pass the same parameter twice... But when in Rome...
                )

        results = [r[0] for r in cur.fetchall()]

        # If type exists but no pokemon reference it, return empty list (not an error)
        conn.close()
        return results
        # --- End Implementation ---

    @app.get("/trainers/pokemon/{pokemon_name}", response_model=List[str])
    def get_trainers_by_pokemon(pokemon_name: str):
        """
        Task 6: Retrieve all trainer names who have a specific Pokémon.
        Query the cleaned database. Handle cases where the Pokémon doesn't exist or has no trainer.
        """
        # --- Implement here ---
        
        if not pokemon_name or not pokemon_name.strip():
            raise HTTPException(status_code=400, detail="Pokemon name cannot be empty.")
        conn = connect_db()
        cur = conn.cursor()
        pokemon_name_ = pokemon_name.strip()
        
        # 1) Find ty[e id (case-insensitive) - also check if the pokemon actually exists
        cur.execute(
            "SELECT id FROM pokemon WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
            (pokemon_name_,)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Pokemon '{pokemon_name}' not found.")

        pokemon_id = row[0]
        # Perform joins        
        results: List[str] = []

        # Simple group by to ensure no duplicate names
        cur.execute(
                    f"""
					SELECT t.name 
					FROM pokemon p
					INNER JOIN trainer_pokemon_abilities ta on ta.pokemon_id=p.id
					INNER JOIN trainers t on ta.trainer_id=t.id
					WHERE p.id=?
					GROUP BY t.name
                    """,
                    (pokemon_id,) 
                )

        results = [r[0] for r in cur.fetchall()]

        # If pokemon exists but no trainer reference it, return empty list (not an error)
        conn.close()
        return results

        # --- End Implementation ---

    @app.get("/abilities/pokemon/{pokemon_name}", response_model=List[str])
    def get_abilities_by_pokemon(pokemon_name: str):
        """
        Task 7: Retrieve all ability names of a specific Pokémon.
        Query the cleaned database. Handle cases where the Pokémon doesn't exist.
        """
        # --- Implement here ---

        if not pokemon_name or not pokemon_name.strip():
            raise HTTPException(status_code=400, detail="Pokemon name cannot be empty.")
        conn = connect_db()
        cur = conn.cursor()
        pokemon_name_ = pokemon_name.strip()
        
        # 1) Find ty[e id (case-insensitive) - also check if the pokemon actually exists
        cur.execute(
            "SELECT id FROM pokemon WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
            (pokemon_name_,)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Pokemon '{pokemon_name}' not found.")

        pokemon_id = row[0]
        # Perform joins        
        results: List[str] = []

        # Simple group by to ensure no duplicate names
        cur.execute(
                    f"""
					SELECT a.name 
					FROM pokemon p
					INNER JOIN trainer_pokemon_abilities ta on ta.pokemon_id=p.id
					INNER JOIN abilities a on ta.ability_id=a.id
					WHERE p.id=?
					GROUP BY a.name
                    """,
                    (pokemon_id,) 
                )

        results = [r[0] for r in cur.fetchall()]

        # If pokemon exists but no ability reference it, return empty list (not an error)
        conn.close()
        return results
        # --- End Implementation ---

    # --- Implement Task 8 here ---
    # API to Create New Pokemon in DB
    @app.post("/pokemon/create/{pokemon_name}")
    async def create_pokemon(pokemon_name: str):
        if not pokemon_name or not pokemon_name.strip():
            raise HTTPException(status_code=400, detail="Pokemon name cannot be empty.")
        
        pokemon_name_ = pokemon_name.strip().lower()
        conn = connect_db()
        cur = conn.cursor()
       # 1) Check if pokemon exists
        cur.execute(
            "SELECT id FROM pokemon WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
            (pokemon_name_,)
        )


        # Camel case function to neaten API name
        def to_camel_case(s: str) -> str:
            s = "".join(ch if ch.isalnum() else " " for ch in s)
            parts = [p for p in s.split() if p]
            if not parts:
                return ""
            first, rest = parts[0].lower(), parts[1:]
            return first + "".join(p.capitalize() for p in rest)

        row = cur.fetchone()
        if row:
            conn.close()
            raise HTTPException(status_code=409, detail=f"Pokemon '{pokemon_name}' already exists in db.")

        # we dont have the Pokemon in DB- get the details
        # ----------------------------
        # 2) Fetch pokemon from PokeAPI
        # ----------------------------
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{POKEAPI_BASE}/{pokemon_name_}")
        except httpx.RequestError:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PokeAPI is unreachable"
            )

        if resp.status_code == 404:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pokemon '{pokemon_name}' not identified"
            )
        if resp.status_code >= 400:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"PokeAPI error ({resp.status_code})"
            )

        data = resp.json()

        # ----------------------------
        # 3) Extract relevant data
        # ----------------------------
        api_pokemon_id: int = data["id"]
        display_name: str = data["name"]

        display_name = to_camel_case(display_name)

        # abilities list from api
        api_abilities: List[str] = [
            a["ability"]["name"]
            for a in data.get("abilities", [])
            if a.get("ability")
        ]
        # types list from api
        api_types: List[str] = [
            t["type"]["name"]
            for t in data.get("types", [])
            if t.get("type")
        ]

        # Get a random trainer ready for later
        cur.execute("SELECT id,name FROM trainers ORDER BY RANDOM() LIMIT 1")
        row = cur.fetchone()
        if not row:
            raise Exception("No trainers in DB")
        random_trainer_id = row[0]
        random_trainer_name = row[1]
        
        cur.execute(
            """
            INSERT INTO pokemon (name, type1_id, type2_id)
            VALUES (?, NULL, NULL)
            """,
            (display_name,)
        )
        new_pokemon_id = cur.lastrowid
        print(f"Created new pokemon ID {new_pokemon_id}")

        # For each ability - check is it in db? No-Add - Assign ID to new pokemon
        for ab_name in api_abilities:
            # 1) check if ability exists
            cur.execute(
                """
                SELECT id FROM abilities
                WHERE name = ?
                LIMIT 1
                """,
                (to_camel_case(ab_name),)
            )
            row = cur.fetchone()

            if row:
                ability_id = row[0]
            else:
                # 2) insert ability if missing
                cur.execute(
                    """
                    INSERT INTO abilities (name)
                    VALUES (?)
                    """,
                    (to_camel_case(ab_name),)
                )
                ability_id = cur.lastrowid

            # 3) link ability to pokemon in junction table
            # (adjust column names if yours differ)
            cur.execute(
                """
                INSERT INTO trainer_pokemon_abilities (pokemon_id, ability_id, trainer_id)
                VALUES (?, ?, ?)
                """,
                (new_pokemon_id, ability_id, random_trainer_id)
            )

        # Resolve up to two type IDs
        type_ids: List[int] = []
        
        for t_name in api_types[:2]:  # only first two types matter
            # 1) check if type exists
            cur.execute(
                """
                SELECT id FROM types
                WHERE name = ?
                LIMIT 1
                """,
                (to_camel_case(t_name),)
            )
            row = cur.fetchone()

            if row:
                t_id = row[0]
            else:
                # 2) insert type if missing
                cur.execute(
                    """
                    INSERT INTO types (name)
                    VALUES (?)
                    """,
                    (to_camel_case(t_name),)
                )
                t_id = cur.lastrowid

            type_ids.append(t_id)

        # Pad if only 0 or 1 type
        type1_id: Optional[int] = type_ids[0] if len(type_ids) > 0 else None
        type2_id: Optional[int] = type_ids[1] if len(type_ids) > 1 else None

        # Update pokemon row with type1_id/type2_id
        cur.execute(
            """
            UPDATE pokemon
            SET type1_id = ?, type2_id = ?
            WHERE id = ?
            """,
            (type1_id, type2_id, new_pokemon_id)
        )

        conn.commit()
        conn.close()
        return {"message": f"Successfully created Pokemon {pokemon_name} who has been trained by {random_trainer_name}"}
    # --- End Implementation ---

    print("FastAPI app created successfully.")
    return app


# --- Main execution / Uvicorn setup (Optional - for candidate to run locally) ---
if __name__ == "__main__":
    # Ensure data is cleaned before running the app for testing
    temp_conn = connect_db()
    if temp_conn:
        clean_database(temp_conn)
        temp_conn.close()

    app_instance = create_fastapi_app()
    uvicorn.run(app_instance, host="127.0.0.1", port=8000)
