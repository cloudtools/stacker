package main

import (
	"log"
	"os"

	"github.com/codegangsta/cli"
	"github.com/remind101/stacker"
)

var buildCommand = cli.Command{
	Name:    "build",
	Aliases: []string{"b"},
	Usage:   "Build stacks from a stacker configuration file",
	Action:  runBuild,
}

func runBuild(c *cli.Context) {
	config, err := stacker.Parse(os.Stdin)
	if err != nil {
		log.Fatal(err)
	}

	plan, err := stacker.Compile(config)
	if err != nil {
		log.Fatal(err)
	}

	stacker := newStacker()
	err = stacker.Execute(plan)
	if err != nil {
		log.Fatal(err)
	}
}

func main() {
	log.SetFlags(0)

	app := cli.NewApp()
	app.Name = "stacker"
	app.Version = stacker.Version
	app.Usage = "Glue for CloudFormation stacks"
	app.Commands = []cli.Command{
		buildCommand,
	}

	app.Run(os.Args)
}

func newStacker() *stacker.Stacker {
	return stacker.NewDefault()
}
