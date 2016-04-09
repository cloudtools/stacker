package stacker

import (
	"fmt"

	"github.com/remind101/stacker/dag"
)

// Plan represents a compiled MetaStack that can be executed.
type Plan struct {
	metaStack *MetaStack
	graph     dag.AcyclicGraph
}

// Compile takes a MetaStack and compiles it into a dependency tree.
func Compile(metaStack *MetaStack) (*Plan, error) {
	plan := Plan{metaStack: metaStack}
	plan.graph.Add(metaStack)
	for _, stack := range metaStack.Stacks {
		plan.graph.Add(stack)
		plan.graph.Connect(dag.BasicEdge(metaStack, stack))
	}

	for _, stack := range metaStack.Stacks {
		for _, p := range stack.Parameters {
			if p.Ref != nil {
				dep := metaStack.Stack(p.Ref.Stack)
				if dep == nil {
					panic(fmt.Sprintf("%s not found in stack", p.Ref.Stack))
				}
				plan.graph.Connect(dag.BasicEdge(stack, dep))
			}
		}
	}

	return &plan, plan.Validate()
}

// String returns a string representation of the Plan.
func (p *Plan) String() string {
	return p.graph.String()
}

// Validates that there are no cyclic dependencies.
func (p *Plan) Validate() error {
	return p.graph.Validate()
}
