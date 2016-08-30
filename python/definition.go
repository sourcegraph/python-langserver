package python

import (
	"encoding/json"
	"fmt"
	"os/exec"
	"strconv"

	"sourcegraph.com/sourcegraph/sourcegraph/pkg/jsonrpc2"
	"sourcegraph.com/sourcegraph/sourcegraph/pkg/lsp"
)

type jediPosResult struct {
	Path   string `json:"path"`
	Line   int    `json:"line"`
	Column int    `json:"column"`
}

func (h *Handler) handleDefinition(req *jsonrpc2.Request, params lsp.TextDocumentPositionParams) ([]lsp.Location, error) {
	b, err := cmdOutput(nil, exec.Command("langserver-python.py",
		"--path", h.filePath(params.TextDocument.URI),
		"--line", strconv.Itoa(params.Position.Line+1),
		"--column", strconv.Itoa(params.Position.Character),
		"definition",
	))
	if err != nil {
		return nil, err
	}

	if len(b) == 0 || b[0] != '{' {
		return nil, fmt.Errorf("error response: %s", b)
	}

	var result *jediPosResult
	if err = json.Unmarshal(b, &result); err != nil {
		return nil, fmt.Errorf("unmarshal JSON: %s", b)
	}

	pos := lsp.Position{
		Line:      result.Line - 1,
		Character: result.Column,
	}
	var locs []lsp.Location
	locs = append(locs, lsp.Location{
		URI: "file://" + result.Path,
		Range: lsp.Range{
			Start: pos,
			End:   pos,
		},
	})
	return locs, nil
}
