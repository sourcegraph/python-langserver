package python

import (
	"os/exec"
	"strconv"

	"sourcegraph.com/sourcegraph/sourcegraph/pkg/jsonrpc2"
	"sourcegraph.com/sourcegraph/sourcegraph/pkg/lsp"
)

func (h *Handler) handleHover(req *jsonrpc2.Request, params lsp.TextDocumentPositionParams) (*lsp.Hover, error) {
	b, err := cmdOutput(nil, exec.Command("langserver-python.py", "hover",
		"--path", h.filePath(params.TextDocument.URI),
		"--line", strconv.Itoa(params.Position.Line+1),
		"--column", strconv.Itoa(params.Position.Character),
	))
	if err != nil {
		return nil, err
	}

	return &lsp.Hover{
		Contents: []lsp.MarkedString{{Language: "text/plain", Value: string(b)}},
	}, nil
}
