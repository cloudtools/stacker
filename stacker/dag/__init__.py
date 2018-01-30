import collections
import logging
from copy import copy, deepcopy
from collections import deque

logger = logging.getLogger(__name__)

try:
    from collections import OrderedDict
except:
    from ordereddict import OrderedDict


class DAGValidationError(Exception):
    pass


class DAG(object):
    """ Directed acyclic graph implementation. """

    def __init__(self):
        """ Construct a new DAG with no nodes or edges. """
        self.reset_graph()

    def add_node(self, node_name):
        """ Add a node if it does not exist yet, or error out. """
        graph = self.graph
        if node_name in graph:
            raise KeyError('node %s already exists' % node_name)
        graph[node_name] = set()

    def add_node_if_not_exists(self, node_name):
        try:
            self.add_node(node_name)
        except KeyError:
            pass

    def delete_node(self, node_name):
        """ Deletes this node and all edges referencing it. """
        graph = self.graph
        if node_name not in graph:
            raise KeyError('node %s does not exist' % node_name)
        graph.pop(node_name)

        for node, edges in graph.iteritems():
            if node_name in edges:
                edges.remove(node_name)

    def delete_node_if_exists(self, node_name):
        try:
            self.delete_node(node_name)
        except KeyError:
            pass

    def add_edge(self, ind_node, dep_node):
        """ Add an edge (dependency) between the specified nodes. """
        graph = self.graph
        if ind_node not in graph:
            raise KeyError('node %s does not exist' % ind_node)
        if dep_node not in graph:
            raise KeyError('node %s does not exist' % dep_node)
        test_graph = deepcopy(graph)
        test_graph[ind_node].add(dep_node)
        test_dag = DAG()
        test_dag.graph = test_graph
        is_valid, message = test_dag.validate()
        if is_valid:
            graph[ind_node].add(dep_node)
        else:
            raise DAGValidationError(message)

    def delete_edge(self, ind_node, dep_node):
        """ Delete an edge from the graph. """
        graph = self.graph
        if dep_node not in graph.get(ind_node, []):
            raise KeyError('this edge does not exist in graph')
        graph[ind_node].remove(dep_node)

    def transpose(self):
        """ Builds a new graph with the edges reversed. """
        graph = self.graph
        transposed = DAG()
        for node, edges in graph.items():
            transposed.add_node(node)
        for node, edges in graph.items():
            # for each edge A -> B, transpose it so that B -> A
            for edge in edges:
                transposed.add_edge(edge, node)
        return transposed

    def walk(self, walk_func):
        """ Walks each node of the graph in reverse topological order.
        This can be used to perform a set of operations, where the next
        operation depends on the previous operation. It's important to note
        that walking happens serially, and is not paralellized.
        """
        nodes = self.topological_sort()
        # Reverse so we start with nodes that have no dependencies.
        nodes.reverse()
        for n in nodes:
            if not walk_func(n):
                return False

        return True

    def rename_edges(self, old_task_name, new_task_name):
        """ Change references to a task in existing edges. """
        graph = self.graph
        for node, edges in graph.items():
            if node == old_task_name:
                graph[new_task_name] = copy(edges)
                del graph[old_task_name]

            else:
                if old_task_name in edges:
                    edges.remove(old_task_name)
                    edges.add(new_task_name)

    def predecessors(self, node):
        """ Returns a list of all predecessors of the given node """
        graph = self.graph
        return [key for key in graph if node in graph[key]]

    def downstream(self, node):
        """ Returns a list of all nodes this node has edges towards. """
        graph = self.graph
        if node not in graph:
            raise KeyError('node %s is not in graph' % node)
        return list(graph[node])

    def all_downstreams(self, node):
        """Returns a list of all nodes ultimately downstream
        of the given node in the dependency graph, in
        topological order."""
        nodes = [node]
        nodes_seen = set()
        i = 0
        while i < len(nodes):
            downstreams = self.downstream(nodes[i])
            for downstream_node in downstreams:
                if downstream_node not in nodes_seen:
                    nodes_seen.add(downstream_node)
                    nodes.append(downstream_node)
            i += 1
        return filter(
                lambda node: node
                in nodes_seen, self.topological_sort())

    def filter(self, nodes):
        """ Returns a new DAG with only the given nodes and their
        dependencies.
        """

        filtered_dag = DAG()

        # Add only the nodes we need.
        for node in nodes:
            filtered_dag.add_node_if_not_exists(node)
            for edge in self.all_downstreams(node):
                filtered_dag.add_node_if_not_exists(edge)

        # Now, rebuild the graph for each node that's present.
        for node, edges in self.graph.items():
            if node in filtered_dag.graph:
                filtered_dag.graph[node] = edges

        return filtered_dag

    def all_leaves(self):
        """ Return a list of all leaves (nodes with no downstreams) """
        graph = self.graph
        return [key for key in graph if not graph[key]]

    def from_dict(self, graph_dict):
        """ Reset the graph and build it from the passed dictionary.

        The dictionary takes the form of {node_name: [directed edges]}
        """

        self.reset_graph()
        for new_node in graph_dict.iterkeys():
            self.add_node(new_node)
        for ind_node, dep_nodes in graph_dict.iteritems():
            if not isinstance(dep_nodes, collections.Iterable):
                raise TypeError('%s: dict values must be lists' % ind_node)
            for dep_node in dep_nodes:
                self.add_edge(ind_node, dep_node)

    def reset_graph(self):
        """ Restore the graph to an empty state. """
        self.graph = OrderedDict()

    def ind_nodes(self):
        """ Returns a list of all nodes in the graph with no dependencies. """
        graph = self.graph

        dependent_nodes = set(
            node for dependents
            in graph.itervalues() for node in dependents)
        return [node for node in graph.keys() if node not in dependent_nodes]

    def validate(self):
        """ Returns (Boolean, message) of whether DAG is valid. """
        if len(self.ind_nodes()) == 0:
            return (False, 'no independent nodes detected')
        try:
            self.topological_sort()
        except ValueError as e:
            return (False, e.message)
        return (True, 'valid')

    def topological_sort(self):
        """ Returns a topological ordering of the DAG.

        Raises an error if this is not possible (graph is not valid).
        """
        graph = self.graph

        in_degree = {}
        for u in graph:
            in_degree[u] = 0

        for u in graph:
            for v in graph[u]:
                in_degree[v] += 1

        queue = deque()
        for u in in_degree:
            if in_degree[u] == 0:
                queue.appendleft(u)

        l = []
        while queue:
            u = queue.pop()
            l.append(u)
            for v in graph[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.appendleft(v)

        if len(l) == len(graph):
            return l
        else:
            raise ValueError('graph is not acyclic')

    def size(self):
        return len(self)

    def __len__(self):
        return len(self.graph)
