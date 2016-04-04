package stacker_test

import (
	"fmt"
	"log"

	"github.com/remind101/stacker"
)

var vpc = &stacker.Stack{
	Name:     "vpc",
	Template: ``,
}

var bastion = &stacker.Stack{
	Name:     "bastion",
	Template: ``,
	Parameters: map[string]string{
		"VpcId": "vpc::Id",
	},
}

var metaStack = &stacker.MetaStack{
	Stacks: []*stacker.Stack{vpc, bastion},
}

func Example() {
	plan, err := stacker.Compile(metaStack)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(plan.String())

	//if err := stacker.Run(metaStack); err != nil {
	//log.Fatal(err)
	//}
}
