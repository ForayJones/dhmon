#!/usr/bin/env python
import collections
import socket
import sys
import time


BulkMetric = collections.namedtuple('BulkMetric', [
  'timestamp', 'hostname', 'metric', 'value'])


backend = None


class CassandraBackend(object):

  def connect(self):
    import cassandra.cluster
    self.cluster = cassandra.cluster.Cluster(['metricstore.event.dreamhack.se'])
    self.session = self.cluster.connect('metric')
    sql = ('UPDATE metric SET data = data + ? WHERE tenant = \'\' AND '
          'rollup = ? AND period = ? AND path = ? AND time = ?')
    self.prepared_insert = self.session.prepare(sql)
    self.ops = []
    self.rollup = 30
    self.period = 86400
    return True

  def queue(self, timestamp, path, value):
    self.ops.append(self.session.execute_async(
      self.prepared_insert, ([value], self.rollup, self.period,
        path, timestamp)))

  def finish(self):
    for op in self.ops:
      op.result()


class CarbonBackend(object):

  def connect(self):
    carbon_address = ('metricstore.event.dreamhack.se', 2003)
    try:
      self.carbon_socket = socket.socket()
      self.carbon_socket.connect(carbon_address)
    except Exception as e:
      return False
    return True

  def queue(self, timestamp, path, value):
    carbon_msg = '%s %s %s\n' % (path, value, timestamp)
    self.carbon_socket.send(carbon_msg)

  def finish(self):
    pass


def connect(backend_cls=CassandraBackend):
  global backend
  backend = backend_cls()
  return backend.connect()


def metric(metric, value, hostname=None, timestamp=None):
  if timestamp is None:
      timestamp = int(time.time())
  if hostname is None:
      hostname = socket.getfqdn()

  return metricbulk([
    BulkMetric(timestamp=timestamp, hostname=hostname,
      metric=metric, value=value)])


def metricbulk(values):
  if backend is None:
    connect()

  ops = []
  for bulkmetric in values:
    rev_hostname = '.'.join(reversed(bulkmetric.hostname.split('.')))
    path = 'dh.%s.%s' % (rev_hostname, bulkmetric.metric)
    rollup = 30
    period = 86400
    timestamp = (int(bulkmetric.timestamp) / rollup) * rollup
    backend.queue(timestamp, path, int(bulkmetric.value))

  backend.finish()

  return True
