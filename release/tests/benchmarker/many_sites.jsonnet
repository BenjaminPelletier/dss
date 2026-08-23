local common = import 'common.libsonnet';

local test_name = 'Many sites';
local db_type = 'crdb';
local dss_instances = ['aws', 'google'];
local users_per_step = 4;

local subscription_strategy = {
  implicit_subscription: {},
};

local location = {
  uniform_random_location: {
    horizontal: {
      lat_min: 30,
      lat_max: 40,
      lng_min: -120,
      lng_max: -80,
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
