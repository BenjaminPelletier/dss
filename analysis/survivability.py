import datetime
import itertools
import math
import numpy as np


def print_survivability(node_owners, replicas, replica_per_uss):
  """Print survivability rates for the specified system configuration.

  Evaluate all possible failure scenarios by brute force assuming equal
  probability for each.

  :param node_owners: USS that owns each node (also defines number of nodes)
  :param replicas: Number of replicas spread across all nodes for each range
  :param replica_per_uss: If true, every USS must own at least one replica
  """
  min_replicas = math.ceil(replicas / 2) # Number of non-failed replicas required for range functionality
  n_nodes = len(node_owners) # Number of nodes in the system
  n_usss = len(set(node_owners)) # Number of USSs in the system
  node_owners = node_owners
  uss_configs = [] # List of boolean arrays mapping USS index to whether that USS is up
  for uss_config in itertools.product((True, False), repeat=n_usss):
    uss_configs.append(tuple(uss_config))
  node_configs = [] # List of boolean arrays mapping node index to whether that node is up
  for node_config in itertools.product((True, False), repeat=n_nodes):
    node_configs.append(tuple(node_config))

  survivals = np.zeros((n_nodes + 1, n_usss + 1), dtype=float) # Whether the range continued to be available after a failure of j USSs plus i other nodes
  counts = np.zeros((n_nodes + 1, n_usss + 1), dtype=float) # Number of scenarios where there was a failure of j USSs plus i other nodes
  replicas_by_uss = np.zeros((n_usss,), dtype=int)

  active_nodes_configs = [] # List of boolean arrays mapping node index to whether that node contains an active replica
  for active_nodes_config in itertools.combinations(range(len(node_owners)), replicas):
    if replica_per_uss:
      replicas_by_uss[:] = 0
      for active_node in active_nodes_config:
        replicas_by_uss[node_owners[active_node]] = 1
      valid = np.all(replicas_by_uss > 0)
      if not valid:
        continue
    active_nodes = set(active_nodes_config)
    node_active = tuple(n in active_nodes for n in range(n_nodes))
    active_nodes_configs.append(node_active)

  # Information regarding how much more time the processing will take
  start_time = datetime.datetime.utcnow()
  last_print = datetime.datetime.utcnow()
  print_every = datetime.timedelta(minutes=5)
  n_configs_processed = 0

  for uss_up in uss_configs:
    n_usss_down = sum(not up for up in uss_up)
    node_up_uss = tuple(uss_up[node_owners[n]] for n in range(n_nodes))
    for node_active in active_nodes_configs:
      for node_up in node_configs:
        n_other_nodes_down = sum(node_up_uss[n] and not node_up[n] for n in range(n_nodes))
        counts[n_other_nodes_down, n_usss_down] += 1
        up_replicas = sum(node_up_uss[n] and node_up[n] and node_active[n] for n in range(n_nodes))
        if up_replicas >= min_replicas:
          survivals[n_other_nodes_down, n_usss_down] += 1

      n_configs_processed += 1
      if datetime.datetime.utcnow() > last_print + print_every:
        fraction_complete = n_configs_processed / (len(uss_configs) * len(active_nodes_configs))
        last_print = datetime.datetime.utcnow()
        print('{:2f}% complete, {:1f} minutes remaining'.format(fraction_complete * 100, (1 - fraction_complete) * ((last_print - start_time).total_seconds() / 60) / fraction_complete))

  survival_rate = np.divide(survivals, counts,
                            where=counts>0,
                            out=np.zeros(counts.shape, dtype=float))

  print('Replica per USS' if replica_per_uss else 'Free replica placement')
  print('Survivability for {} USSs\n{} replicas'.format(n_usss, replicas))
  for r in range(survival_rate.shape[0]):
    print('\t'.join(str(survival_rate[r,c]) if counts[r,c] > 0 else ''
                    for c in range(survival_rate.shape[1])))


replica_per_uss = True

# print_survivability((0, 0, 0, 0, 0, 0), 5, replica_per_uss)
#
# print_survivability((0, 0, 0, 0, 1, 1), 5, replica_per_uss)
#
# print_survivability((0, 0, 1, 1, 2, 2), 5, replica_per_uss)
#
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3), 5, replica_per_uss)
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3), 7, replica_per_uss)
#
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4), 5, replica_per_uss)
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4), 7, replica_per_uss)
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4), 9, replica_per_uss)
#
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5), 7, replica_per_uss)
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5), 9, replica_per_uss)
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5), 11, replica_per_uss)
#
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6), 9, replica_per_uss)
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6), 11, replica_per_uss)
# print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6), 13, replica_per_uss)

print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6), 9, True)
print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6), 11, True)
print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6), 13, True)
print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6), 9, False)
print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6), 11, False)
print_survivability((0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6), 13, False)
