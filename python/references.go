package python

import (
	"encoding/json"
	"fmt"
	"os/exec"
	"strconv"

	"sourcegraph.com/sourcegraph/sourcegraph/pkg/jsonrpc2"
	"sourcegraph.com/sourcegraph/sourcegraph/pkg/lsp"
)

func (h *Handler) handleReferences(req *jsonrpc2.Request, params lsp.ReferenceParams) ([]lsp.Location, error) {
	b, err := cmdOutput(nil, exec.Command("langserver-python.py",
		"--path", h.filePath(params.TextDocument.URI),
		"--line", strconv.Itoa(params.Position.Line+1),
		"--column", strconv.Itoa(params.Position.Character),
		"references",
	))
	if err != nil {
		return nil, err
	}

	if len(b) == 0 || b[0] != '[' {
		return nil, fmt.Errorf("error response: %s", b)
	}

	var results []*jediPosResult
	if err = json.Unmarshal(b, &results); err != nil {
		return nil, fmt.Errorf("unmarshal JSON: %s", b)
	}

	locs := make([]lsp.Location, len(results))
	for i := 0; i < len(results); i++ {
		pos := lsp.Position{
			Line:      results[i].Line - 1,
			Character: results[i].Column,
		}
		locs[i] = lsp.Location{
			URI: "file://" + results[i].Path,
			Range: lsp.Range{
				Start: pos,
				End:   pos,
			},
		}
	}
	return locs, nil
}
