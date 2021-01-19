import subprocess
import sys

"""
This script produces a graph indicating what dependencies lead to specified
modules being included in the Go distribution.

Usage:
  python why_go_sum.py github.com/example/module-1 github.com/example/module-2 [...]
The arguments are a list of modules of interest.  These modules and their
ancestor dependencies will be included in the output graph.

Output:
go_mod_graph.gv: Graphviz descriptor of the module dependencies
go_mod_graph.png: Produced if `dot` is present on the system, a Graphviz
  rendering of go_mod_graph.gv.
"""

def main():
  keywords = sys.argv

  lines = subprocess.check_output(['go', 'mod', 'graph']).decode('utf8').split('\n')

  connections = set()
  parents = {}
  children = {}
  for line in lines:
    cols = line.split(' ')
    if len(cols) != 2:
      continue
    parent, child = cols
    parent = parent.split('@')[0]
    child = child.split('@')[0]

    connections.add((parent, child))

    deps = children.get(parent, set())
    deps.add(child)
    children[parent] = deps

    parent_set = parents.get(child, set())
    parent_set.add(parent)
    parents[child] = parent_set

  key_nodes = set()
  for child in children.keys():
    for kw in keywords:
      if kw in child:
        key_nodes.add(child)
  for parent in parents.keys():
    for kw in keywords:
      if kw in parent:
        key_nodes.add(parent)

  relevant = set()
  processed = set()
  for kn in key_nodes:
    queue = [kn]
    while queue:
      n = queue[0]
      queue = queue[1:]
      if n not in processed:
        relevant.add(n)
        for p in parents.get(n, []):
          queue.append(p)
        processed.add(n)

  with open('go_mod_graph.gv', 'w') as f:
    f.write('digraph g {\n')
    f.write('  node [shape=box]\n')
    for kn in key_nodes:
      f.write('  "{}" [color=red]\n'.format(kn))
    for connection in connections:
      if connection[0] in relevant and connection[1] in relevant:
        f.write('  "{}" -> "{}"\n'.format(connection[0], connection[1]))
    f.write('}\n')

  img_gen = subprocess.check_output(['dot', '-Tpng', '-ogo_mod_graph.png', 'go_mod_graph.gv']).decode('utf8')
  print(img_gen)


if __name__ == '__main__':
  main()
