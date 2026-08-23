local common = import 'common.libsonnet';

local test_name = 'Nominal';
local db_type = 'crdb';
local dss_instances = ['aws', 'google'];
local users_per_step = 4;

local subscription_strategy = {
  single_subscription: {
    subscription_id: '4c8e70a3-34e8-466d-8b83-b7787381d643',
    duration: '23h',
    area: {
      lat_min: 34 - 0.14,
      lng_min: -118 - 0.14,
      lat_max: 34 + 0.14,
      lng_max: -118 + 0.14,
    },
    min_alt: {value: 0, units: 'M', reference: 'W84'},
    max_alt: {value: 3000, units: 'M', reference: 'W84'},
  },
};

local location = {
  uniform_random_location: {
    horizontal: {
      lat_min: 34 - 0.14,
      lat_max: 34 + 0.14,
      lng_min: -118 - 0.14,
      lng_max: -118 + 0.14,
    },
    vertical: {value: 300, reference: 'W84', units: 'M'},
  },
};

common.make_benchmark(
  test_name=test_name,
  db_type=db_type,
  dss_instances=dss_instances,
  users_per_step=users_per_step,
  subscription_strategy=subscription_strategy,
  location=location,
)
