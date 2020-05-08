import os

from app.scd import geo


class ScdConfig(object):
  SCD_GEO_CONFIG = geo.Config(
    min_s2_level=os.environ.get('SCD_MIN_S2_LEVEL', 13),
    max_s2_level=os.environ.get('SCD_MAX_S2_LEVEL', 13),
  )
