local common = import 'common.libsonnet';

local test_name = 'Congested area';
local db_type = 'crdb';
local dss_instances = ['aws', 'google'];
local users_per_step = 2;

local subscription_strategy = {
  single_subscription: {
    subscription_id: '3bdb0b88-a522-4286-9499-160e56c953bb',
    duration: '23h',
    area: {
      lat_min: 34 - 0.00001,
      lng_min: -118 - 0.00001,
      lat_max: 34 + 0.00001,
      lng_max: -118 + 0.00001,
    },
    min_alt: {value: 0, units: 'M', reference: 'W84'},
    max_alt: {value: 3000, units: 'M', reference: 'W84'},
  },
};

local location = {
  fixed_location: {
    horizontal: {lat: 34, lng: -118},
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
