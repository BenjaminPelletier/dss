from monitoring.monitorlib import kml_mechanics
from . import visualization


ICON_ARROW = 'http://maps.google.com/mapfiles/kml/shapes/arrow.png'
ICON_DIAMOND = 'http://maps.google.com/mapfiles/kml/shapes/open-diamond.png'
ICON_AIRPLANE = 'http://maps.google.com/mapfiles/kml/shapes/airports.png'
ICON_HELIPORT = 'http://maps.google.com/mapfiles/kml/shapes/heliport.png'
ICON_RED_PADDLE = 'http://maps.google.com/mapfiles/kml/paddle/red-circle.png'
ICON_YELLOW_PADDLE = 'http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png'
ICON_ORANGE_PADDLE = 'http://maps.google.com/mapfiles/kml/paddle/orange-circle.png'
ICON_GREEN_PADDLE = 'http://maps.google.com/mapfiles/kml/paddle/grn-circle.png'


def add_styles(doc):
  add_style = lambda name, **kwargs: kml_mechanics.add_style(doc, name, **kwargs)
  add_style('target_locked', icon=ICON_RED_PADDLE)
  add_style('target_cooking', icon=ICON_YELLOW_PADDLE)
  add_style('target_waiting', icon=ICON_ORANGE_PADDLE)
  add_style('target_delivering', icon=ICON_GREEN_PADDLE)
  add_style('waypoint', icon=ICON_DIAMOND)

  add_style('op_volume_current_accepted',      line_color='#ffaa0000', line_width=2.0, poly_color='#7daa0000')
  add_style('op_volume_current_activated',     line_color='#ff00aa00', line_width=2.0, poly_color='#7d00aa00')
  add_style('op_volume_current_nonconforming', line_color='#ff00aaff', line_width=2.0, poly_color='#7d00aaff')
  add_style('op_volume_current_contingent',    line_color='#ff0000ff', line_width=2.0, poly_color='#7d0000ff')

  add_style('op_volume_old_accepted',          line_color='#ff00aaff', line_width=2.0, poly_color='#11aa0000')
  add_style('op_volume_old_activated',         line_color='#ff00aaff', line_width=2.0, poly_color='#1100aa00')
  add_style('op_volume_old_nonconforming',     line_color='#ff00aaff', line_width=2.0, poly_color='#113dc8ff')
  add_style('op_volume_old_contingent',        line_color='#ff00aaff', line_width=2.0, poly_color='#113dc8ff')

  add_style('op_volume_future_accepted',       line_color='#ff00aaff', line_width=2.0, poly_color='#7d3dc8ff')
  add_style('op_volume_future_activated',      line_color='#ff00aaff', line_width=2.0, poly_color='#7d3dc8ff')
  add_style('op_volume_future_nonconforming',  line_color='#ff00aaff', line_width=2.0, poly_color='#7d3dc8ff')
  add_style('op_volume_future_contingent',     line_color='#ff00aaff', line_width=2.0, poly_color='#7d3dc8ff')


def render_state(state: visualization.UTMState):
  doc = kml_mechanics.make_document()
  add_styles(doc)

  if state.operations is not None:
    op_folder = kml_mechanics.add_folder(doc, 'Operations')
    for op_id, op in state.operations.items():
      kml_mechanics.add_volume(op_folder, name='{}'.format(op_id))


def kml_draw_reservations(intended_flight, order_folder):
  """Add Placemarks to order_folder showing airspace reservation volumes.

  Args:
    intended_flight: IntendedFlight containing flight plan reservations.
    order_folder: KML folder to which reservation Placemarks should be added.
  """
  flight_folder = kml_mechanics.add_folder(order_folder, 'Reservations')
  origin = intended_flight.flight.reservations[0].shape.polygon.vertices[0]
  offset = kml_mechanics.GetWgs84Egm96Offset(origin.latitude, origin.longitude)
  for leg, reservation in enumerate(intended_flight.flight.reservations, 1):
    kml_mechanics.AddVolume(flight_folder, reservation, 'Leg %i' % leg, -offset,
                       'volume')


def kml_draw_flight_path(intended_flight, order_folder):
  """Add Placemarks to order_folder showing intended flight path.

  Args:
    intended_flight: IntendedFlight containing flight path.
    order_folder: KML folder to which flight path Placemarks should be added.
  """
  request = intended_flight.plan_delivery_request
  path = intended_flight.plan_delivery_response.plan.nominal_path

  waypoint_index = 1
  wp0 = realtime_pb2.Waypoint()
  wp0.position.latitude = request.takeoff_coordinates.latitude
  wp0.position.longitude = request.takeoff_coordinates.longitude
  wp0.position.altitude = 0
  wp0.arrival_time_us = path.start_time_us

  for wp1 in path.waypoints:
    action = realtime_pb2.Waypoint.Action.Name(wp1.action)
    ls = kml_mechanics.AddLineString(
      order_folder,
      [wp0.position.latitude, wp1.position.latitude],
      [wp0.position.longitude, wp1.position.longitude],
      [wp0.position.altitude + path.home_altitude_meters_wgs84,
       wp1.position.altitude + path.home_altitude_meters_wgs84],
      extrude=True,
      name=('%03d' % waypoint_index) + ' ' + action,
      style=action + '_path')
    kml_mechanics.ApplyTimespan(
      ls,
      datetime.datetime.utcfromtimestamp(wp0.arrival_time_us * 1e-6),
      datetime.datetime.utcfromtimestamp(wp1.departure_time_us * 1e-6))
    waypoint_index += 1
    wp0 = wp1


