# CASA 2.6 rules: Controlled aerodromes

## Overview

In this scenario, a simulated user "views" a virtual airspace map with controlled aerodrome features and the USS is expected to indicate whether the USS's app will indicate to the user that the location of interest is expected to block a flight, produce an advisory, or neither.

## Resources

### airspace_map_providers

The set of USSs providing airspace maps to users.

### inside_no_fly_zone_locations

A set of map locations inside the 3nm no-fly zone

### outside_no_fly_zone_locations

A set of map locations outside the 3nm no-fly zone

## 3nm no-fly zone test case

### Inside no-fly zone test step

In this step, for each different rule set, uss_qualifier queries each airspace map provider for relevant geometry at locations known to be inside the 3nm no-fly zone.

#### Hobbyist block check

Per **HBY0030**, the USS must indicate to the hobbyist user that a flight involving the queried location would be blocked.

#### Commercial excluded check

Per **CEX0030**, the USS must indicate to the commercial excluded user that a flight involving the queried location would be blocked.

#### ReOC check

Per **ReOC0025**, the USS must indicate to the ReOC user that a flight involving the queried location would be accompanied by an advisory.

### Outside no-fly zone test step

This step repeats the previous step, except with locations that are outside (sometimes barely outside) the 3nm no-fly zone.

#### Hobbyist block check

Per **HBY0030**, the USS must not indicate to the hobbyist user that a flight involving the queried location would be blocked or carry an advisory.

#### Commercial excluded check

Per **CEX0030**, the USS must not indicate to the commercial excluded user that a flight involving the queried location would be blocked or carry an advisory.

#### ReOC check

Per **ReOC0025**, the USS must not indicate to the ReOC user that a flight involving the queried location would be blocked or carry an advisory.
