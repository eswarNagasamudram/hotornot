import json
import toml

# Load the JSON file
with open("vertex-key.json", "r") as f:
    json_data = json.load(f)

# Convert the JSON data to TOML
toml_data = toml.dumps(json_data)

# Save the TOML file
with open("vertex-key.toml", "w") as f:
    f.write(toml_data)