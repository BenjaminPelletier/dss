import logging
import sys

from app import webapp

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('DSS')


def main(argv):
  del argv

  log.info('Starting webserver...')
  webapp.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
  main(sys.argv)
