package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"

	"github.com/sourcegraph/langserver/client"

	"github.com/sourcegraph/go-langserver/pkg/lsp"
)

var (
	mode     = flag.String("mode", "stdio", "communication mode (stdio|tcp)")
	addr     = flag.String("addr", ":2088", "server listen address (tcp)")
	rootPath = flag.String("root", "", "workspace root path")
	cmd      = flag.String("cmd", "", "langserver executable command (for stdio mode)")
	ctx      = context.Background()
	stdin    = bufio.NewReader(os.Stdin)
)

func main() {
	flag.Parse()
	log.SetFlags(0)

	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run() error {
	if *rootPath == "" {
		return fmt.Errorf("specify a workspace root")
	}
	if *mode == "stdio" && *cmd == "" {
		return fmt.Errorf("specify a command to run to start a language server")
	}

	var c *client.LspConn
	var e *exec.Cmd
	var err error

	switch *mode {
	case "tcp":
		c, err = client.NewTCPClient(ctx, *addr)

	case "stdio":
		c, e, err = client.NewStdioClient(ctx, *cmd)

	default:
		return fmt.Errorf("invalid mode (tcp|stdio): %s", *mode)
	}

	if err != nil {
		return err
	}

	defer c.Close()
	if e != nil {
		defer e.Process.Kill()
	}

	err = c.Initialize(ctx, *rootPath)
	if err != nil {
		return err
	}

	for {
		method := promptMethod()
		if method == "" {
			continue
		}
		if method == "shutdown" {
			break
		}

		var (
			p lsp.TextDocumentPositionParams
			q lsp.WorkspaceSymbolParams
		)
		if method == "symbol" {
			query := promptQuery()
			q = lsp.WorkspaceSymbolParams{
				Query: query,
				Limit: 10,
			}
		} else {
			file := promptFile()
			if file == "" || filepath.IsAbs(file) {
				continue
			}

			line := promptLine()
			char := promptCharacter()

			p = lsp.TextDocumentPositionParams{
				TextDocument: lsp.TextDocumentIdentifier{URI: file},
				Position:     lsp.Position{Line: line, Character: char},
			}
		}

		printResponse := func(resp interface{}, err error) {
			if err != nil {
				fmt.Println("ERROR: ", err)
			}
			j, _ := json.MarshalIndent(resp, "", "\t")
			fmt.Printf("\n\n%v\n\n\n", string(j))
		}

		switch method {
		case "hover":
			resp, err := c.Hover(ctx, &p)
			printResponse(resp, err)

		case "definition":
			resp, err := c.Definition(ctx, &p)
			printResponse(resp, err)

		case "references":
			resp, err := c.References(ctx, &p)
			printResponse(resp, err)

		case "symbol":
			resp, err := c.Symbol(ctx, &q)
			printResponse(resp, err)

		default:
			continue
		}
	}

	err = c.Shutdown(ctx)
	if err != nil {
		return err
	}

	return nil
}

func promptString(prompt string) string {
	fmt.Print(prompt)
	var text string
	fmt.Scanln(&text)
	return text
}

func promptInt(prompt string) int {
	for {
		i, err := strconv.Atoi(promptString(prompt))
		if err == nil {
			return i
		}
	}
}

func promptMethod() string {
	switch promptString("Choose (1) hover, (2) definition, (3) references, (4) symbol, (5) shutdown: ") {
	case "1":
		return "hover"
	case "2":
		return "definition"
	case "3":
		return "references"
	case "4":
		return "symbol"
	case "5":
		return "shutdown"
	default:
		return ""
	}
}

func promptFile() string {
	return promptString("Choose a file path relative to root: ")
}

func promptQuery() string {
	return promptString("Enter a query: ")
}

func promptLine() int {
	return promptInt("Choose a 0-indexed line: ")
}

func promptCharacter() int {
	return promptInt("Choose a 0-indexed character offset for that line: ")
}
