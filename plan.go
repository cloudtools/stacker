package stacker

import "github.com/remind101/stacker/dag"

// Plan represents a compiled MetaStack that can be executed.
type Plan struct {
	graph dag.AcyclicGraph
}

// String returns a string representation of the Plan.
func (p *Plan) String() string {
	return p.graph.String()
}

// Validates that there are no cyclic dependencies.
func (p *Plan) Validate() error {
	return p.graph.Validate()
}
