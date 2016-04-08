package stacker

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCompile(t *testing.T) {
	vpc := &Stack{Name: "vpc"}
	bastion := &Stack{
		Name: "bastion",
		Parameters: map[string]string{
			"Something": "Thing",
			"VpcId":     "vpc::Id",
		},
	}
	metaStack := &MetaStack{
		Stacks: []*Stack{vpc, bastion},
	}

	plan, err := Compile(metaStack)
	assert.NoError(t, err)
	assertPlan(t, `
(root)
  bastion
  vpc
bastion
  vpc
vpc
`, plan)
}

func TestCompile_CircularDependencies(t *testing.T) {
	vpc := &Stack{Name: "vpc"}
	db := &Stack{Name: "db", Parameters: map[string]string{"AppName": "app::Name"}}
	app := &Stack{Name: "app", Parameters: map[string]string{"DatabaseUrl": "db::Url"}}
	metaStack := &MetaStack{
		Stacks: []*Stack{vpc, db, app},
	}

	_, err := Compile(metaStack)
	assert.Error(t, err)
}

func assertPlan(t testing.TB, expected string, plan *Plan) {
	assert.Equal(t, strings.TrimSpace(expected)+"\n", plan.String())
}
