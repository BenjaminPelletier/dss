from monitoring.monitorlib import validate

req = {
  "extents": {
    "spatial_volume": {
      "footprint": {
        "vertices": [
          {
            "lng": -118.456,
            "lat": 34.123
          },
          {
            "lng": -118.456,
            "lat": 34.123
          },
          {
            "lng": -118.456,
            "lat": 34.123
          }
        ]
      },
      "altitude_lo": 19.5,
      "altitude_hi": 19.5
    },
    "time_start": "2019-08-24T14:15:22Z",
    "time_end": "2019-08-24T14:15:22Z"
  },
  "flights_url": "https://example.com/flights"
}

validate.rid(req["extents"], validate.RIDObject.Volume4D)
