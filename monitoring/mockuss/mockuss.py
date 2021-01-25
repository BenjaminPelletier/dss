import sys

from monitoring.mockuss import webapp


def main(argv):
  del argv
  webapp.run(host='localhost', port=8086)


if __name__ == '__main__':
  main(sys.argv)
