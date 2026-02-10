# ModScout: The Module Scout

## Overview

`ModScout` is a Flask‑based web application that browses **Lmod** module systems, checks for module‑load conflicts, and suggests alternative modules when conflicts occur.

## Quick Start

1. Copy the `.env` template file and fill in the required settings. See the **[Environment Setup Guide](#configuration-reference-envtemplate-)** for detailed information.

```bash
cp .env.template .env
```

2. Simply execute `run` script in terminal

```bash
./run
```

It does following:

1. Create/activate a Python virtual environment (`venv`).
2. Install dependencies from `requirements.txt`.
3. Launch the chosen server mode.

For more information type `./run --help` in terminal.

**Note:**

- If the run script is not executable, make it so by using

```bash
chmod +x run
```

- On the first run, there is no database yet, so nothing will be displayed. Once the app is started, simply run:

```bash
./run update # calls /update route
```

## Demo: ModScout Web Interface

![demo](./demo.gif)

## Configuration Reference (`.env.template` )

The application reads its runtime settings from a **`.env`** file (created automatically from the template). Below is a description of each variable you may need to edit.

| Variable                         | Example                    | Description                                                                                                         |
| -------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `APP_PORT`                       | `8000`                     | Port on which Flask (development) or Gunicorn (production) will listen.                                             |
| `DATA_DIR`                       | `./data`                   | Directory where the JSON files (`processed_module_*.json`) are stored. Must be writable by the app.                 |
| `AUTO_UPDATE_DATABASE`           | `False`                    | When `True`, a background scheduler (not shown here) will periodically run the update routine.                      |
| `UPDATE_SCHEDULE`                | `friday 23:00`             | Cron‑style schedule used when `AUTO_UPDATE_DATABASE=True`.                                                          |
| `HPC_USERNAME`                   | `myuser`                   | Username for SSH connections to the remote HPC systems.                                                             |
| `HPC_SSH_KEY`                    | `/home/myuser/.ssh/id_rsa` | Path to the private SSH key used for authentication.                                                                |
| `SYSTEM_1_NAME`                  | `system1`                  | Logical name for the first HPC system (used in API calls).                                                          |
| `SYSTEM_1_HOST`                  | `hpc.example.edu`          | Hostname or IP of the first HPC system.                                                                             |
| `SYSTEM_2_NAME`, `SYSTEM_2_HOST` | …                          | Additional systems follow the same pattern (`SYSTEM_2_NAME`, `SYSTEM_2_HOST`, etc.). You can add as many as needed. |

## API

All endpoints accept **GET** requests and return JSON.

### General Endpoints

| HTTP Method & Path | Description                                                                     | Example                               |
| ------------------ | ------------------------------------------------------------------------------- | ------------------------------------- |
| **GET** `/update`  | Kick‑off an asynchronous update of the module cache for each configured system. | `curl -X GET https://your‑domain.com/update` |
| **GET** `/status`  | Return the current status of the background update jobs.                        | `curl -X GET https://your‑domain.com/status` |

### Module Information Endpoints

| HTTP Method & Path            | Description                                                                                     |
| ----------------------------- | ----------------------------------------------------------------------------------------------- |
| **GET** `/module/system_list` | List all systems that are configured in the app.                                                |
| **GET** `/module/data`        | Serve the pre‑processed JSON file that contains the full module tree for a system.              |
| **GET** `/module/search`      | Search modules on a given system.                                                               |
| **POST** `/module/conflict`   | Check a selected set of modules for load conflicts and, if any, return alternative suggestions. |

#### **GET** `/module/system_list`

- Example
  ```bash
  curl -X GET "https://your‑domain.com/module/system_list"
  ```
- Output
  ```json
  {
    "systems": ["system1", "system2"]
  }
  ```

#### **GET** `/module/data`

- **Query parameter**

  | Parameter | Description                 | Example          |
  | --------- | --------------------------- | ---------------- |
  | `system`  | Name of the system to query | `system=system1` |

- Example
  ```bash
  curl -X GET "https://your‑domain.com/module/data?system=system1"
  # Output: The full json file content for system1
  ```

#### **GET** `/module/search`

- **Query parameters**

  | Parameter | Description                                                                                                                              |
  | --------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
  | `system`  | Name of the system to search in.                                                                                                         |
  | `query`   | Search terms. Multiple modules can be supplied, separated by commas. The syntax after each module name controls the scope of the search. |

- **`query` syntax**

  | Format               | Meaning                                                                                  |
  | -------------------- | ---------------------------------------------------------------------------------------- |
  | `module1`            | Searches **both** the module name **and** its description.                               |
  | `module1/`           | Searches **only** the module name, but returns **all** available versions.               |
  | `module1/v1`         | Searches **only** the module name and restricts results to the specified version (`v1`). |
  | `module1/v1,module2` | Searches for multiple modules in one request. Use a comma (`,`) to separate each entry.  |

- Example

  ```bash
  curl -X GET "https://your‑domain.com/module/search?system=system1&query=module1"
  curl -X GET "https://your‑domain.com/module/search?system=system1&query=module1/"
  curl -X GET "https://your‑domain.com/module/search?system=system1&query=module1/v2"
  curl -X GET "https://your‑domain.com/module/search?system=system1&query=module1/v2,module2"
  ```

- **Output**

  ```json
  {
    "release1": {
      "compiler1": [
        {
          "compiler": "GCC/13.2.0",
          "description": "",
          "load_cmd": "module load release/24.04 GCC/13.2.0 module1",
          "name": "module1/v1",
          "package": "module1",
          "release": "release",
          "url": "",
          "version": "v1"
        }
        // … additional module entries …
      ]
      // … other compilers for this release …
    }
    // … other releases …
  }
  ```

#### **POST** `/module/conflict`

- **Query parameter**

  | Parameter | Description                                   |
  | --------- | --------------------------------------------- |
  | JSON body | JSON Body with list of modules as shown below |

- Example
  ```bash
    curl -X POST "https://your‑domain.com/module/conflict" \
    -H "Content-Type: application/json" \
    -d '{
        "system": "<system-name>",          // e.g. "system1"
        "selected": [
        {
            "package": "PackageA",
            "version": "X.Y.Z",
            "name": "PackageA/X.Y.Z",
            "release": "release/YY.MM",
            "compiler": "GCC/13.2.0",
            "load_cmd": "module load release/YY.MM GCC/13.2.0 PackageA/X.Y.Z"
        },
        {
            "package": "PackageB",
            "version": "U.V.W",
            "name": "PackageB/U.V.W",
            "release": "release/YY.MM",
            "compiler": "GCC/13.2.0",
            "load_cmd": "module load release/YY.MM GCC/13.2.0 PackageB/U.V.W"
        }
        // … additional module objects as needed …
        ]
    }'
  ```
- Output
  ```json
  {
    "conflict": true,
    "msg": "Modules must share the same releases.",
    "suggestions": {
      "success": true,
      "suggestion_count": 2,
      "suggestions_full": [
        [
          {
            "package": "PackageA",
            "version": "X.Y.Z",
            "name": "PackageA/X.Y.Z",
            "description": "Short description of PackageA",
            "url": "https://example.com/packageA",
            "release": "release/YY.MM",
            "compiler": "GCC/13.2.0",
            "load_cmd": "module load release/YY.MM GCC/13.2.0 PackageA/X.Y.Z"
          },
          {
            "package": "PackageB",
            "version": "U.V.W",
            "name": "PackageB/U.V.W",
            "description": "Short description of PackageB",
            "url": "https://example.com/packageB",
            "release": "release/YY.MM",
            "compiler": "GCC/13.2.0",
            "load_cmd": "module load release/YY.MM GCC/13.2.0 PackageB/U.V.W"
          }
        ]
        // ... second group of suggestions
      ]
    }
  }
  ```
  or
  ```json
  {
    "conflict": true,
    "msg": "Modules must share the same releases.",
    "suggestions": {
      "suggestion_count": 0,
      "suggestions_full": [],
      "suggestions_parsed": []
    }
  }
  ```

## TODO

- Supporting extension modules. Currently the extension modules are not extracted using command present in the Flask App.
- Containerization using docker.

## License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.
