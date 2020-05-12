import datetime
from dateutil import parser
import pytz


def format_ts(timestamp: datetime.datetime = None) -> str:
  """Formats a Python datetime as a NASA-style string.

  Args:
    timestamp: Python datetime to format; defaults to now

  Returns:
    String formatted like YYYY-mm-ddTHH:MM:SS.fffZ
  """
  r = datetime.datetime.now(pytz.utc) if timestamp is None else timestamp
  r = r.astimezone(pytz.utc)
  return '{0}Z'.format(r.strftime('%Y-%m-%dT%H:%M:%S.%f')[:23])


def parse_timestamp(timestamp_str: str) -> datetime.datetime:
  """Parses a timestamp into a Python datetime.

  Args:
    timestamp_str: timestamp string, with or without Z suffix

  Returns:
    Python datetime representation of timestamp
  """
  timestamp = parser.parse(timestamp_str)
  if timestamp.tzinfo is None:
    timestamp = timestamp.replace(tzinfo=pytz.utc)
  return timestamp
