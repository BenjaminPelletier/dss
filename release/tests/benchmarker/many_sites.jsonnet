local common = import 'common.libsonnet';

local test_name = 'Many sites';
local db_type = 'crdb';
local dss_instances = ['aws', 'google'];
local users_per_step = 10;

local subscription_strategy = {
  implicit_subscription: {},
};

common.make_benchmark(
  test_name=test_name,
  db_type=db_type,
  dss_instances=dss_instances,
  users_per_step=users_per_step,
  subscription_strategy=subscription_strategy,
)
