""" Tests on the DAG implementation """
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import threading

import pytest

from stacker.dag import (
    DAG,
    DAGValidationError,
    ThreadedWalker,
    UnlimitedSemaphore
)


@pytest.fixture
def empty_dag():
    return DAG()


@pytest.fixture
def basic_dag():
    dag = DAG()
    dag.from_dict({'a': ['b', 'c'],
                   'b': ['d'],
                   'c': ['d'],
                   'd': []})
    return dag


def test_add_node(empty_dag):
    dag = empty_dag

    dag.add_node('a')
    assert dag.graph == {'a': set()}


def test_transpose(basic_dag):
    dag = basic_dag

    transposed = dag.transpose()
    assert transposed.graph == {'d': set(['c', 'b']),
                                'c': set(['a']),
                                'b': set(['a']),
                                'a': set([])}


def test_add_edge(empty_dag):
    dag = empty_dag

    dag.add_node('a')
    dag.add_node('b')
    dag.add_edge('a', 'b')
    assert dag.graph == {'a': set('b'), 'b': set()}


def test_from_dict(empty_dag):
    dag = empty_dag

    dag.from_dict({'a': ['b', 'c'],
                   'b': ['d'],
                   'c': ['d'],
                   'd': []})
    assert dag.graph == {'a': set(['b', 'c']),
                         'b': set('d'),
                         'c': set('d'),
                         'd': set()}


def test_reset_graph(empty_dag):
    dag = empty_dag

    dag.add_node('a')
    assert dag.graph == {'a': set()}
    dag.reset_graph()
    assert dag.graph == {}


def test_walk(empty_dag):
    dag = empty_dag

    # b and c should be executed at the same time.
    dag.from_dict({'a': ['b', 'c'],
                   'b': ['d'],
                   'c': ['d'],
                   'd': []})

    nodes = []

    def walk_func(n):
        nodes.append(n)
        return True

    dag.walk(walk_func)
    assert nodes == ['d', 'c', 'b', 'a'] or nodes == ['d', 'b', 'c', 'a']


def test_ind_nodes(basic_dag):
    dag = basic_dag
    assert dag.ind_nodes() == ['a']


def test_topological_sort(empty_dag):
    dag = empty_dag
    dag.from_dict({'a': [],
                   'b': ['a'],
                   'c': ['b']})
    assert dag.topological_sort() == ['c', 'b', 'a']


def test_successful_validation(basic_dag):
    dag = basic_dag
    assert dag.validate()[0] == True  # noqa: E712


def test_failed_validation(empty_dag):
    dag = empty_dag

    with pytest.raises(DAGValidationError):
        dag.from_dict({'a': ['b'],
                       'b': ['a']})


def test_downstream(basic_dag):
    dag = basic_dag
    assert set(dag.downstream('a')) == set(['b', 'c'])


def test_all_downstreams(basic_dag):
    dag = basic_dag

    assert dag.all_downstreams('a') == ['b', 'c', 'd']
    assert dag.all_downstreams('b') == ['d']
    assert dag.all_downstreams('d') == []


def test_all_downstreams_pass_graph(empty_dag):
    dag = empty_dag
    dag.from_dict({'a': ['c'],
                   'b': ['d'],
                   'c': ['d'],
                   'd': []})
    assert dag.all_downstreams('a') == ['c', 'd']
    assert dag.all_downstreams('b') == ['d']
    assert dag.all_downstreams('d') == []


def test_predecessors(basic_dag):
    dag = basic_dag

    assert set(dag.predecessors('a')) == set([])
    assert set(dag.predecessors('b')) == set(['a'])
    assert set(dag.predecessors('c')) == set(['a'])
    assert set(dag.predecessors('d')) == set(['b', 'c'])


def test_filter(basic_dag):
    dag = basic_dag

    dag2 = dag.filter(['b', 'c'])
    assert dag2.graph == {'b': set('d'),
                          'c': set('d'),
                          'd': set()}


def test_all_leaves(basic_dag):
    dag = basic_dag

    assert dag.all_leaves() == ['d']


def test_size(basic_dag):
    dag = basic_dag

    assert dag.size() == 4
    dag.delete_node('a')
    assert dag.size() == 3


def test_transitive_reduction_no_reduction(empty_dag):
    dag = empty_dag
    dag.from_dict({'a': ['b', 'c'],
                   'b': ['d'],
                   'c': ['d'],
                   'd': []})
    dag.transitive_reduction()
    assert dag.graph == {'a': set(['b', 'c']),
                         'b': set('d'),
                         'c': set('d'),
                         'd': set()}


def test_transitive_reduction(empty_dag):
    dag = empty_dag
    # https://en.wikipedia.org/wiki/Transitive_reduction#/media/File:Tred-G.svg
    dag.from_dict({'a': ['b', 'c', 'd', 'e'],
                   'b': ['d'],
                   'c': ['d', 'e'],
                   'd': ['e'],
                   'e': []})
    dag.transitive_reduction()
    # https://en.wikipedia.org/wiki/Transitive_reduction#/media/File:Tred-Gprime.svg
    assert dag.graph == {'a': set(['b', 'c']),
                         'b': set('d'),
                         'c': set('d'),
                         'd': set('e'),
                         'e': set()}


def test_transitive_deep_reduction(empty_dag):
    dag = empty_dag
    # https://en.wikipedia.org/wiki/Transitive_reduction#/media/File:Tred-G.svg
    dag.from_dict({
        'a': ['b', 'd'],
        'b': ['c'],
        'c': ['d'],
        'd': [],
    })
    dag.transitive_reduction()
    # https://en.wikipedia.org/wiki/Transitive_reduction#/media/File:Tred-Gprime.svg
    assert dag.graph == {'a': set('b'),
                         'b': set('c'),
                         'c': set('d'),
                         'd': set()}


def test_threaded_walker(empty_dag):
    dag = empty_dag

    walker = ThreadedWalker(UnlimitedSemaphore())

    # b and c should be executed at the same time.
    dag.from_dict({'a': ['b', 'c'],
                   'b': ['d'],
                   'c': ['d'],
                   'd': []})

    lock = threading.Lock()  # Protects nodes from concurrent access
    nodes = []

    def walk_func(n):
        lock.acquire()
        nodes.append(n)
        lock.release()
        return True

    walker.walk(dag, walk_func)
    assert nodes == ['d', 'c', 'b', 'a'] or nodes == ['d', 'b', 'c', 'a']
