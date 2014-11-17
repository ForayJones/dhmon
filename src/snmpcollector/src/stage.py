import abc
import argparse
import logging
import logging.handlers
import os
import pickle
import pika
import sys
import time

import config

class Action(object):
  """Base class that represents an Action that moves between stages."""
  __metadata__ = abc.ABCMeta

  @abc.abstractmethod
  def do(self, stage):
    """Execute an action, return a list of result actions."""
    pass


class Stage(object):
  """Base class for SNMP collector workers.

  By implementing this class you will get access to the
  appropriate RabbitMQ queues and event processing.

  When an Action instance is pushed, it will be executed with the
  stage (class instance) as a parameter.
  """

  def __init__(self, name, task_queue=None, result_queue=None, mq='localhost'):
    self.name = name
    self.task_queue = 'dhmon:%s' % task_queue if task_queue else None
    self.result_queue = 'dhmon:%s' % result_queue if result_queue else None
    self.mq = mq
    self.task_channel = None
    self.result_channel = None

    self.connection = pika.BlockingConnection(
        pika.ConnectionParameters(self.mq))
    if result_queue:
      self.result_channel = self.connection.channel()

  def startup(self):
    config.load('/etc/snmpcollector.yaml')
    logging.info('Started %s', self.name)

  def shutdown(self):
    logging.info('Terminating %s', self.name)
    self.connection.close()

  def push(self, action):
    if not self.result_channel:
      return
    self.result_channel.basic_publish(
        exchange='', routing_key=self.result_queue,
        body=pickle.dumps(action, protocol=pickle.HIGHEST_PROTOCOL))

  def _task_callback(self, channel, method, properties, body):
    action = pickle.loads(body)
    if not isinstance(action, Action):
      print >>sys.stderr, 'Got non-action in task queue:', repr(body)
      channel.basic_ack(delivery_tag=method.delivery_tag)
      return

    # Buffer up on all outgoing actions to ack only when we're done
    actions = list(action.do(self))

    # Ack now, if we die during sending we will hopefully not crash loop
    channel.basic_ack(delivery_tag=method.delivery_tag)
    for action in actions:
      self.push(action)

  def _setup(self, purge_task_queue):
    root = logging.getLogger()
    root.addHandler(logging.handlers.SysLogHandler('/dev/log'))
    root.setLevel(logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--debug', dest='debug', action='store_const', const=True,
        default=False, help='do not fork, print output to console')
    parser.add_argument('pidfile', help='pidfile to write')
    args = parser.parse_args()

    if args.debug:
      root.setLevel(logging.INFO)
      ch = logging.StreamHandler(sys.stdout)
      ch.setLevel(logging.INFO)
      formatter = logging.Formatter( '%(asctime)s - %(name)s - '
          '%(levelname)s - %(message)s' )
      ch.setFormatter(formatter)
      root.addHandler(ch)
      self._internal_run(args.pidfile, purge_task_queue)
    else:
      with daemon.DaemonContext():
        self._internal_run(args.pidfile, purge_task_queue)

  def run(self, purge_task_queue=False):
    if not self.task_queue:
      raise ValueError('Cannot run a stage that lacks an input queue')

    self._setup(purge_task_queue)

  def _internal_run(self, pidfile, purge_task_queue):
    logging.info('Starting %s', self.name)

    try:
      import procname
      procname.setprocname(self.name)
    except ImportError:
      pass

    with open(pidfile, 'w') as f:
      f.write(str(os.getpid()))

    self.task_channel = self.connection.channel()
    self.task_channel.queue_declare(queue=self.task_queue)

    if purge_task_queue:
      self.task_channel.queue_purge(queue=self.task_queue)

    self.task_channel.basic_consume(self._task_callback, queue=self.task_queue)
    self.startup()
    try:
      self.task_channel.start_consuming()
    except KeyboardInterrupt:
      print >>sys.stderr, 'Keyboard interrupt, shutting down..'
    self.shutdown()