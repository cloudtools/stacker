package stacker_test

import (
	"io"
	"strings"
	"testing"

	"github.com/remind101/stacker"
	"github.com/stretchr/testify/assert"
)

var planTests = []struct {
	config io.Reader
	plan   string
}{
	{
		config: strings.NewReader(`---
stacks:
  - name: vpc
  - name: bastion
    parameters:
      VpcId: vpc::Id
`),
		plan: `
(root)
  bastion
  vpc
bastion
  vpc
vpc
`,
	},

	{
		config: strings.NewReader(`---
stacks:
  - name: vpc
  - name: database
    parameters:
      VpcId: vpc::Id
  - name: application
    parameters:
      DatabseUrl: database::Url
`),
		plan: `
(root)
  application
  database
  vpc
application
  database
database
  vpc
vpc
`,
	},

	{
		config: strings.NewReader(`---
stacks:
  - name: vpc
  - name: bastion
    parameters:
      VpcId: vpc::Id
  - name: database
    parameters:
      VpcId: vpc::Id
  - name: application
    parameters:
      DatabseUrl: database::Url
`),
		plan: `
(root)
  application
  bastion
  database
  vpc
application
  database
bastion
  vpc
database
  vpc
vpc
`,
	},
}

func TestStacker(t *testing.T) {
	for _, tt := range planTests {
		m, err := stacker.Parse(tt.config)
		assert.NoError(t, err)

		plan, err := stacker.Compile(m)
		assert.NoError(t, err)
		assert.Equal(t, strings.TrimSpace(tt.plan)+"\n", plan.String())

		s := stacker.New(new(mockStackBuilder))
		err = s.Execute(plan)
		assert.NoError(t, err)
	}
}

type mockStackBuilder struct{}

func (p *mockStackBuilder) Build(stack *stacker.Stack) (map[string]string, error) {
	return nil, nil
}
