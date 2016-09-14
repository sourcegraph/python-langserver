package testharness

import "sourcegraph.com/sourcegraph/sourcegraph/pkg/lsp"

// TestCase includes specific hover, definition, and references cases for a
// particular repository.
type TestCase struct {
	Repo            string
	HoverCases      []HoverCase
	DefinitionCases []DefinitionCase
	ReferencesCases []ReferencesCase
}

// HoverCase encodes the expected result for a hover operation.
type HoverCase struct {
	File      string
	Line      int
	Character int
	Resp      lsp.Hover
}

// ToRequestParams provides syntactic sugar for writing test cases.
func (hc *HoverCase) ToRequestParams() *lsp.TextDocumentPositionParams {
	return &lsp.TextDocumentPositionParams{
		TextDocument: lsp.TextDocumentIdentifier{URI: hc.File},
		Position:     lsp.Position{Line: hc.Line, Character: hc.Character},
	}
}

// DefinitionCase encodes the expected result for a definition operation.
type DefinitionCase struct {
	File      string
	Line      int
	Character int
	Resp      []lsp.Location
}

// ToRequestParams provides syntactic sugar for writing test cases.
func (dc *DefinitionCase) ToRequestParams() *lsp.TextDocumentPositionParams {
	return &lsp.TextDocumentPositionParams{
		TextDocument: lsp.TextDocumentIdentifier{URI: dc.File},
		Position:     lsp.Position{Line: dc.Line, Character: dc.Character},
	}
}

// ReferencesCase encodes the expected result for a references operation.
type ReferencesCase struct {
	File      string
	Line      int
	Character int
	Resp      []lsp.Location
}

// ToRequestParams provides syntactic sugar for writing test cases.
func (rc *ReferencesCase) ToRequestParams() *lsp.TextDocumentPositionParams {
	return &lsp.TextDocumentPositionParams{
		TextDocument: lsp.TextDocumentIdentifier{URI: rc.File},
		Position:     lsp.Position{Line: rc.Line, Character: rc.Character},
	}
}
