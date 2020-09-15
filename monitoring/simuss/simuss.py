import sys

from monitoring.simuss import webapp


def main(argv):
  del argv
  webapp.run(host='localhost', port=5000)


if __name__ == '__main__':
  main(sys.argv)