class KmlWriter(processor.FulfilledOrderSetProcessor):
  """Writes a KML per FulfilledOrderSet to a provided output path."""

  def __init__(self, output_path, pretty_print, include_kml_flight_paths,
               include_reservation_volumes, include_order_status):
    """Instantiate a FulfilledOrderSetProcessor to write KMLs.

    Note that the KML is built in memory, so its size cannot exceed available
    memory.  This limitation is generally acceptable because Google Earth cannot
    render more than a certain number of objects, and the working memory limit
    is generally larger than the Google Earth limitation.

    Args:
      output_path: Base path of the KML files to write.
      pretty_print: True for human-readable KML, False for compact.
      include_kml_flight_paths: True to include visualization of the flight path
        from the PlanMissionResponse.
      include_reservation_volumes: True to include visualization of the
        airspacetime reservation volumes.  These visualizations usually have
        high polygon count, and only a limited number can be rendered by Google
        Earth.
      include_order_status: True to include time-bounded point markers on order
        destinations that change according to that order's status.
    """
    self._output_path = output_path
    self._pretty_print = pretty_print
    self._include_kml_flight_paths = include_kml_flight_paths
    self._include_reservation_volumes = include_reservation_volumes
    self._include_order_status = include_order_status

  def process_orders(self, fulfilled_order_set):
    # Overrides method in parent class.

    doc = kml_mechanics.Document()
    kml_add_styles(doc)

    for fulfilled_order in fulfilled_order_set.order:
      order_folder = kml_mechanics.Folder(
        doc, fulfilled_order.fulfillment.customer_order.order_id)

      if self._include_order_status:
        self._draw_target_states(fulfilled_order, order_folder)

      if not fulfilled_order.HasField('intended_flight'):
        continue
      intended_flight = fulfilled_order.intended_flight

      if (self._include_reservation_volumes
        and intended_flight.HasField('flight')):
        kml_draw_reservations(intended_flight, order_folder)

      if (self._include_kml_flight_paths
        and intended_flight.HasField('plan_delivery_response')):
        kml_draw_flight_path(intended_flight, order_folder)

    if not gfile.IsDirectory(self._output_path):
      gfile.MakeDirs(self._output_path)
    filename = os.path.join(
      self._output_path,
      '%s.kml' % processor.fulfilled_order_set_name(fulfilled_order_set))
    with gfile.Open(filename, 'w') as f:
      f.write(kml_mechanics.ToKmlString(doc, self._pretty_print))

  def _draw_target_states(self, fulfilled_order, order_folder):
    """Add Placemarks to order_folder showing states of order fulfillment.

    Args:
      fulfilled_order: FulfilledOrder with the order state changes to display
        as color-coded points on the delivery destination.
      order_folder: KML folder to which state change Placemarks should be added.
    """
    fulfillment = fulfilled_order.fulfillment
    order = fulfillment.customer_order

    request = fulfilled_order.intended_flight.plan_delivery_request
    if request is None:
      return

    # Show the delivery target through various phases of the order
    lat = request.delivery_coordinates.latitude
    lng = request.delivery_coordinates.longitude
    name = order.order_id[-4:] + ' (%s)'

    # Show the delivery target during locked phase
    t0 = order.time_originated.ToDatetime()
    t1 = fulfillment.time_unlocked.ToDatetime()
    if t1 > t0:
      point = kml_mechanics.AddPoint(order_folder, name % 'locked',
                                lat, lng, style='target_locked')
      kml_mechanics.ApplyTimespan(point, t0, t1)
      t0 = t1

    # Show the delivery target during cooking phase
    t1 = fulfillment.time_scanned.ToDatetime()
    if t1 > t0:
      point = kml_mechanics.AddPoint(order_folder, name % 'cooking',
                                lat, lng, style='target_cooking')
      kml_mechanics.ApplyTimespan(point, t0, t1)
      t0 = t1

    # Show the delivery target during pre-takeoff phase
    if not fulfillment.HasField('flight_record'):
      return
    flight_record = fulfillment.flight_record
    t1 = flight_record.time_takeoff.ToDatetime()
    if t1 > t0:
      point = kml_mechanics.AddPoint(order_folder, name % 'waiting',
                                lat, lng, style='target_waiting')
      kml_mechanics.ApplyTimespan(point, t0, t1)
      t0 = t1

    # Show the delivery target during delivery phase
    if not flight_record.HasField('time_delivery'):
      return
    t1 = flight_record.time_delivery.ToDatetime()
    if t1 > t0:
      point = kml_mechanics.AddPoint(order_folder, name % 'delivering',
                                lat, lng, style='target_delivering')
      kml_mechanics.ApplyTimespan(point, t0, t1)
