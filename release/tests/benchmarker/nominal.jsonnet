local common = import 'common.libsonnet';

local test_name = 'Nominal';
local db_type = 'crdb';
local dss_instances = ['aws', 'google'];
local users_per_step = 4;

local cluster_count = 11;
local base_lat = 34.0;
local base_lng = -118.0;
local area_radius_m = 15182; // 15.182 km radius per FlightsInSub.py (Scenario 3)
local cluster_spacing_lat = (2 * area_radius_m) / 111111;
local sub_lat_radius = area_radius_m / 111111;
local sub_lng_radius = area_radius_m / (111111 * std.cos(base_lat * 3.141592653589793 / 180));

local user_types = std.flattenArrays([
  [
    local site_lat = base_lat + i * cluster_spacing_lat;
    local site_sub = {
      single_subscription: {
        subscription_id: '4c8e7%03d-0000-4000-8000-%012d' % [dss_index, i],
        duration: '23h',
        area: {
          lat_min: site_lat - sub_lat_radius,
          lat_max: site_lat + sub_lat_radius,
          lng_min: base_lng - sub_lng_radius,
          lng_max: base_lng + sub_lng_radius,
        },
        min_alt: {value: 0, units: 'M', reference: 'W84'},
        max_alt: {value: 3000, units: 'M', reference: 'W84'},
      },
    };
    local site_loc = {
      fixed_location: {
        horizontal: {lat: site_lat, lng: base_lng},
        vertical: {value: 300, reference: 'W84', units: 'M'},
      },
    };
    {
      name: 'FPU_%s_site%d' % [dss_instances[dss_index - 1], i],
      flight_planner: {
        flight_generation: {
          independent_time_location_shape: {
            time: {
              fixed_spacing: '38s',
              uniform_random_spacing: '4s',
            },
            location: site_loc,
            shape: {
              fixed_volumes: common.shape,
            },
          },
        },
        flight_execution: {
          end_flight_after_start: '5s',
        },
        scd_behavior: {
          dss_pool: ['%s_dss_pool' % dss_instances[dss_index - 1]],
          dss_selection_strategy: 'Random',
          subscription_strategy: site_sub,
          op_intent_ref_creation_strategy: {
            ovn_coordination_group: 'cluster1',
            coordinate_requested_ovns: true,
            retries: 2,
            accept_before_flight_start: '30s',
            activate_before_flight_start: '20s',
            expect_timely_clearance: true,
          },
          op_intent_ref_cleanup_strategy: {
            after_actual_flight_end: '1s',
          },
        },
      },
    } for i in std.range(0, cluster_count - 1)
  ] for dss_index in std.range(1, std.length(dss_instances))
]);

local loads = [
  {
    name: 'Flight planner ramp for %s' % dss,
    user_ramp: {
      user_types: ['FPU_%s_site%d' % [dss, i] for i in std.range(0, cluster_count - 1)],
      initial_users: users_per_step,
      additional_users_per_step: users_per_step,
      random_seed: 1234,
      throughput_stability_criteria: {
        each_user_completed_at_least: {
          count: 1,
          operations: ['workflow.flight_planner.flight'],
        },
      },
      throughput_instability_criteria: {
        any_of: [
          {
            failures_more_than: {
              count: 30,
              operations: ['workflow.flight_planner.flight'],
            },
          },
          {
            phase_duration_at_least: '120s',
          },
          {
            average_duration_more_than: {
              duration: '60s',
              operations: ['workflow.flight_planner.flight'],
            },
          },
        ],
      },
      step_completion_criteria: {
        any_of: [
          {
            sampling_duration_at_least: '90s',
          },
          {
            completed_at_least: {
              count: 100,
              operations: ['workflow.flight_planner.flight'],
            },
          },
        ],
        sampling_duration_at_least: '10s',
        completed_at_least: {
          count: 5,
          operations: ['workflow.flight_planner.flight'],
        },
      },
      load_completion_criteria: {
        any_of: [
          {
            throughput_lower_than_peak: {
              operations: ['workflow.flight_planner.flight'],
              fraction_of_peak: 0.7,
            },
          },
        ],
      },
    },
  } for dss in dss_instances
];

common.make_benchmark(
  test_name=test_name,
  db_type=db_type,
  dss_instances=dss_instances,
  users_per_step=users_per_step,
  user_types=user_types,
  loads=loads,
)
