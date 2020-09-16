import enum

import jsonschema
import yaml

# https://stackoverflow.com/questions/42159346/jsonschema-refresolver-to-resolve-multiple-refs-in-python
# https://pypi.org/project/py-openapi-schema-to-json-schema/

class RIDObject(enum.Enum):
  Volume4D = 1,


def read_rid_api():
  with open('../../interfaces/uastech.standards/remoteid/augmented.yaml', 'r') as f:
    return yaml.full_load(f)

rid_api = read_rid_api()


def rid(instance, object_type: RIDObject):
  schema = rid_api['components']['schemas'][object_type.name]
  resolver = jsonschema.RefResolver('')
  jsonschema.validate(instance, rid_components)
  jsonschema.validators.Draft7Validator
