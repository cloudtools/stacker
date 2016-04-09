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
		config: strings.NewReader(`
{
  "Stacks": [
    {
      "Name": "vpc"
    },
    {
      "Name": "bastion",
      "Parameters": {
        "VpcId": "vpc::Id"
      }
    }
  ]
}`),
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
		config: strings.NewReader(`
{
  "Stacks": [
    {
      "Name": "vpc"
    },
    {
      "Name": "database",
      "Parameters": {
        "VpcId": "vpc::Id"
      }
    },
    {
      "Name": "application",
      "Parameters": {
        "DatabaseUrl": "database::Url"
      }
    }
  ]
}`),
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
		config: strings.NewReader(`
{
  "Stacks": [
    {
      "Name": "vpc"
    },
    {
      "Name": "bastion",
      "Parameters": {
        "VpcId": "vpc::Id"
      }
    },
    {
      "Name": "database",
      "Parameters": {
	"VpcId": "vpc::Id"
      }
    },
    {
      "Name": "application",
      "Parameters": {
	"DatabaseUrl": "database::Url"
      }
    }
  ]
}`),
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

func (p *mockStackBuilder) Exists(stack *stacker.Stack) bool {
	return false
}

func (p *mockStackBuilder) Create(stack *stacker.Stack) (map[string]string, error) {
	return nil, nil
}

func (p *mockStackBuilder) Update(stack *stacker.Stack) (map[string]string, error) {
	return nil, nil
}
