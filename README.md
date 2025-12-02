# Pokemon Assessment API

A small FastAPI + SQLite service built for a technical assessment.
It cleans a provided Pokémon-themed database and exposes several read endpoints, plus an endpoint to create a new Pokémon by fetching data from the public PokeAPI.

## Contents

* [Features](#features)
* [Tech Stack](#tech-stack)
* [Project Structure](#project-structure)
* [Setup](#setup)
* [Running the App](#running-the-app)
* [Database Cleaning](#database-cleaning)
* [API Endpoints](#api-endpoints)

---

## Features

* Connects to a local SQLite database (`pokemon_assessment.db`).
* Cleans data by:

  * Fixing common misspellings.
  * Standardizing casing/whitespace.
  * Removing duplicates while preserving referential integrity.
  * Removing placeholder / junk rows.
* Exposes endpoints to:

  * List Pokémon by ability.
  * List Pokémon by type (type1 or type2).
  * List trainers by Pokémon.
  * List abilities by Pokémon.
* Creates a new Pokémon by name:

  * Fetches canonical data from PokeAPI.
  * Inserts Pokémon, types, and abilities if missing.
  * Links a random trainer to the new Pokémon with its abilities.

---

## Tech Stack

* **Python 3.10+**
* **FastAPI**
* **Uvicorn**
* **SQLite3**
* **httpx** (async HTTP client)

---

## Project Structure

```
.
├── candidate_solution.py
├── pokemon_assessment.db (created on the fly)
```

---

## Setup

1. **Clone / download the project**

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS/Linux
   .venv\Scripts\activate      # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install fastapi uvicorn httpx
   ```
---

## Running the App

From the project directory:

```bash
python candidate_solution.py
```

The app will:

1. Connect to the DB.
2. Run `clean_database()` once at startup (when executed as `__main__`).
3. Start FastAPI on:

```
http://127.0.0.1:8000
```

Interactive docs:

* Swagger UI: `http://127.0.0.1:8000/docs`
* Redoc: `http://127.0.0.1:8000/redoc`

---

## Database Cleaning

On startup (local run), the script cleans these tables:

* `pokemon`
* `types`
* `abilities`
* `trainers`

Cleaning steps:

1. **Misspelling corrections** using a fixed mapping (case-insensitive).
2. **Whitespace trimming** and **title-casing** for standardized display.
3. **Duplicate removal** by normalized name:

   * Keeps the lowest ID row.
   * Remaps foreign keys in referencing tables to the kept ID.
4. **Removal of junk values** (e.g., `"???"`, `"---"`, empty strings).

---

## API Endpoints

### 1. Health / root

**GET** `/`

Returns a simple status message.

Example:

```json
{
  "message": "Status: Ready. The time is 2025-12-02 09:43:10"
}
```

---

### 2. Pokémon by Ability

**GET** `/pokemon/ability/{ability_name}`

Returns all Pokémon names that have the given ability.

* **400** if the name is empty.
* **404** if the ability does not exist.

Example:

`/pokemon/ability/Overgrow`

```json
["Bulbasaur", "Ivysaur", "Venusaur"]
```

---

### 3. Pokémon by Type

**GET** `/pokemon/type/{type_name}`

Returns all Pokémon that match the type in either `type1_id` or `type2_id`.

* **400** if empty.
* **404** if type not found.

Example:

`/pokemon/type/Fire`

```json
["Charmander", "Charmeleon", "Charizard"]
```

---

### 4. Trainers by Pokémon

**GET** `/trainers/pokemon/{pokemon_name}`

Returns all trainers who have the given Pokémon.

* **400** if empty.
* **404** if Pokémon not found.

Example:

`/trainers/pokemon/Pikachu`

```json
["Ash", "Misty"]
```

---

### 5. Abilities by Pokémon

**GET** `/abilities/pokemon/{pokemon_name}`

Returns all abilities for a given Pokémon.

* **400** if empty.
* **404** if Pokémon not found.

Example:

`/abilities/pokemon/Squirtle`

```json
["Torrent", "Rain Dish"]
```

---

### 6. Create Pokémon (from PokeAPI)

**POST** `/pokemon/create/{pokemon_name}`

Fetches a Pokémon from PokeAPI and inserts it into the DB if missing.

**Behavior**

* **400** if `{pokemon_name}` is empty.
* **409 Conflict** if the Pokémon already exists in the DB.
* **404** if the name is not found in PokeAPI.
* **503** if PokeAPI is unreachable.
* On success:

  * Inserts Pokémon.
  * Inserts missing abilities/types.
  * Links abilities to Pokémon in `trainer_pokemon_abilities`.
  * Randomly assigns one trainer from DB.

Example:

`POST /pokemon/create/pikachu`

```json
{
  "message": "Successfully created Pokemon pikachu who has been trained by Ash"
}
```
